"""Una batalla que espera a las personas, en vez de jugarla la IA de corrido.

Logica pura, sin Discord. `battle.py` sabe resolver un turno cuando tiene
todas las decisiones; lo que no sabia nadie es **esperar**. Eso es lo que hace
este modulo, y es la unica pieza que faltaba para que una guerra se pueda
jugar a mano.

La regla de fondo: **las decisiones de un turno son simultaneas y secretas**.
Nadie ve lo que eligio otro, el turno no se resuelve hasta que han elegido
todos, y los bots deciden en el mismo instante que las personas (no antes, o
el orden de llegada valdria informacion). De ahi sale la forma del objeto:

- `pendientes` es a quien se espera ahora mismo,
- `decidir` apunta una decision y devuelve `[]` mientras falte alguien,
- cuando no falta nadie, resuelve el turno y devuelve los eventos,
- y `avanzar_con_ia` es la salida de emergencia del plazo: rellena por quien
  no contesto y sigue. Un combate no puede quedarse colgado porque alguien
  cerro Discord.

Un combate sin personas vivas dentro (dos bots, o el ultimo humano caido) se
juega solo hasta el final: no hay a quien esperar. Eso hace que el camino
viejo —la IA por todos— siga siendo un caso particular de este, y no un
modulo aparte.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from enum import Enum

from . import ai
from .battle import Accion, Batalla, Decision, Estado

# Tope de turnos antes de dar la batalla por empatada. El mismo que usaba el
# cierre automatico del dia: el simulador no ve ninguna batalla de guerra
# acercarse, esta para que un empate imposible no cuelgue el bot.
MAXIMO_TURNOS = 60

# Lo que se espera a alguien antes de decidir por el. Es el plazo por turno de
# las reglas. Sin esto, una persona que cierra Discord deja la batalla —y con
# ella el dia, y con el la guerra— parada para siempre.
SEGUNDOS_POR_TURNO = 5 * 60


class Espera(Enum):
    """Que se le esta pidiendo a la gente ahora mismo."""

    TURNO = "turno"
    VOTACION = "votacion"
    NADA = "nada"


class Combate:
    """Una batalla en curso que para a pedir decisiones.

    `humanos` son los ids que deciden a mano. El resto los decide la IA en el
    momento de resolver, nunca antes.
    """

    def __init__(
        self,
        batalla: Batalla,
        humanos: set[str],
        rng: random.Random | None = None,
        maximo_turnos: int = MAXIMO_TURNOS,
        reloj: Callable[[], float] = time.time,
    ) -> None:
        self.batalla = batalla
        self.humanos = set(humanos)
        self.rng = rng or batalla.rng
        self.maximo_turnos = maximo_turnos
        # El reloj de la guerra, para el plazo del turno. Se puede cambiar por
        # uno de mentira y asi los 5 minutos pasan en una linea.
        self.reloj = reloj
        self.espera_desde = reloj()
        self._decisiones: dict[str, Decision] = {}
        self._votos: dict[str, bool] = {}
        # Lo ultimo que paso, para que quien narra no tenga que acordarse de
        # por donde iba el registro.
        self.ultimos_eventos: list[str] = []
        self._jugar_lo_que_no_espera_a_nadie()

    # --- consultas ---

    @property
    def terminado(self) -> bool:
        return self.batalla.terminada or self.batalla.turno >= self.maximo_turnos

    @property
    def espera(self) -> Espera:
        if self.terminado:
            return Espera.NADA
        if self.batalla.estado is Estado.VOTACION:
            return Espera.VOTACION
        return Espera.TURNO

    @property
    def pendientes(self) -> list[str]:
        """A quien se espera. Vacio significa que el combate puede avanzar."""
        if self.terminado:
            return []
        if self.batalla.estado is Estado.VOTACION:
            return [
                c.id
                for c in self.batalla.vivos
                if c.id in self.humanos and c.id not in self._votos
            ]
        return [
            c.id
            for c in self.batalla.vivos
            if c.id in self.humanos
            and c.id not in self._decisiones
            and self._puede_actuar(c.id)
        ]

    def _puede_actuar(self, id_: str) -> bool:
        """Si tiene algo que decidir este turno.

        En el turno especial, a quien voto por retirarse solo le queda
        esperar: no se le pregunta nada.
        """
        posibles = self.batalla.acciones_posibles(id_)
        return bool(posibles) and posibles != [Accion.ESPERAR]

    @property
    def segundos_esperando(self) -> float:
        """Lo que lleva esperando a que alguien decida."""
        return max(0.0, self.reloj() - self.espera_desde)

    def plazo_cumplido(self, segundos: float = SEGUNDOS_POR_TURNO) -> bool:
        """Si se le acabo el tiempo al turno y hay que decidir por quien falte.

        El reloj se pone a cero cuando el turno se resuelve, no cada vez que
        alguien decide: son 5 minutos por turno, no por persona.
        """
        return (
            not self.terminado
            and bool(self.pendientes)
            and self.segundos_esperando >= segundos
        )

    def ya_decidio(self, id_: str) -> bool:
        if self.batalla.estado is Estado.VOTACION:
            return id_ in self._votos
        return id_ in self._decisiones

    # --- decidir ---

    def decidir(self, id_: str, decision: Decision) -> list[str]:
        """Apunta la decision de alguien. Devuelve los eventos si cerro el turno.

        Mientras falte gente devuelve `[]`: el turno no se resuelve a medias,
        porque eso delataria lo que eligio el primero.
        """
        if self.espera is not Espera.TURNO:
            raise RuntimeError(f"ahora no se decide un turno, se espera {self.espera}")
        if id_ not in self.humanos:
            raise RuntimeError(f"{id_} no decide a mano en este combate")
        if not self.batalla.combatientes[id_].vivo:
            raise RuntimeError(f"{id_} ya cayo")
        if not self._puede_actuar(id_):
            raise RuntimeError(f"{id_} no tiene nada que decidir este turno")
        # Cambiar de idea no revelaria nada (nadie ve nada hasta que se
        # resuelve el turno), pero se prohibe igual: el menu apaga los botones
        # en cuanto eliges, y si la regla no estuviera aqui tambien, dos
        # pulsaciones seguidas harian cosas distintas segun quien mire.
        if id_ in self._decisiones:
            raise RuntimeError(f"{id_} ya decidio este turno")
        self._decisiones[id_] = decision
        if self.pendientes:
            return []
        return self._resolver_turno()

    def usar_objeto(self, id_: str, objeto) -> list[str]:
        """Usa un objeto de combate. No cuenta como la decision del turno.

        Despues de usarlo sigues teniendo que elegir tu accion, y por eso no
        se toca `self._decisiones` ni se resuelve nada: el turno se cierra
        cuando todos deciden, igual que siempre.

        El tope de uno por batalla **no esta aqui**: vive en el inventario del
        Master (`objetos.Inventario.usados_en_la_batalla`), porque el objeto y
        su tope son suyos y una batalla no sabe de inventarios. Lo comprueba
        el Cog antes de llamar.
        """
        if self.terminado:
            raise RuntimeError("el combate ya acabo")
        if id_ not in self.humanos:
            raise RuntimeError(f"{id_} no usa objetos a mano en este combate")
        combatiente = self.batalla.combatientes.get(id_)
        if combatiente is None:
            raise RuntimeError(f"{id_} no esta en este combate")
        if not combatiente.vivo:
            raise RuntimeError(f"{id_} ya cayo")
        return self.batalla.usar_objeto(combatiente, objeto)

    def usar_sello(self, id_: str, sello) -> list[str]:
        """Gasta un Sello de Comando. Tampoco cuenta como la decision del turno.

        Las mismas comprobaciones que `usar_objeto` y por las mismas razones.
        Los dos topes del Sello (tres por guerra, uno por batalla) **no estan
        aqui**: viven en el `Master` (`sellos` y `sellos_en_la_batalla`), y los
        comprueba el Cog antes de llamar, igual que el del inventario.
        """
        if self.terminado:
            raise RuntimeError("el combate ya acabo")
        if id_ not in self.humanos:
            raise RuntimeError(f"{id_} no usa sellos a mano en este combate")
        combatiente = self.batalla.combatientes.get(id_)
        if combatiente is None:
            raise RuntimeError(f"{id_} no esta en este combate")
        if not combatiente.vivo:
            raise RuntimeError(f"{id_} ya cayo")
        return self.batalla.usar_sello(combatiente, sello)

    def votar(self, id_: str, seguir: bool) -> list[str]:
        """Apunta un voto. Devuelve los eventos si cerro la votacion."""
        if self.espera is not Espera.VOTACION:
            raise RuntimeError("no hay una votacion abierta")
        if id_ not in self.humanos:
            raise RuntimeError(f"{id_} no vota a mano en este combate")
        if not self.batalla.combatientes[id_].vivo:
            raise RuntimeError(f"{id_} ya cayo")
        if id_ in self._votos:
            raise RuntimeError(f"{id_} ya voto")
        self._votos[id_] = seguir
        if self.pendientes:
            return []
        return self._resolver_votacion()

    def avanzar_con_ia(self) -> list[str]:
        """Rellena por quien no contesto y sigue. Es lo que hace el plazo.

        No es lo mismo que `decidir` por ellos: aqui la IA elige igual que
        elegiria para un bot, asi que faltar al turno no es ni ventaja ni
        castigo aparte de no haber elegido.
        """
        if self.espera is Espera.VOTACION:
            return self._resolver_votacion()
        if self.espera is Espera.TURNO:
            return self._resolver_turno()
        return []

    # --- resolver ---

    def _decisiones_completas(self) -> dict[str, Decision]:
        """Las decisiones apuntadas mas las de la IA por todos los demas."""
        completas = dict(self._decisiones)
        for c in self.batalla.vivos:
            if c.id in completas or not self._puede_actuar(c.id):
                continue
            completas[c.id] = ai.decidir(self.batalla, c, self.rng)
        return completas

    def _resolver_turno(self) -> list[str]:
        eventos = self.batalla.resolver_turno(self._decisiones_completas())
        self._decisiones.clear()
        self._votos.clear()
        self.espera_desde = self.reloj()
        eventos.extend(self._jugar_lo_que_no_espera_a_nadie())
        self.ultimos_eventos = eventos
        return eventos

    def _resolver_votacion(self) -> list[str]:
        votos = dict(self._votos)
        for c in self.batalla.vivos:
            if c.id not in votos:
                votos[c.id] = ai.votar_continuar(self.batalla, c)
        eventos = self.batalla.registrar_votos(votos)
        self._votos.clear()
        self._decisiones.clear()
        self.espera_desde = self.reloj()
        eventos.extend(self._jugar_lo_que_no_espera_a_nadie())
        self.ultimos_eventos = eventos
        return eventos

    def _jugar_lo_que_no_espera_a_nadie(self) -> list[str]:
        """Sigue solo mientras no haya a quien preguntar.

        Dos casos: un combate de bots, y un combate donde ya cayeron todas las
        personas. En los dos esperar seria esperar a nadie.
        """
        eventos: list[str] = []
        while not self.terminado and not self.pendientes:
            if self.batalla.estado is Estado.VOTACION:
                votos = {
                    c.id: ai.votar_continuar(self.batalla, c)
                    for c in self.batalla.vivos
                }
                eventos.extend(self.batalla.registrar_votos(votos))
                continue
            eventos.extend(self.batalla.resolver_turno(self._decisiones_completas()))
            self._decisiones.clear()
        return eventos
