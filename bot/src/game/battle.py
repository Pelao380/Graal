"""Motor de batalla por turnos con decisiones ocultas.

Reglas implementadas (ver docs/reglas-graal.md):

- Todos eligen en secreto; el dano se aplica en orden de velocidad.
- Defender reduce 50% el dano y tiene 10% de evitarlo del todo.
- La segunda defensa seguida solo tiene 30% de exito; si falla, pierde el turno.
- Atacar da +15 de mana, defender +20, las habilidades 0.
- Una habilidad gasta el turno y tiene enfriamiento: no se puede repetir la
  mejor todos los turnos. Si su efecto se puede dar a otro, el Master elige a
  quien (ver `objetivos_posibles`): en Graal no hay equipos, asi que un
  beneficio se puede regalar, y tambien traicionar.
- El Noble Fantasma cuesta 100 de mana y **no tiene tope**: se puede repetir
  cada vez que se junte. Tenia tope de uno y eso dejaba el mana sin valor en
  cuanto lo soltabas; ver docs/decisiones.md.
- Si un ataque no conecta porque el objetivo ya cayo, el atacante solo suma
  el mana: el ataque no se redirige.
- La batalla termina cuando cae un Servant. Con 2 o mas en pie, solo
  termina si todos quieren; si alguno sigue, se juega un turno especial.

Este modulo es logica pura: no importa discord ni sqlite. Se puede probar y
simular miles de veces sin encender el bot.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from . import sellos
from .clases import multiplicador_triangulo
from .personajes import BONO_DEL_NEGATIVO, Efecto, Habilidad, Objetivo
from .textos import IDIOMA_POR_DEFECTO, idioma_valido, t, turnos as turnos_texto
from .servant import (
    MANA_POR_ATAQUE,
    MANA_POR_DEFENSA,
    MANA_POR_HABILIDAD,
    Servant,
)

# Multiplicadores de dano
VARIACION_DANO = (0.7, 1.3)
MULTIPLICADOR_NOBLE_FANTASMA = 3.0
REDUCCION_DEFENSA = 0.5

# Criticos: el azar que impide que el nivel decida solo el combate.
PROB_CRITICO = 0.15
MULTIPLICADOR_CRITICO = 1.8

# Esquiva por velocidad, sin necesidad de defenderse, sobre la ventaja
# relativa de velocidad, con un tope para que nadie sea intocable.
#
# Calibrado contra el plantel completo de 349 personajes, no contra casos
# sueltos. Al 0.5 la velocidad no valia nada y ningun personaje rapido era
# jugable. Al 0.8 valia demasiado y las clases lentas se hundian: Berserker
# ganaba el 41% de media y Saber el 54%. Al 0.6 las 8 clases quedan entre el
# 47% y el 52%.
FACTOR_ESQUIVA_VELOCIDAD = 0.6
TOPE_ESQUIVA_VELOCIDAD = 0.30

# Cuanto vale en el combate lo que trae la ficha de una habilidad.
#
# Los valores salen traducidos de FGO, que esta calibrado para otro juego: una
# partida larga con seis acciones por turno, donde un +9% de ataque durante 3
# turnos se nota. Aqui una habilidad gasta el turno entero, asi que el mismo
# +9% puede no pagar lo que cuesta. Esta es la perilla para subirlos o bajarlos
# sin reimportar el plantel; medir primero, cambiar despues.
ESCALA_EFECTO = {
    Efecto.ATAQUE: 1.0,
    Efecto.DEFENSA: 1.0,
    Efecto.CRITICO: 1.0,
    Efecto.MANA: 1.0,
    Efecto.CURAR: 1.0,
    Efecto.EVASION: 1.0,
    Efecto.AGUANTAR: 1.0,
    Efecto.BAJAR_ATAQUE: 1.0,
    Efecto.BAJAR_DEFENSA: 1.0,
    Efecto.BAJAR_MANA: 1.0,
}

# Tope de lo que puede acumular un combatiente por efecto, sumando todas sus
# habilidades activas, para que apilar beneficios no vuelva a nadie intocable.
# Un solo bono nunca llega al tope: estan puestos para los personajes que
# tienen dos habilidades del mismo efecto, no para recortar una sola.
TOPE_BONO = {
    Efecto.ATAQUE: 2.00,  # x3 de dano como maximo
    Efecto.DEFENSA: 0.60,  # nunca inmune, ni apilando con defenderse
    Efecto.CRITICO: 0.60,  # con el 15% de base, 75% de criticos
}

# Y el suelo, que hace falta desde que hay efectos negativos: BAJAR_ATAQUE y
# BAJAR_DEFENSA entran como bonos de ataque y de defensa con el valor en
# negativo, asi que sin suelo dos rivales turnandose podrian dejar a alguien
# sin pegar nada. Con -0.60 el peor caso es pegar un 40% y recibir un 60% mas.
#
# No es solo un tope de seguridad: **una bajada de defensa ya llega al suelo
# ella sola** (vale 0.60), asi que apilar una segunda no baja mas. Eso es a
# proposito y se midio: por encima de 0.60 el numero deja de cambiar nada
# (0.60, 0.70 y 0.80 dan el mismo 70.5% en duelo espejo). Si alguna vez se
# quiere que apilar sirva, hay que bajar el suelo **y** medir otra vez.
SUELO_BONO = {
    Efecto.ATAQUE: -0.60,
    Efecto.DEFENSA: -0.60,
}


def prob_esquiva_por_velocidad(velocidad_defensor: int, velocidad_atacante: int) -> float:
    """Probabilidad de esquivar solo por ser mas rapido que el atacante."""
    if velocidad_atacante <= 0 or velocidad_defensor <= velocidad_atacante:
        return 0.0
    ventaja = (velocidad_defensor - velocidad_atacante) / velocidad_atacante
    return min(ventaja * FACTOR_ESQUIVA_VELOCIDAD, TOPE_ESQUIVA_VELOCIDAD)


class Accion(Enum):
    ATACAR = "atacar"
    DEFENDER = "defender"
    HABILIDAD = "habilidad"
    NOBLE_FANTASMA = "noble_fantasma"
    ESPERAR = "esperar"  # quien pidio terminar, durante el turno especial


class Estado(Enum):
    EN_CURSO = "en_curso"
    VOTACION = "votacion"
    TURNO_ESPECIAL = "turno_especial"
    TERMINADA = "terminada"


@dataclass
class Decision:
    accion: Accion
    objetivo: str | None = None
    habilidad: int | None = None


@dataclass
class Cuenta:
    """Una cuenta atras en turnos.

    No descuenta el turno en que nacio, porque usar una habilidad ya gasta ese
    turno: si contara, una habilidad de 1 turno no serviria para nada.
    """

    turnos: int = 0
    turno_creado: int = 0

    @property
    def activa(self) -> bool:
        return self.turnos > 0

    def pasar_turno(self, turno: int) -> None:
        if self.turno_creado < turno:
            self.turnos -= 1


@dataclass
class Bono(Cuenta):
    """Un efecto de habilidad activo sobre un combatiente."""

    efecto: Efecto = Efecto.NINGUNO
    valor: float = 0.0


@dataclass
class Combatiente:
    id: str
    nombre: str
    servant: Servant
    vida: int = 0
    mana: int = -1
    # Cuantos Noble Fantasmas ha soltado. No hay tope: cada uno cuesta su
    # mana otra vez. Era uno por combate, y eso hacia que el mana no valiera
    # nada en cuanto lo soltabas: ver "El Noble Fantasma se puede repetir" en
    # docs/decisiones.md.
    nps_usados: int = 0
    defendio_turno_anterior: bool = False
    uso_habilidad_turno_anterior: bool = False
    _defendiendo: bool = False
    controlado_por_ia: bool = False
    # Efectos de habilidad activos y enfriamientos por numero de habilidad.
    bonos: list[Bono] = field(default_factory=list)
    enfriamientos: dict[int, Cuenta] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.vida:
            self.vida = self.servant.vida_maxima
        if self.mana < 0:
            self.mana = self.servant.rasgo.mana_inicial

    @property
    def vivo(self) -> bool:
        return self.vida > 0

    @property
    def np_usado(self) -> bool:
        """Si ya solto alguno. Para contarlo, no para prohibirlo."""
        return self.nps_usados > 0

    # --- efectos de habilidad ---

    def bono(self, efecto: Efecto) -> float:
        """Lo acumulado de un efecto, con su tope y su suelo."""
        total = sum(b.valor for b in self.bonos if b.efecto is efecto and b.activa)
        tope = TOPE_BONO.get(efecto)
        if tope is not None:
            total = min(total, tope)
        suelo = SUELO_BONO.get(efecto)
        if suelo is not None:
            total = max(total, suelo)
        return total

    def gastar_bono(self, efecto: Efecto) -> float:
        """Usa el primer bono de ese efecto y lo quita. 0 si no habia.

        Es para los que se gastan de uno en uno en vez de durar turnos:
        esquivar un golpe y aguantar un golpe mortal. Si duraran por turnos,
        una EVASION de dos turnos esquivaria los tres ataques de una batalla
        de cuatro, y eso no es una habilidad, es ser intocable.
        """
        for b in self.bonos:
            if b.efecto is efecto and b.activa:
                self.bonos.remove(b)
                return b.valor
        return 0.0

    @property
    def ataque_actual(self) -> int:
        return int(self.servant.ataque * (1 + self.bono(Efecto.ATAQUE)))

    @property
    def prob_critico(self) -> float:
        return PROB_CRITICO + self.bono(Efecto.CRITICO)

    def enfriamiento_restante(self, numero: int) -> int:
        cuenta = self.enfriamientos.get(numero)
        return cuenta.turnos if cuenta and cuenta.activa else 0

    def pasar_turno(self, turno: int) -> None:
        """Descuenta un turno a los bonos y a los enfriamientos."""
        for b in self.bonos:
            b.pasar_turno(turno)
        self.bonos = [b for b in self.bonos if b.activa]
        for cuenta in self.enfriamientos.values():
            cuenta.pasar_turno(turno)

    @property
    def costo_np(self) -> int:
        return self.servant.rasgo.costo_noble_fantasma

    @property
    def puede_defender(self) -> bool:
        return self.servant.rasgo.puede_defender

    @property
    def puede_noble_fantasma(self) -> bool:
        return self.mana >= self.costo_np


class Batalla:
    """Una batalla entre 2 y 4 Masters."""

    TOPE_COMBATIENTES = 4

    def __init__(
        self,
        combatientes: list[Combatiente],
        rng: random.Random | None = None,
        idioma: str = IDIOMA_POR_DEFECTO,
    ) -> None:
        if not 2 <= len(combatientes) <= self.TOPE_COMBATIENTES:
            raise ValueError(
                f"una batalla es de 2 a {self.TOPE_COMBATIENTES} Masters, "
                f"llegaron {len(combatientes)}"
            )
        self.combatientes = {c.id: c for c in combatientes}
        self.rng = rng or random.Random()
        # El idioma del registro. Lo elige la guerra; aqui solo se usa para
        # escribir, nunca para decidir nada del combate.
        self.idioma = idioma_valido(idioma)
        self.turno = 0
        self.estado = Estado.EN_CURSO
        self.registro: list[str] = []
        self.caidos: list[str] = []
        self._siguen_luchando: set[str] = set()
        self._votaciones_hechas = 0

    # --- consultas ---

    def _t(self, clave: str, **datos: object) -> str:
        """Una frase del registro, en el idioma de la batalla."""
        return t(clave, self.idioma, **datos)

    @property
    def vivos(self) -> list[Combatiente]:
        return [c for c in self.combatientes.values() if c.vivo]

    @property
    def terminada(self) -> bool:
        return self.estado is Estado.TERMINADA

    def ganador(self) -> Combatiente | None:
        vivos = self.vivos
        return vivos[0] if self.terminada and len(vivos) == 1 else None

    def rivales_de(self, id_: str) -> list[Combatiente]:
        return [c for c in self.vivos if c.id != id_]

    def acciones_posibles(self, id_: str) -> list[Accion]:
        c = self.combatientes[id_]
        if not c.vivo:
            return []
        if self.estado is Estado.TURNO_ESPECIAL and id_ not in self._siguen_luchando:
            return [Accion.ESPERAR]
        posibles = [Accion.ATACAR]
        if c.puede_defender:
            posibles.append(Accion.DEFENDER)
        if self.habilidades_disponibles(id_):
            posibles.append(Accion.HABILIDAD)
        if c.puede_noble_fantasma:
            posibles.append(Accion.NOBLE_FANTASMA)
        return posibles

    # --- habilidades: que se puede usar y sobre quien ---

    def habilidades_disponibles(self, id_: str) -> list[int]:
        """Numeros (1, 2, 3) de las habilidades que se pueden usar ahora.

        Desbloqueadas por nivel, con nombre (un hueco vacio no es una
        habilidad) y sin enfriamiento pendiente.
        """
        c = self.combatientes[id_]
        if not c.vivo:
            return []
        disponibles = []
        for n in range(1, c.servant.habilidades_desbloqueadas + 1):
            hab = c.servant.habilidad(n)
            if hab and hab.nombre and not c.enfriamiento_restante(n):
                disponibles.append(n)
        return disponibles

    def objetivos_posibles(self, id_: str, numero: int) -> list[Combatiente]:
        """A quien se le puede dar la habilidad `numero`.

        Esto es lo que el Master ve en Discord cuando elige. En Graal no hay
        equipos, asi que un efecto que en FGO iba "a un aliado" aqui va a
        cualquiera de la batalla, incluido uno mismo; el que iba "a otro" va a
        cualquiera menos a uno mismo. Lo que apuntaba a todo un bando pasa a
        apuntar a uno solo: una habilidad afecta siempre a un unico objetivo.
        """
        c = self.combatientes[id_]
        hab = c.servant.habilidad(numero)
        if hab is None or not hab.nombre or not c.vivo:
            return []
        if hab.objetivo is Objetivo.UNO_MISMO:
            return [c]
        if hab.objetivo is Objetivo.OTRO:
            return self.rivales_de(id_)
        return [c] + self.rivales_de(id_)

    # --- el turno ---

    def resolver_turno(self, decisiones: dict[str, Decision]) -> list[str]:
        """Aplica las decisiones de un turno y devuelve el registro de eventos."""
        if self.estado not in (Estado.EN_CURSO, Estado.TURNO_ESPECIAL):
            raise RuntimeError(f"no se puede jugar un turno en estado {self.estado}")

        self.turno += 1
        eventos: list[str] = [self._t("batalla.turno", turno=self.turno)]
        especial = self.estado is Estado.TURNO_ESPECIAL

        actuan = [
            c
            for c in self.vivos
            if not especial or c.id in self._siguen_luchando
        ]

        # 1. Las defensas se declaran en secreto, asi que valen para todo el
        #    turno: se resuelven antes de cualquier dano.
        for c in actuan:
            c._defendiendo = False
            d = decisiones.get(c.id)
            if d is None or d.accion is not Accion.DEFENDER:
                continue
            if not c.puede_defender:
                eventos.append(self._t("batalla.no_sabe_defenderse", nombre=c.nombre))
                continue
            if c.defendio_turno_anterior:
                if self.rng.random() < c.servant.rasgo.prob_segunda_defensa:
                    c._defendiendo = True
                    c.mana += MANA_POR_DEFENSA
                    eventos.append(
                        self._t("batalla.segunda_defensa_lograda", nombre=c.nombre)
                    )
                else:
                    eventos.append(
                        self._t("batalla.segunda_defensa_falla", nombre=c.nombre)
                    )
            else:
                c._defendiendo = True
                c.mana += MANA_POR_DEFENSA
                eventos.append(self._t("batalla.en_guardia", nombre=c.nombre))

        # 2. El resto se resuelve de mas rapido a mas lento. A igual
        #    velocidad el desempate es al azar, nunca por orden de
        #    inscripcion: si no, el primero en entrar tendria ventaja.
        #    Un rasgo puede adelantar a su portador cuando su blanco no se
        #    defiende (los que disparan de lejos).
        def prioridad(c: Combatiente) -> tuple[int, int, float]:
            adelanta = 0
            if c.servant.rasgo.ataca_primero_si_el_blanco_no_defiende:
                d = decisiones.get(c.id)
                blanco = self.combatientes.get(d.objetivo) if d and d.objetivo else None
                if blanco is not None and not blanco._defendiendo:
                    adelanta = 1
            return (adelanta, c.servant.velocidad, self.rng.random())

        orden = sorted(actuan, key=prioridad, reverse=True)
        for atacante in orden:
            if not atacante.vivo:
                continue
            d = decisiones.get(atacante.id)
            if d is None or d.accion in (Accion.DEFENDER, Accion.ESPERAR):
                continue
            eventos.extend(self._aplicar(atacante, d))

        # 3. Cierre del turno: memoria de defensa, cuentas atras de las
        #    habilidades y comprobacion del final.
        for c in self.combatientes.values():
            d = decisiones.get(c.id)
            c.defendio_turno_anterior = bool(d and d.accion is Accion.DEFENDER)
            c.uso_habilidad_turno_anterior = bool(
                d and d.accion is Accion.HABILIDAD
            )
            c._defendiendo = False
            c.pasar_turno(self.turno)

        if especial:
            self.estado = Estado.EN_CURSO
            self._siguen_luchando.clear()

        eventos.extend(self._revisar_final())
        self.registro.extend(eventos)
        return eventos

    def _aplicar(self, atacante: Combatiente, d: Decision) -> list[str]:
        eventos: list[str] = []

        if d.accion is Accion.HABILIDAD:
            return self._usar_habilidad(atacante, d)

        objetivo = self.combatientes.get(d.objetivo) if d.objetivo else None

        # Quien ataca al azar no elige: su demencia decide por el.
        if atacante.servant.rasgo.objetivo_al_azar:
            rivales = self.rivales_de(atacante.id)
            if rivales:
                elegido = self.rng.choice(rivales)
                if objetivo is not elegido:
                    eventos.append(
                        self._t(
                            "batalla.demencia",
                            nombre=atacante.nombre,
                            objetivo=elegido.nombre,
                        )
                    )
                objetivo = elegido

        if d.accion is Accion.NOBLE_FANTASMA:
            if not atacante.puede_noble_fantasma:
                eventos.append(
                    self._t("batalla.np_imposible", nombre=atacante.nombre)
                )
                return eventos
            atacante.mana -= atacante.costo_np
            atacante.nps_usados += 1
            if objetivo is None or not objetivo.vivo:
                eventos.append(
                    self._t("batalla.np_sin_objetivo", nombre=atacante.nombre)
                )
                return eventos
            eventos.append(self._t("batalla.np_liberado", nombre=atacante.nombre))
            eventos.extend(
                self._danar(atacante, objetivo, MULTIPLICADOR_NOBLE_FANTASMA)
            )
            return eventos

        # Accion.ATACAR
        atacante.mana += MANA_POR_ATAQUE + atacante.servant.rasgo.mana_extra_ataque
        if objetivo is None or not objetivo.vivo:
            eventos.append(
                self._t("batalla.ataque_no_conecta", nombre=atacante.nombre)
            )
            return eventos
        eventos.extend(self._danar(atacante, objetivo, 1.0))
        return eventos

    def _usar_habilidad(self, quien: Combatiente, d: Decision) -> list[str]:
        """Usa una habilidad. Gasta el turno, no gasta mana y se enfria."""
        numero = d.habilidad or 1
        hab = quien.servant.habilidad(numero)
        if hab is None or not hab.nombre:
            return [
                self._t(
                    "habilidad.inexistente", nombre=quien.nombre, numero=numero
                )
            ]
        nombre = hab.nombre_para(self.idioma) or self._t(
            "habilidad.sin_numero", numero=numero
        )
        restante = quien.enfriamiento_restante(numero)
        if restante:
            return [
                self._t(
                    "habilidad.enfriando",
                    nombre=quien.nombre,
                    habilidad=nombre,
                    turnos=restante,
                )
            ]

        # Usarla la gasta, conecte o no, igual que el Noble Fantasma, y da su
        # mana, igual que un ataque que no conecta.
        quien.enfriamientos[numero] = Cuenta(
            turnos=hab.turnos_de_enfriamiento, turno_creado=self.turno
        )
        quien.mana += MANA_POR_HABILIDAD
        if not hab.hace_algo:
            return [
                self._t(
                    "habilidad.sin_efecto_aun", nombre=quien.nombre, habilidad=nombre
                )
            ]

        elegido = self.combatientes.get(d.objetivo) if d.objetivo else None
        if elegido is not None and not elegido.vivo:
            return [
                self._t(
                    "habilidad.objetivo_caido",
                    nombre=quien.nombre,
                    habilidad=nombre,
                    objetivo=elegido.nombre,
                )
            ]
        posibles = self.objetivos_posibles(quien.id, numero)
        if elegido is None or elegido not in posibles:
            # Sin eleccion valida, el beneficio se queda en casa; y si la
            # habilidad solo sirve para otro, le toca a uno al azar.
            elegido = quien if quien in posibles else None
            if elegido is None and posibles:
                elegido = self.rng.choice(posibles)
        if elegido is None:
            return [
                self._t(
                    "habilidad.sin_objetivo", nombre=quien.nombre, habilidad=nombre
                )
            ]

        if elegido is quien:
            eventos = [
                self._t("habilidad.usada", nombre=quien.nombre, habilidad=nombre)
            ]
        else:
            eventos = [
                self._t(
                    "habilidad.usada_sobre",
                    nombre=quien.nombre,
                    habilidad=nombre,
                    objetivo=elegido.nombre,
                )
            ]
        eventos.extend(self._aplicar_efecto(hab, elegido))
        return eventos

    def usar_objeto(self, quien: Combatiente, objeto) -> list[str]:
        """Aplica un objeto de combate a quien lo usa. **No gasta el turno.**

        Esa es toda la diferencia con una habilidad, y es la que manda: una
        habilidad gasta el turno y por eso sus numeros son grandes; un objeto
        no gasta nada, asi que sus numeros son mas pequenos (ver
        `objetos.VALOR_POR_EFECTO_DE_OBJETO`) y solo se puede usar uno por
        batalla. Tampoco da mana ni se enfria: no es una accion, es algo que
        pasa **antes** de que elijas tu accion.

        No necesita codigo nuevo: un objeto tiene `efecto`, `valor` y
        `turnos`, que es exactamente lo que `_aplicar_efecto` ya sabia aplicar
        de una habilidad. Quien comprueba que se puede usar es
        `combate.Combate.usar_objeto`, no esto.
        """
        eventos = [
            self._t(
                "combate.objeto_usado",
                nombre=quien.nombre,
                objeto=objeto.nombre_para(self.idioma),
            )
        ]
        eventos.extend(self._aplicar_efecto(objeto, quien))
        self.registro.extend(eventos)
        return eventos

    def usar_sello(self, quien: Combatiente, s: "sellos.Sello") -> list[str]:
        """Gasta un Sello de Comando sobre quien lo usa. **No gasta el turno.**

        Lo mismo que `usar_objeto` en forma, y por lo mismo: no es una accion,
        es algo que pasa antes de elegirla. La diferencia esta fuera de aqui,
        en lo que cuesta: un Sello no se compra y no vuelve, y los dos topes
        (tres por guerra, uno por batalla) viven en el `Master`, porque una
        batalla no sabe de Masters. Los comprueba el Cog antes de llamar.

        Los tres usos son la lista cerrada de `sellos.Uso`. Uno pasa por
        `_aplicar_efecto` (curar es uno de los diez efectos) y los otros dos no
        pueden: llenar la barra no es sumar mana, es ponerla al costo del Noble
        Fantasma, y apagar los enfriamientos no es un bono de nadie.
        """
        nombre = s.nombre_para(self.idioma)
        eventos = [
            self._t("sello.usado", nombre=quien.nombre, sello=nombre)
        ]

        if s.uso is sellos.Uso.MANA:
            antes = quien.mana
            # Se llena **hasta** el costo del Noble Fantasma y no mas: si ya
            # tenia de sobra, el Sello no le regala el siguiente.
            quien.mana = max(quien.mana, quien.costo_np)
            eventos.append(
                self._t(
                    "sello.mana_lleno",
                    nombre=quien.nombre,
                    mana=quien.mana - antes,
                    total=quien.mana,
                )
            )
        elif s.uso is sellos.Uso.ENFRIAMIENTOS:
            quien.enfriamientos.clear()
            eventos.append(self._t("sello.enfriamientos", nombre=quien.nombre))
        else:
            eventos.extend(self._aplicar_efecto(s, quien))

        self.registro.extend(eventos)
        return eventos

    def _aplicar_efecto(self, hab: Habilidad, quien: Combatiente) -> list[str]:
        """Aplica un efecto. Vale para una `Habilidad` y para un `Objeto`.

        Lo unico que mira de `hab` es `efecto`, `valor` y `turnos`, asi que
        los dos encajan sin que haya dos copias de las mismas cinco reglas.
        """
        valor = hab.valor * ESCALA_EFECTO.get(hab.efecto, 1.0)

        if hab.efecto is Efecto.MANA:
            quien.mana += int(valor)
            return [
                self._t(
                    "efecto.mana",
                    nombre=quien.nombre,
                    mana=int(valor),
                    total=quien.mana,
                )
            ]

        # El espejo exacto del de arriba, y por eso tampoco es un bono: el
        # mana es un numero y bajarlo es restar. Lo que quita es lo que
        # retrasa el Noble Fantasma del rival.
        if hab.efecto is Efecto.BAJAR_MANA:
            antes = quien.mana
            quien.mana = max(0, quien.mana - int(valor))
            return [
                self._t(
                    "efecto.bajar_mana",
                    nombre=quien.nombre,
                    mana=antes - quien.mana,
                    total=quien.mana,
                )
            ]

        if hab.efecto is Efecto.CURAR:
            maxima = quien.servant.vida_maxima
            antes = quien.vida
            quien.vida = min(maxima, quien.vida + int(maxima * valor))
            return [
                self._t(
                    "efecto.curar",
                    nombre=quien.nombre,
                    vida=quien.vida - antes,
                    actual=quien.vida,
                    maxima=maxima,
                )
            ]

        # Los negativos no necesitan reglas nuevas: son el mismo bono de
        # ataque o de defensa con el valor en negativo, puesto sobre el otro.
        # Quien se lo lleva ya lo eligio `_usar_habilidad`, que para estas
        # habilidades solo ofrece rivales (`Objetivo.OTRO`).
        if hab.efecto in BONO_DEL_NEGATIVO:
            quien.bonos.append(
                Bono(
                    turnos=hab.turnos,
                    turno_creado=self.turno,
                    efecto=BONO_DEL_NEGATIVO[hab.efecto],
                    valor=-valor,
                )
            )
            clave = (
                "efecto.bajar_ataque"
                if hab.efecto is Efecto.BAJAR_ATAQUE
                else "efecto.bajar_defensa"
            )
            return [
                self._t(
                    clave,
                    nombre=quien.nombre,
                    porcentaje=f"{valor * 100:.0f}",
                    duracion=turnos_texto(hab.turnos, self.idioma),
                )
            ]

        quien.bonos.append(
            Bono(
                turnos=hab.turnos,
                turno_creado=self.turno,
                efecto=hab.efecto,
                valor=valor,
            )
        )
        duracion = turnos_texto(hab.turnos, self.idioma)
        if hab.efecto is Efecto.EVASION:
            return [
                self._t(
                    "efecto.evasion", nombre=quien.nombre, duracion=duracion
                )
            ]
        if hab.efecto is Efecto.AGUANTAR:
            return [
                self._t(
                    "efecto.aguantar",
                    nombre=quien.nombre,
                    porcentaje=f"{valor * 100:.0f}",
                    duracion=duracion,
                )
            ]
        if hab.efecto is Efecto.ATAQUE:
            return [
                self._t(
                    "efecto.ataque",
                    nombre=quien.nombre,
                    factor=f"{1 + valor:.2g}",
                    duracion=duracion,
                )
            ]
        if hab.efecto is Efecto.DEFENSA:
            return [
                self._t(
                    "efecto.defensa",
                    nombre=quien.nombre,
                    porcentaje=f"{valor * 100:.0f}",
                    duracion=duracion,
                )
            ]
        return [
            self._t(
                "efecto.critico",
                nombre=quien.nombre,
                puntos=f"{valor * 100:.0f}",
                duracion=duracion,
            )
        ]

    def _danar(
        self, atacante: Combatiente, objetivo: Combatiente, multiplicador: float
    ) -> list[str]:
        eventos: list[str] = []
        triangulo = multiplicador_triangulo(
            atacante.servant.clase, objetivo.servant.clase
        )
        # Esquiva por velocidad: se juega antes que nada, defendiendose o no.
        esquiva = prob_esquiva_por_velocidad(
            objetivo.servant.velocidad, atacante.servant.velocidad
        )
        if esquiva and self.rng.random() < esquiva:
            eventos.append(
                self._t("batalla.esquiva_velocidad", nombre=objetivo.nombre)
            )
            return eventos

        # Esquiva de habilidad: no es una probabilidad, es un golpe que no te
        # toca. Se juega despues de la de velocidad para no gastarla cuando ya
        # te habias librado, y antes del dano porque no deja nada que reducir.
        if objetivo.gastar_bono(Efecto.EVASION):
            eventos.append(
                self._t("batalla.esquiva_habilidad", nombre=objetivo.nombre)
            )
            return eventos

        base = atacante.ataque_actual * multiplicador * triangulo
        dano = int(base * self.rng.uniform(*VARIACION_DANO))
        if self.rng.random() < atacante.prob_critico:
            dano = int(dano * MULTIPLICADOR_CRITICO)
            eventos.append(self._t("batalla.critico"))
        if triangulo > 1:
            eventos.append(
                self._t(
                    "batalla.ventaja",
                    clase_atacante=atacante.servant.clase.value,
                    clase_objetivo=objetivo.servant.clase.value,
                )
            )
        elif triangulo < 1:
            eventos.append(
                self._t(
                    "batalla.desventaja",
                    clase_atacante=atacante.servant.clase.value,
                    clase_objetivo=objetivo.servant.clase.value,
                )
            )

        if objetivo._defendiendo:
            if self.rng.random() < objetivo.servant.rasgo.prob_evasion:
                eventos.append(
                    self._t("batalla.evita_golpe", nombre=objetivo.nombre)
                )
                return eventos
            dano = int(dano * REDUCCION_DEFENSA)
            eventos.append(self._t("batalla.bloquea", nombre=objetivo.nombre))

        escudo = objetivo.bono(Efecto.DEFENSA)
        if escudo:
            dano = int(dano * (1 - escudo))

        objetivo.vida = max(0, objetivo.vida - dano)
        eventos.append(
            self._t(
                "batalla.dano",
                atacante=atacante.nombre,
                dano=dano,
                objetivo=objetivo.nombre,
                vida=objetivo.vida,
                maxima=objetivo.servant.vida_maxima,
            )
        )
        # Aguantar: el golpe se cuenta entero, se lee en el registro, y
        # despues te levanta. Se gasta solo cuando te salva: mientras no te
        # tumben, sigue puesto.
        aguante = objetivo.gastar_bono(Efecto.AGUANTAR) if not objetivo.vivo else 0.0
        if aguante:
            objetivo.vida = max(1, int(objetivo.servant.vida_maxima * aguante))
            eventos.append(
                self._t(
                    "batalla.aguanta",
                    nombre=objetivo.nombre,
                    vida=objetivo.vida,
                    maxima=objetivo.servant.vida_maxima,
                )
            )
        if not objetivo.vivo:
            eventos.append(self._t("batalla.cae", nombre=objetivo.nombre))
            self.caidos.append(objetivo.id)
        return eventos

    def _revisar_final(self) -> list[str]:
        vivos = self.vivos
        if len(vivos) <= 1:
            self.estado = Estado.TERMINADA
            if vivos:
                return [
                    self._t("batalla.fin_con_ganador", nombre=vivos[0].nombre)
                ]
            return [self._t("batalla.fin_sin_nadie")]
        # Si cayo alguien y quedan 2 o mas en pie, se abre la votacion.
        if self.estado is Estado.EN_CURSO and len(self.caidos) > self._votaciones_hechas:
            self.estado = Estado.VOTACION
            return [
                self._t(
                    "batalla.votacion",
                    nombres=", ".join(c.nombre for c in vivos),
                )
            ]
        return []

    # --- votacion y turno especial ---

    def registrar_votos(self, votos: dict[str, bool]) -> list[str]:
        """`True` = continuar la batalla, `False` = terminarla."""
        if self.estado is not Estado.VOTACION:
            raise RuntimeError("no hay una votacion abierta")
        self._votaciones_hechas += 1
        siguen = {id_ for id_, v in votos.items() if v and self.combatientes[id_].vivo}

        if not siguen:
            self.estado = Estado.TERMINADA
            eventos = [self._t("batalla.todos_terminan")]
            self.registro.extend(eventos)
            return eventos

        self._siguen_luchando = siguen
        self.estado = Estado.TURNO_ESPECIAL
        nombres = ", ".join(self.combatientes[i].nombre for i in siguen)
        esperan = [c.nombre for c in self.vivos if c.id not in siguen]
        eventos = [self._t("batalla.siguen_luchando", nombres=nombres)]
        if esperan:
            eventos.append(
                self._t("batalla.esperan", nombres=", ".join(esperan))
            )
        self.registro.extend(eventos)
        return eventos
