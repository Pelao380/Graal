"""La guerra: lobby, dias, fases y formacion de batallas.

Logica pura. Los plazos se expresan en segundos y quien los vigila es el bot,
que los guarda en la base de datos para que un reinicio no pierda la guerra.

Los cupos que no llena una persona los puede llenar la IA, para poder jugar
sin esperar a seis mas. Esa guerra se juega igual, pero **no entrega el
Grial**: para eso hacen falta al menos 4 personas de verdad.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from . import sellos as sellos_mod
from .npc import COMBATES_POR_DIA, pelear, vida_inicial
from .objetos import Inventario
from .servant import Servant
from .textos import IDIOMA_POR_DEFECTO, idioma_valido, t

MINIMO_MASTERS = 7
# Una guerra son exactamente 7 Masters: hay 7 cupos de clase y el Ruler,
# cuando aparece, ocupa uno de ellos.
MAXIMO_MASTERS = 7

# Personas de verdad que hacen falta para que la guerra entregue el Grial. Por
# debajo de eso se juega igual, pero el premio no cuenta: con uno o dos
# humanos y el resto bots, ganar diria mas de la IA que del jugador.
MINIMO_HUMANOS_PARA_GRIAL = 4

# Y cuantas hacen falta si la guerra se acabo porque los demas **se
# retiraron** en vez de caer: mas de 5, o sea 6 o 7. El minimo normal son 4, y
# con 4 se podrian poner de acuerdo tres personas para coronar a la cuarta
# gratis. Pidiendo 6 hay que juntar a seis personas de verdad para repartirse
# un grial, que ya es mas trabajo que jugar la guerra. Lo decidio Cristopher
# el 2026-11-10, y es lo que separa "ganar porque se fueron" de "farmear".
MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA = 6

# Cuantos combates NPC pelea cada bot al dia. Los bots entrenan como un
# jugador aplicado: si no lo hicieran se quedarian al nivel 1 y una guerra
# contra bots no tendria ninguna gracia a partir del dia 2.
COMBATES_NPC_DE_LOS_BOTS = COMBATES_POR_DIA
TOPE_POR_BATALLA = 4
DERROTAS_PARA_ELIMINAR = 2
SELLOS_POR_MASTER = 3
# Cuantos se pueden gastar en una misma batalla; el otro tope vive aqui arriba.
SELLOS_POR_BATALLA = sellos_mod.SELLOS_POR_BATALLA

# Opciones de ventana de preparacion, en segundos.
TIEMPOS_PREPARACION = {"30m": 30 * 60, "1h": 60 * 60, "24h": 24 * 60 * 60}

SEGUNDOS_BOTON_LISTO = 5 * 60
SEGUNDOS_POR_TURNO = 5 * 60


class Fase(Enum):
    LOBBY = "lobby"
    PREPARACION = "preparacion"
    FORMACION = "formacion"
    LISTOS = "listos"
    BATALLA = "batalla"
    CIERRE = "cierre"
    TERMINADA = "terminada"


@dataclass
class Master:
    id: str
    nombre: str
    servant: Servant | None = None
    derrotas: int = 0
    # Los Sellos de Comando que le quedan **para toda la guerra**. Este si se
    # guarda en la base de datos, que es la mitad que importa: un reinicio no
    # puede devolverte un Sello gastado.
    sellos: int = SELLOS_POR_MASTER
    # Cuantos ha gastado en la batalla de hoy. Se reinicia con el dia y **no**
    # se guarda, igual que `inventario.usados_en_la_batalla`: una batalla dura
    # minutos y el tope de la guerra, que es el que cuenta, si esta a salvo.
    sellos_en_la_batalla: int = 0
    # Se reinician cada dia
    intentos_npc: int = 0
    derrotas_npc: int = 0
    objetivo: str | None = None
    # Ha dicho que ya hizo todo lo que queria hacer hoy. Solo sirve para que
    # el creador pueda cerrar el dia antes de que se agote la ventana: ver
    # `Guerra.faltan_por_estar_listos`.
    listo: bool = False
    # El idioma en el que se le habla: el de su guerra.
    idioma: str = IDIOMA_POR_DEFECTO
    # Un cupo que llena la IA porque no habia gente. Juega igual que los
    # demas, pero no cuenta para el Grial.
    es_bot: bool = False
    # Se rindio y se salio de la guerra. Cuenta como eliminado (ver
    # `eliminado`) y por eso no hizo falta tocar nada mas: el que se rinde
    # deja de estar en `activos`, asi que no entra en batallas, no se le
    # espera para cerrar el dia y no puede ganar. No se deshace.
    retirado: bool = False
    # Los Masters cuyo Servant ha visto, porque peleo contra el. Al suyo no
    # hace falta apuntarlo: `conoce` ya lo da por sabido.
    conocidos: set[str] = field(default_factory=set)

    # Lo que lleva encima. Los objetos los suelta ganar un combate de
    # entrenamiento, y duran toda la guerra: por eso van en el Master y no en
    # la batalla, y por eso se guardan en la base de datos.
    inventario: Inventario = field(default_factory=Inventario)

    # El oro de esta guerra, para la tienda. Lo da ganar NPC y ganar batallas.
    # **Vive y muere con la guerra**: esta aqui dentro y no en una cuenta
    # aparte precisamente por eso. Lo que si sobrevive son los griales, que van
    # en `tienda.Cuenta` porque son de la persona y no de la guerra.
    oro: int = 0

    # El registro de la ultima batalla que peleo, y de que dia. No se
    # publica en el canal porque las frases nombran las habilidades, y el
    # nombre de una habilidad delata al Servant: "Throne of Quirinus" solo lo
    # tiene Romulus=Quirinus. Lo ve en su menu quien estuvo delante.
    ultimo_registro: list[str] = field(default_factory=list)
    ultimo_registro_dia: int = 0

    def conoce(self, id_: str) -> bool:
        """Si sabe que Servant lleva ese Master.

        Al principio nadie sabe nada de nadie: los Servants de los demas no
        se anuncian. Se aprenden peleando, y asi declarar un ataque es una
        apuesta a ciegas la primera vez.
        """
        return id_ == self.id or id_ in self.conocidos

    @property
    def eliminado(self) -> bool:
        """Fuera de la guerra, por las dos vias que hay: perder o rendirse.

        Que rendirse pase por aqui es lo que hace que no haya una regla nueva:
        todo lo que ya preguntaba "esta fuera" (formar batallas, a quien se
        espera, quien puede ganar) lo pregunta igual.
        """
        return self.derrotas >= DERROTAS_PARA_ELIMINAR or self.retirado

    @property
    def puede_usar_sello(self) -> bool:
        """Si le queda alguno **y** no gasto el de esta batalla.

        Los dos topes juntos, que es como se preguntan siempre. Vive aqui y no
        en el combate porque los Sellos son del Master y duran la guerra; una
        batalla no sabe de Masters, igual que no sabe de inventarios.
        """
        return self.sellos > 0 and self.sellos_en_la_batalla < SELLOS_POR_BATALLA

    def gastar_sello(self) -> None:
        """Descuenta uno de los dos contadores de una vez. Nunca por separado.

        Si alguien bajara solo `sellos`, el tope por batalla no se enteraria y
        se podrian gastar los tres en un turno; si bajara solo el otro, los
        Sellos serian infinitos.
        """
        if not self.puede_usar_sello:
            raise RuntimeError(t("sello.no_puede", self.idioma, nombre=self.nombre))
        self.sellos -= 1
        self.sellos_en_la_batalla += 1

    @property
    def intentos_npc_restantes(self) -> int:
        return COMBATES_POR_DIA - self.intentos_npc

    def vida_para_la_batalla(self) -> int:
        if self.servant is None:
            raise RuntimeError(t("guerra.sin_servant", self.idioma, nombre=self.nombre))
        return vida_inicial(self.servant, self.derrotas_npc)

    def nuevo_dia(self) -> None:
        self.intentos_npc = 0
        self.derrotas_npc = 0
        self.objetivo = None
        # Estar listo vale para un dia: al dia siguiente hay cosas nuevas que
        # hacer y hay que volver a decirlo. A los bots los vuelve a marcar
        # `abrir_dia`, que es donde hacen lo suyo.
        self.listo = False
        # Los objetos **no** se pierden con el dia: duran la guerra. Lo que se
        # reinicia es cuantos usaste en la batalla, que es un tope por batalla.
        self.inventario.nueva_batalla()
        # Y lo mismo con los Sellos: los que te quedan son de la guerra, el
        # tope de uno por batalla es de hoy.
        self.sellos_en_la_batalla = 0


@dataclass
class Guerra:
    id: str
    canal_id: str
    preparacion: str = "1h"
    maximo_dia_segundos: int = 24 * 60 * 60
    dia: int = 0
    fase: Fase = Fase.LOBBY
    masters: dict[str, Master] = field(default_factory=dict)
    orden_declaraciones: list[str] = field(default_factory=list)
    # Los 7 Servants que salieron sorteados y todavia no tienen Master. El
    # sorteo se hace al empezar la guerra, pero el reparto lo pide cada Master
    # cuando quiere: ver `invocar_para`.
    sin_repartir: list[Servant] = field(default_factory=list)
    # Quien abrio la guerra: el unico que puede empezarla con bots.
    creador_id: str = ""
    # El idioma de la guerra: en el que se escribe en el canal y en el que se
    # narra la batalla. Lo elige quien la crea.
    idioma: str = IDIOMA_POR_DEFECTO
    # El dado de la guerra, el que usa la IA al abrir el dia. Se puede pasar
    # uno con semilla para que el simulador repita una partida igual.
    rng: random.Random = field(default_factory=random.Random)
    # El reloj de la guerra, en segundos. Se puede cambiar por uno de mentira
    # para probar los plazos sin esperar una hora.
    reloj: Callable[[], float] = time.time
    # Cuando se agota la ventana de preparacion del dia en curso. Lo pone
    # `abrir_dia`, asi que ningun dia puede quedarse sin plazo.
    vence_preparacion: float = 0.0
    # La cerraron a mano en vez de acabarse jugando: ver `cancelar`. No se
    # guarda en la base de datos y no hace falta, porque una guerra cancelada
    # queda marcada como terminada y no se vuelve a cargar.
    cancelada: bool = False
    # Se acabo porque el ultimo rival se rindio, no porque cayera. La guerra
    # tiene ganador igual, pero **no paga Grial**: sin esto, cuatro personas
    # de acuerdo se repartirian un grial por guerra rindiendose el dia 1, que
    # es justo lo que `gana_el_grial` existe para impedir. Tampoco se guarda,
    # por lo mismo que `cancelada`.
    acabo_por_retirada: bool = False

    def __post_init__(self) -> None:
        self.idioma = idioma_valido(self.idioma)

    # --- lobby ---

    @property
    def activos(self) -> list[Master]:
        return [m for m in self.masters.values() if not m.eliminado]

    @property
    def humanos(self) -> list[Master]:
        return [m for m in self.masters.values() if not m.es_bot]

    @property
    def bots(self) -> list[Master]:
        return [m for m in self.masters.values() if m.es_bot]

    @property
    def otorga_grial(self) -> bool:
        """Si esta guerra entrega el Grial al que quede en pie.

        Lo decide cuanta gente de verdad juega, no cuantos cupos hay llenos.
        """
        return len(self.humanos) >= MINIMO_HUMANOS_PARA_GRIAL

    @property
    def puede_empezar(self) -> bool:
        return self.fase is Fase.LOBBY and len(self.masters) >= MINIMO_MASTERS

    @property
    def cupos_libres(self) -> int:
        return MAXIMO_MASTERS - len(self.masters)

    @property
    def puede_empezar_con_bots(self) -> bool:
        """Con al menos una persona, los cupos que falten los llena la IA."""
        return self.fase is Fase.LOBBY and len(self.humanos) >= 1

    def inscribir(self, id_: str, nombre: str) -> Master:
        if self.fase is not Fase.LOBBY:
            raise RuntimeError(t("guerra.ya_empezo", self.idioma))
        if id_ in self.masters:
            raise ValueError(t("guerra.ya_inscrito", self.idioma))
        if len(self.masters) >= MAXIMO_MASTERS:
            raise ValueError(
                t("guerra.llena", self.idioma, maximo=MAXIMO_MASTERS)
            )
        m = Master(id=id_, nombre=nombre, idioma=self.idioma)
        self.masters[id_] = m
        if not self.creador_id:
            self.creador_id = id_
        return m

    def rellenar_con_bots(self) -> list[Master]:
        """Llena los cupos que falten con Masters que juega la IA.

        Hace falta al menos una persona: una guerra de siete bots no la
        miraria nadie. Devuelve los bots que entraron, que puede ser ninguno
        si el lobby ya estaba lleno.
        """
        if self.fase is not Fase.LOBBY:
            raise RuntimeError(t("guerra.ya_empezo", self.idioma))
        if not self.humanos:
            raise RuntimeError(t("guerra.sin_humanos", self.idioma))
        nuevos: list[Master] = []
        for _ in range(self.cupos_libres):
            numero = len(self.bots) + 1
            m = Master(
                id=f"bot:{numero}",
                nombre=t("guerra.nombre_bot", self.idioma, numero=numero),
                idioma=self.idioma,
                es_bot=True,
            )
            self.masters[m.id] = m
            nuevos.append(m)
        return nuevos

    def empezar(self, servants: list[Servant]) -> None:
        """Arranca la guerra con el sorteo hecho, pero sin repartir.

        `servants` sale de `invocacion.invocar(catalogo, rng)`: son los 7
        cupos de clase, ya mezclados. **No se asignan aqui.** Quedan en
        `sin_repartir` y cada Master invoca el suyo cuando quiera a lo largo
        del dia 1; al que no lo haga, `formar_batallas` se lo invoca antes de
        armar las batallas, porque nadie pelea sin Servant.

        El sorteo tiene que pasar aqui y no en cada invocacion: los 7 cupos de
        clase y la tirada del Ruler son una propiedad de la guerra entera, no
        de cada Master. Si cada uno sorteara el suyo por separado saldrian
        clases repetidas.
        """
        if not self.puede_empezar:
            faltan = MINIMO_MASTERS - len(self.masters)
            raise RuntimeError(t("guerra.faltan_masters", self.idioma, faltan=faltan))
        if len(servants) < len(self.masters):
            raise ValueError(
                f"hacen falta {len(self.masters)} Servants y llegaron "
                f"{len(servants)}"
            )
        self.sin_repartir = list(servants)
        self.dia = 1
        self.fase = Fase.PREPARACION
        self.abrir_dia()

    # --- invocacion ---

    def invocar_para(self, id_: str, rng: random.Random | None = None) -> Servant:
        """Le reparte su Servant a un Master, cuando el lo pide.

        Sale uno al azar de los que quedan sin repartir. La lista ya venia
        mezclada del sorteo, pero se vuelve a tirar aqui para que el orden en
        que cada uno invoque no decida nada: si fuera por orden, invocar
        primero seria una jugada, y la invocacion no deberia ser una jugada.
        """
        m = self.masters[id_]
        if self.fase is Fase.LOBBY:
            raise RuntimeError(t("guerra.todavia_no_empezo", self.idioma))
        if m.servant is not None:
            raise RuntimeError(t("guerra.ya_invocaste", self.idioma))
        if not self.sin_repartir:
            raise RuntimeError(t("guerra.sin_servants_libres", self.idioma))
        rng = rng or self.rng
        s = self.sin_repartir.pop(rng.randrange(len(self.sin_repartir)))
        m.servant = s
        m.sellos = s.rasgo.sellos
        return s

    @property
    def faltan_por_estar_listos(self) -> list[Master]:
        """Las personas vivas que todavia no han dicho que acabaron el dia.

        Es lo que impide que el creador cierre el dia antes de que los demas
        entrenen. Medido: entrenar sus 4 combates y cerrar enseguida le
        doblaba las victorias (del 11.5% al 22.9%) y dejaba a los otros tres
        en el 2.7%, porque se quedaban sin entrenar. Los bots no cuentan: ya
        hicieron lo suyo al abrirse el dia.
        """
        return [m for m in self.activos if not m.es_bot and not m.listo]

    @property
    def sin_invocar(self) -> list[Master]:
        """Los que siguen en pie y todavia no han invocado."""
        return [m for m in self.activos if m.servant is None]

    def invocar_a_los_que_falten(
        self, rng: random.Random | None = None
    ) -> list[Master]:
        """Completa el ritual por los que no lo pidieron.

        Es el plazo del dia 1: quien no invoca, acaba invocando igual. No
        invocar no puede ser una forma de no pelear, que es la puerta que ya
        cerramos con las declaraciones de ataque.
        """
        rng = rng or self.rng
        faltaban = self.sin_invocar
        for m in faltaban:
            self.invocar_para(m.id, rng)
        return faltaban

    @property
    def segundos_preparacion(self) -> int:
        return TIEMPOS_PREPARACION[self.preparacion]

    @property
    def segundos_para_cerrar(self) -> float:
        """Lo que le queda al dia, en segundos. Nunca negativo."""
        return max(0.0, self.vence_preparacion - self.reloj())

    @property
    def plazo_cumplido(self) -> bool:
        """Si al dia en curso ya se le agoto la ventana de preparacion.

        Esto cierra el dia **sin esperar a nadie**, al contrario que el boton
        del creador: para eso existe el plazo. Quien no entreno tuvo la
        ventana entera, asi que no se le quita nada.
        """
        return (
            self.fase is Fase.PREPARACION
            and not self.terminada
            and self.segundos_para_cerrar <= 0
        )

    # --- declaracion de ataques ---

    def declarar_ataque(self, atacante: str, objetivo: str) -> None:
        if self.fase is not Fase.PREPARACION:
            raise RuntimeError(t("guerra.fuera_de_preparacion", self.idioma))
        if atacante == objetivo:
            raise ValueError(t("guerra.no_a_ti_mismo", self.idioma))
        for id_ in (atacante, objetivo):
            m = self.masters.get(id_)
            if m is None or m.eliminado:
                raise ValueError(t("guerra.master_fuera", self.idioma))
        # Al objetivo no se le exige Servant: si todavia no invoco, lo tendra
        # antes de la batalla. Al atacante si, porque sin Servant no hay con
        # que atacar.
        if self.masters[atacante].servant is None:
            raise RuntimeError(t("guerra.invoca_primero", self.idioma))
        self.masters[atacante].objetivo = objetivo
        if atacante in self.orden_declaraciones:
            self.orden_declaraciones.remove(atacante)
        self.orden_declaraciones.append(atacante)

    def declarar_ataque_de_bot(
        self, id_: str, rng: random.Random | None = None
    ) -> str | None:
        """Declara el ataque de un bot: a uno al azar de los que siguen en pie.

        Los bots siempre atacan: si descansaran, una guerra con pocos humanos
        no avanzaria nunca. A quien atacan es al azar a proposito, porque
        elegir bien es jugar por el jugador (ver "Que tan bien juega la IA
        sustituta" en docs/puntos-abiertos.md).
        """
        m = self.masters[id_]
        if m.eliminado or m.objetivo is not None:
            return None
        rivales = [o for o in self.activos if o.id != m.id]
        if not rivales:
            return None
        objetivo = (rng or random.Random()).choice(rivales).id
        self.declarar_ataque(m.id, objetivo)
        return objetivo

    def declarar_ataques_de_los_bots(self, rng: random.Random | None = None) -> None:
        """Lo mismo para todos los bots de la guerra.

        Da igual cuando se llame: desde que `formar_batallas` sortea quien se
        queda fuera, el orden de declaracion no decide nada.
        """
        rng = rng or random.Random()
        for m in self.bots:
            self.declarar_ataque_de_bot(m.id, rng)

    def entrenar_a_los_bots(self, rng: random.Random | None = None) -> None:
        """Los bots pelean sus combates NPC del dia."""
        rng = rng or random.Random()
        for m in self.bots:
            if m.servant is None or m.eliminado:
                continue
            while m.intentos_npc < COMBATES_NPC_DE_LOS_BOTS:
                resultado = pelear(
                    m.servant, m.intentos_npc, self.dia, rng, idioma=self.idioma
                )
                m.intentos_npc += 1
                if resultado.gano:
                    m.servant.ganar_xp(resultado.xp)
                else:
                    m.derrotas_npc += 1

    def abrir_dia(self, rng: random.Random | None = None) -> None:
        """Todo lo que hace la IA al empezar un dia de preparacion.

        La llaman `empezar` (dia 1) y `siguiente_dia` (el resto), no la capa
        de Discord, y eso es a proposito. Si el dia de los bots dependiera de
        que alguien escriba un comando, el dia que el jugador no apareciera
        sus rivales se quedarian al nivel 1, y una guerra de uno contra seis
        bots se gana sola. Asi no hay forma de que se les olvide.

        Invocan, entrenan y declaran, en ese orden, que es con el que se midio
        que una persona sola contra seis bots gana 1 de cada 7. La IA no
        espera para invocar: elegir el momento es una decision de jugador y
        aqui no hay nada que decidir.
        """
        rng = rng or self.rng
        # El plazo se pone aqui por lo mismo que lo demas: si lo pusiera quien
        # abre el dia, un dia podria quedarse sin plazo y la guerra se pararia
        # para siempre esperando a alguien.
        self.vence_preparacion = self.reloj() + self.segundos_preparacion
        for m in self.bots:
            if m.servant is None and not m.eliminado:
                self.invocar_para(m.id, rng)
        self.entrenar_a_los_bots(rng)
        self.declarar_ataques_de_los_bots(rng)
        # Ya hicieron todo lo suyo, asi que nunca hacen esperar a nadie.
        for m in self.bots:
            m.listo = True

    def formar_batallas(
        self, rng: random.Random | None = None
    ) -> tuple[list[list[str]], list[str]]:
        """Agrupa a los Masters unidos por ataques, con tope de 4.

        Devuelve los grupos de batalla y los atacantes que al final descansan
        porque no cupieron en ninguna.

        Dos reglas que no son evidentes y que vienen de medir:

        **El orden de declaracion no decide nada: se sortea.** Antes entraban
        los primeros 4 de cada cadena por orden de declaracion, y eso hacia
        que declarar tarde fuera la mejor jugada del dia, porque al que se
        queda fuera le toca descansar y descansar no arriesga nada. Medido con
        guerras enteras, al mismo jugador le cambiaba la tasa de victorias del
        10% al 27% segun si declaraba antes o despues que los demas. Ahora
        quien se queda fuera es cuestion de suerte, no de reloj.

        **Declarar un ataque es comprometerse a pelear.** Al que no cabe en su
        cadena se le busca otro rival: primero alguien libre, y si no hay,
        otro atacante que tampoco cupo. Solo descansa si no queda nadie con
        quien pelear. Antes "redirigir o descansar" era decision suya, que es
        la misma puerta por otro lado.

        **Lo primero que hace es cerrar las invocaciones que falten.** Nadie
        pelea sin Servant, y esperar no puede servir para librarse del dia: es
        la misma puerta otra vez. Por eso el plazo del dia 1 vive aqui y no en
        `siguiente_dia`, que correria despues de las batallas.
        """
        rng = rng or random.Random()
        self.invocar_a_los_que_falten(rng)
        padre = {m.id: m.id for m in self.activos}
        tamano = {m.id: 1 for m in self.activos}
        excluidos: list[str] = []

        def raiz(x: str) -> str:
            while padre[x] != x:
                padre[x] = padre[padre[x]]
                x = padre[x]
            return x

        declarantes = [
            a
            for a in self.orden_declaraciones
            if a in padre and self.masters[a].objetivo is not None
        ]
        rng.shuffle(declarantes)
        for atacante in declarantes:
            objetivo = self.masters[atacante].objetivo
            if objetivo not in padre:
                continue
            ra, ro = raiz(atacante), raiz(objetivo)
            if ra == ro:
                continue
            if tamano[ra] + tamano[ro] > TOPE_POR_BATALLA:
                excluidos.append(atacante)
                continue
            if tamano[ra] < tamano[ro]:
                ra, ro = ro, ra
            padre[ro] = ra
            tamano[ra] += tamano[ro]

        grupos: dict[str, list[str]] = {}
        for id_ in padre:
            grupos.setdefault(raiz(id_), []).append(id_)
        batallas = [sorted(g) for g in grupos.values() if len(g) >= 2]

        batallas.extend(self._redirigir(excluidos, batallas, rng))
        en_batalla = {id_ for grupo in batallas for id_ in grupo}
        descansan = [a for a in excluidos if a not in en_batalla]
        return sorted(batallas), descansan

    def _redirigir(
        self,
        excluidos: list[str],
        batallas: list[list[str]],
        rng: random.Random,
    ) -> list[list[str]]:
        """Le busca pelea a cada atacante que no cupo en su cadena.

        Primero contra un Master libre, que es el que no ataca ni es atacado;
        si no hay ninguno, contra otro atacante que tampoco cupo. El libre no
        eligio pelear, pero las reglas ya decian que si alguien lo ataca el
        combate se inicia igual.
        """
        en_batalla = {id_ for grupo in batallas for id_ in grupo}
        libres = [
            m.id
            for m in self.activos
            if m.id not in en_batalla and m.id not in excluidos
        ]
        rng.shuffle(libres)
        # Los que ya pelean por otro lado no necesitan que se les busque
        # rival: su ataque no conecto, pero el dia no se lo pierden.
        pendientes = [a for a in excluidos if a not in en_batalla]
        rng.shuffle(pendientes)

        nuevas: list[list[str]] = []
        while pendientes:
            atacante = pendientes.pop()
            if libres:
                objetivo = libres.pop()
            elif pendientes:
                objetivo = pendientes.pop()
            else:
                break
            self.masters[atacante].objetivo = objetivo
            nuevas.append(sorted([atacante, objetivo]))
        return nuevas

    def descansan(self, batallas: list[list[str]]) -> list[str]:
        en_batalla = {id_ for grupo in batallas for id_ in grupo}
        return [m.id for m in self.activos if m.id not in en_batalla]

    # --- cierre del dia y de la guerra ---

    def registrar_derrota(self, id_: str) -> bool:
        """Suma una derrota contra jugadores. Devuelve `True` si queda eliminado."""
        m = self.masters[id_]
        m.derrotas += 1
        return m.eliminado

    def rendirse(self, id_: str) -> bool:
        """Saca a alguien de la guerra por su propia voluntad.

        Devuelve `True` si con eso la guerra se acabo. No es cancelar: la
        guerra sigue para los demas, y si solo queda uno, ese **gana**. Lo que
        no da es el Grial: ver `acabo_por_retirada` y `gana_el_grial`.

        No se deshace, y por eso el boton pide pulsarlo dos veces.
        """
        m = self.masters[id_]
        # Devuelve False, no `terminada`: lo que contesta es "esta retirada
        # acabo la guerra", y quien ya estaba fuera no acaba nada. Devolver
        # `terminada` hacia que rendirse otra vez despues del final volviera
        # a pagar el Grial, porque el que paga mira esta respuesta. Lo
        # encontro una prueba.
        if m.eliminado or self.terminada:
            return False
        m.retirado = True
        m.listo = True  # no se le espera para cerrar el dia de hoy
        m.objetivo = None
        if len(self.activos) <= 1:
            # El ultimo rival se fue en vez de caer. La guerra se acabo y el
            # que queda gana, pero esto es lo que impide que cuatro amigos se
            # repartan griales rindiendose: ver `gana_el_grial`.
            self.acabo_por_retirada = True
            self.fase = Fase.TERMINADA
            self.vence_preparacion = 0.0
            return True
        return False

    def siguiente_dia(self) -> None:
        for m in self.masters.values():
            m.nuevo_dia()
        self.orden_declaraciones.clear()
        if len(self.activos) <= 1:
            self.fase = Fase.TERMINADA
            return
        self.dia += 1
        self.fase = Fase.PREPARACION
        self.abrir_dia()

    def cancelar(self) -> None:
        """Cierra la guerra a mano, sin ganador y sin Grial.

        No es lo mismo que acabarla: una guerra que se acaba jugando deja a
        uno en pie y ese gana. Esta se corta a la mitad porque se atasco, se
        abandono o se abrio por error, asi que **nadie gana**, ni aunque
        quedara uno solo vivo en el momento de cortarla. Por eso hace falta
        el `cancelada` aparte de la fase: `ganador()` cuenta los activos, y
        sin el, cancelar una guerra de dos en la que uno ya estaba eliminado
        coronaria al otro.

        Deja la fase en TERMINADA, que es lo que hace que la persistencia la
        marque y no la vuelva a cargar, y borra el plazo de preparacion para
        que el vigilante no intente cerrarle un dia que ya no existe.
        """
        self.cancelada = True
        self.fase = Fase.TERMINADA
        self.vence_preparacion = 0.0

    @property
    def terminada(self) -> bool:
        """Si la guerra se acabo porque solo queda uno en pie.

        Ojo con el `dia >= 1`: sin el, un lobby recien abierto con una sola
        persona dentro se daba por terminado, porque efectivamente solo hay
        uno "en pie". Lo encontro la persistencia, que marcaba la guerra como
        acabada en cuanto se creaba y no la volvia a cargar.
        """
        if self.fase is Fase.TERMINADA:
            return True
        return self.dia >= 1 and len(self.activos) <= 1

    def ganador(self) -> Master | None:
        """Quien quedo en pie, si la guerra ya acabo.

        Lo de `terminada` no es adorno: sin eso, un lobby con una sola
        persona dentro tenia ganador antes de empezar.
        """
        if self.cancelada:
            return None
        activos = self.activos
        if not self.terminada or len(activos) != 1:
            return None
        return activos[0]

    def gana_el_grial(self) -> Master | None:
        """Quien se lleva el Grial, que no es lo mismo que quien gana.

        Hacen falta 4 personas de verdad en la guerra, y que el que queda en
        pie sea una de ellas.
        """
        g = self.ganador()
        if g is None or g.es_bot or not self.otorga_grial:
            return None
        # Ganar porque los demas se fueron cuesta mas caro: hacen falta mas
        # de 5 personas apuntadas, no 4. Con 4 bastaria que tres se pusieran
        # de acuerdo para coronar a la cuarta, que es justo lo que este
        # metodo existe para impedir.
        if (
            self.acabo_por_retirada
            and len(self.humanos) < MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA
        ):
            return None
        return g
