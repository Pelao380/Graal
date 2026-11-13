"""Cerrar un dia de guerra: invocar, formar batallas, pelearlas y pasar pagina.

Logica pura, sin Discord. Es el unico sitio donde se cierra un dia, y lo
llaman dos cosas distintas:

- el boton del creador, que cierra el dia cuando quiere sin esperar la
  ventana de preparacion,
- y el vigilante de plazos, cuando esa ventana se agota (todavia por hacer).

Por eso el orden vive aqui y no en quien lo llama: si cada puerta cerrara el
dia a su manera, dos guerras iguales acabarian distintas. Es la misma razon
por la que `Guerra.abrir_dia` abre el dia desde la propia guerra.

**Hay dos formas de pelear el dia y las dos viven aqui.**

- `cerrar_dia` lo pelea todo de corrido con la IA. Es lo que usa el
  simulador, lo que usa una guerra sin personas dentro, y la red de seguridad
  del vigilante de plazos.
- `abrir_combates` deja las batallas **en curso**, esperando decisiones, y
  `cerrar_combates` pasa el dia cuando se acabaron todas. Eso es jugar a
  mano, y es lo que usa Discord.

Las dos tienen que dejar la misma mesa: invocar por quien falte, formar los
grupos, registrar las derrotas y pasar pagina **en ese orden**. Si algun dia
se separan, dos guerras iguales acabarian distintas.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import ai
from .battle import Batalla, Combatiente, Estado
from .combate import Combate
from .npc import vida_inicial
from .tienda import ORO_POR_BATALLA_GANADA
from .war import Fase, Guerra

# Tope de turnos de una batalla antes de darla por empatada. El simulador usa
# 60 para las batallas de guerra y ninguna se acerca; esta aqui para que un
# empate imposible no cuelgue el bot.
MAXIMO_TURNOS = 60


@dataclass(frozen=True)
class BatallaDelDia:
    """Lo que paso en una batalla, para poder contarlo.

    `caidos` es una lista y no uno solo porque **en una batalla puede caer mas
    de un Servant**: la batalla se acaba cuando cae el primero, pero si quedan
    dos o mas en pie y alguien vota por seguir, se sigue, y entonces puede
    caer otro. Durante un tiempo solo se apuntaba la derrota del primero y las
    demas se perdian: quien cayera en el turno especial salia gratis.
    """

    grupo: list[str]
    caidos: list[str]
    eliminados: list[str]
    turnos: int
    registro: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CierreDelDia:
    """Lo que paso al cerrar el dia. Quien lo recibe solo tiene que narrarlo."""

    dia: int
    invocados: list[str]
    batallas: list[BatallaDelDia]
    descansan: list[str]
    terminada: bool
    ganador: str | None
    grial: str | None


def puede_cerrar(guerra: Guerra, id_: str) -> bool:
    """Si ese Master puede cerrar el dia ahora mismo.

    Tres condiciones: es el creador, la guerra esta en preparacion y **todas
    las personas vivas han dicho que estan listas**. Lo tercero no estaba al
    principio y era un agujero: el creador entrenaba sus 4 combates y cerraba
    antes de que los demas entrenaran, lo que le doblaba las victorias (del
    11.5% al 22.9% medido con 1500 guerras de 4 personas) y dejaba a los otros
    tres en el 2.7%. Ahora el boton significa "ya esta todo el mundo", que es
    para lo que se pidio.

    Cuando exista el vigilante de plazos, agotarse la ventana sera la otra
    forma de cerrar el dia, y esa no esperara a nadie.
    """
    return (
        guerra.fase is Fase.PREPARACION
        and not guerra.terminada
        and id_ == guerra.creador_id
        and not guerra.faltan_por_estar_listos
    )


def armar_batalla(
    guerra: Guerra, grupo: list[str], rng: random.Random | None = None
) -> Batalla:
    """Monta la batalla de un grupo, con la vida que traen de entrenar."""
    rng = rng or guerra.rng
    combatientes = [
        Combatiente(
            id=id_,
            nombre=guerra.masters[id_].nombre,
            servant=guerra.masters[id_].servant,
            vida=vida_inicial(
                guerra.masters[id_].servant, guerra.masters[id_].derrotas_npc
            ),
        )
        for id_ in grupo
    ]
    return Batalla(combatientes, rng=rng, idioma=guerra.idioma)


def anotar_batalla(
    guerra: Guerra, grupo: list[str], batalla: Batalla
) -> BatallaDelDia:
    """Apunta lo que deja una batalla acabada: lo visto y la derrota.

    Lo llaman los dos caminos, el de la IA y el de las personas, porque esto
    es lo que no se puede olvidar: si se anota en un lado y no en el otro, hay
    guerras donde los Servants nunca se destapan.
    """
    # Pelear contra alguien es verle el Servant, y eso no se olvida. Se
    # apunta aunque la batalla acabe en empate: lo que lo revela es haber
    # estado delante.
    for id_ in grupo:
        m = guerra.masters[id_]
        m.conocidos.update(o for o in grupo if o != id_)
        # El registro se queda con quien peleo, no se publica: las frases
        # nombran las habilidades y eso delata al Servant.
        m.ultimo_registro = list(batalla.registro)
        m.ultimo_registro_dia = guerra.dia

    # Todos los que cayeron, en el orden en que cayeron, y cada uno con su
    # derrota: una batalla que sigue despues de la votacion puede tumbar a
    # varios, y la derrota de cada uno es igual de real que la del primero.
    caidos = list(batalla.caidos)
    eliminados = [id_ for id_ in caidos if guerra.registrar_derrota(id_)]

    # El oro de ganar la batalla. Va aqui por lo mismo que las derrotas: es de
    # las cosas que no se pueden olvidar al acabar una batalla, y los dos
    # caminos (la IA y las personas) pasan por esta funcion. Si estuviera en el
    # Cog, las batallas que resuelve la IA no pagarian.
    #
    # Cobra quien sale en pie **de una batalla que tumbo a alguien**: un empate
    # por limite de turnos no paga, porque lo que se cobra es ganar y no estar.
    if caidos:
        for id_ in grupo:
            if id_ not in caidos:
                guerra.masters[id_].oro += ORO_POR_BATALLA_GANADA

    return BatallaDelDia(
        grupo=list(grupo),
        caidos=caidos,
        eliminados=eliminados,
        turnos=batalla.turno,
        registro=list(batalla.registro),
    )


def jugar_batalla(
    guerra: Guerra,
    grupo: list[str],
    rng: random.Random | None = None,
    maximo_turnos: int = MAXIMO_TURNOS,
) -> BatallaDelDia:
    """Pelea una batalla del dia entera con la IA en todos los lados."""
    rng = rng or guerra.rng
    batalla = armar_batalla(guerra, grupo, rng)
    while not batalla.terminada and batalla.turno < maximo_turnos:
        if batalla.estado is Estado.VOTACION:
            batalla.registrar_votos(
                {c.id: ai.votar_continuar(batalla, c) for c in batalla.vivos}
            )
            continue
        batalla.resolver_turno(
            {c.id: ai.decidir(batalla, c, rng) for c in batalla.vivos}
        )
    return anotar_batalla(guerra, grupo, batalla)


def cerrar_dia(guerra: Guerra, rng: random.Random | None = None) -> CierreDelDia:
    """Cierra el dia: invoca por quien falte, pelea todo y pasa al siguiente.

    El orden importa y es el mismo que mide el simulador. Lo unico que no se
    hace aqui es entrenar y declarar por los bots: eso es abrir el dia, y lo
    hace `siguiente_dia` al final de esta misma funcion.
    """
    if guerra.fase is not Fase.PREPARACION:
        raise RuntimeError("el dia solo se cierra desde la preparacion")

    rng = rng or guerra.rng
    # Antes de nada, el plazo de la invocacion: nadie pelea sin Servant.
    # `formar_batallas` lo haria igual, pero aqui sabemos a quien le toco para
    # poder decirselo.
    invocados = [m.id for m in guerra.invocar_a_los_que_falten(rng)]

    grupos, _ = guerra.formar_batallas(rng)
    descansan = guerra.descansan(grupos)
    batallas = [jugar_batalla(guerra, grupo, rng) for grupo in grupos]

    dia = guerra.dia
    guerra.siguiente_dia()

    ganador = guerra.ganador()
    grial = guerra.gana_el_grial()
    return CierreDelDia(
        dia=dia,
        invocados=invocados,
        batallas=batallas,
        descansan=descansan,
        terminada=guerra.terminada,
        ganador=ganador.id if ganador else None,
        grial=grial.id if grial else None,
    )


# --- jugar el dia a mano ---


@dataclass
class CombatesDelDia:
    """Las batallas del dia, en curso. Lo que Discord tiene en la mano.

    No es un `frozen`: se va vaciando a medida que los combates acaban. Lo
    que ya acabo esta en `resueltos` y **ya esta anotado** en la guerra; lo
    que sigue, en `combates`.
    """

    dia: int
    invocados: list[str]
    descansan: list[str]
    combates: list[Combate] = field(default_factory=list)
    resueltos: list[BatallaDelDia] = field(default_factory=list)

    @property
    def pendientes(self) -> list[Combate]:
        return [c for c in self.combates if not c.terminado]

    @property
    def acabaron_todos(self) -> bool:
        return not self.pendientes

    def combate_de(self, id_: str) -> Combate | None:
        """El combate en el que pelea ese Master, si pelea en alguno."""
        for c in self.pendientes:
            if id_ in c.batalla.combatientes:
                return c
        return None


def abrir_combates(
    guerra: Guerra,
    rng: random.Random | None = None,
    maximo_turnos: int = MAXIMO_TURNOS,
) -> CombatesDelDia:
    """Cierra la preparacion y deja las batallas del dia esperando decisiones.

    Hace lo mismo que `cerrar_dia` hasta el momento de pelear: invoca por
    quien falte y forma los grupos. Lo que no hace es pelear ni pasar al dia
    siguiente; eso es `cerrar_combates`, cuando se acaben todas.

    Las batallas de puros bots se resuelven aqui mismo, porque no hay a quien
    esperar: salen ya en `resueltos`.
    """
    if guerra.fase is not Fase.PREPARACION:
        raise RuntimeError("el dia solo se cierra desde la preparacion")

    rng = rng or guerra.rng
    invocados = [m.id for m in guerra.invocar_a_los_que_falten(rng)]
    grupos, _ = guerra.formar_batallas(rng)
    estado = CombatesDelDia(
        dia=guerra.dia,
        invocados=invocados,
        descansan=guerra.descansan(grupos),
    )
    for grupo in grupos:
        humanos = {id_ for id_ in grupo if not guerra.masters[id_].es_bot}
        estado.combates.append(
            Combate(
                armar_batalla(guerra, grupo, rng),
                humanos=humanos,
                rng=rng,
                maximo_turnos=maximo_turnos,
                reloj=guerra.reloj,
            )
        )
    guerra.fase = Fase.BATALLA
    recoger(guerra, estado)
    return estado


def recoger(guerra: Guerra, estado: CombatesDelDia) -> list[BatallaDelDia]:
    """Anota los combates que hayan acabado y devuelve los recien anotados.

    Es idempotente a proposito: lo llama cada decision y cada plazo, y un
    combate solo se anota una vez. Si esto se olvidara, nadie se enteraria
    hasta que un Servant derrotado siguiera vivo.
    """
    nuevos: list[BatallaDelDia] = []
    ya = {tuple(b.grupo) for b in estado.resueltos}
    for c in estado.combates:
        grupo = sorted(c.batalla.combatientes)
        if not c.terminado or tuple(grupo) in ya:
            continue
        b = anotar_batalla(guerra, grupo, c.batalla)
        estado.resueltos.append(b)
        ya.add(tuple(grupo))
        nuevos.append(b)
    return nuevos


def cerrar_combates(guerra: Guerra, estado: CombatesDelDia) -> CierreDelDia:
    """Pasa pagina cuando se acabaron todas las batallas del dia.

    Deja exactamente lo que deja `cerrar_dia`, para que el canal se narre
    igual se haya jugado a mano o no.
    """
    recoger(guerra, estado)
    if not estado.acabaron_todos:
        raise RuntimeError("todavia quedan batallas sin acabar")
    # `siguiente_dia` deja la fase (PREPARACION, o TERMINADA si solo queda
    # uno), asi que de aqui no sale nunca una guerra en Fase.BATALLA.
    guerra.siguiente_dia()
    ganador = guerra.ganador()
    grial = guerra.gana_el_grial()
    return CierreDelDia(
        dia=estado.dia,
        invocados=list(estado.invocados),
        batallas=list(estado.resueltos),
        descansan=list(estado.descansan),
        terminada=guerra.terminada,
        ganador=ganador.id if ganador else None,
        grial=grial.id if grial else None,
    )


def recuperar_dia(guerra: Guerra, rng: random.Random | None = None) -> CierreDelDia:
    """Saca del atasco a una guerra que se quedo en `Fase.BATALLA`.

    Pasa si el bot se reinicia a media batalla: los combates viven en memoria
    (una batalla dura minutos, un plazo dura dias) y al volver no estan, pero
    la guerra si, y parada en una fase que solo cierra una decision que ya no
    va a llegar.

    Lo que si sobrevive es **quien peleo hoy**, porque `anotar_batalla` deja
    `ultimo_registro_dia` puesto y eso se guarda. Asi que se vuelven a formar
    los grupos y se pelean con la IA solo los de quien no peleo todavia; el
    que ya tiene su batalla del dia apuntada no la repite.
    """
    if guerra.fase is not Fase.BATALLA:
        raise RuntimeError("esto solo saca de Fase.BATALLA")
    rng = rng or guerra.rng
    grupos, _ = guerra.formar_batallas(rng)
    pendientes = [
        grupo
        for grupo in grupos
        if not any(
            guerra.masters[id_].ultimo_registro_dia == guerra.dia for id_ in grupo
        )
    ]
    batallas = [jugar_batalla(guerra, grupo, rng) for grupo in pendientes]
    dia_ = guerra.dia
    guerra.siguiente_dia()
    ganador = guerra.ganador()
    grial = guerra.gana_el_grial()
    return CierreDelDia(
        dia=dia_,
        invocados=[],
        batallas=batallas,
        descansan=guerra.descansan(grupos),
        terminada=guerra.terminada,
        ganador=ganador.id if ganador else None,
        grial=grial.id if grial else None,
    )


def rendir_en_combates(estado: CombatesDelDia, id_: str) -> list[str]:
    """Saca de su batalla en curso a quien se acaba de rendir.

    No se le mata al Servant ni se le da la batalla por perdida: se le quita
    de los que deciden a mano, asi que **la IA juega su mano**, igual que
    cuando alguien no contesta en 5 minutos. Ya esta fuera de la guerra
    (`Master.retirado`), asi que como acabe esa batalla no cambia nada para
    el; lo que importa es que los demas puedan seguir peleandola.

    Y si era el unico que decidia, la batalla se queda sin nadie a quien
    esperar y se juega sola hasta el final: si no, el dia se quedaria colgado
    hasta que venciera el plazo del turno.
    """
    combate = estado.combate_de(id_)
    if combate is None:
        return []
    combate.humanos.discard(id_)
    eventos: list[str] = []
    while not combate.terminado and not combate.pendientes:
        eventos.extend(combate.avanzar_con_ia())
    return eventos


def abandonar_combates(guerra: Guerra, estado: CombatesDelDia) -> CierreDelDia:
    """Acaba a la IA lo que quede y cierra el dia. La red de seguridad.

    La usa el plazo del dia y la usaria un reinicio del bot: un combate a
    medias no puede dejar la guerra parada para siempre. Es el mismo trato
    que un turno sin contestar, pero de golpe.
    """
    for c in estado.pendientes:
        while not c.terminado:
            c.avanzar_con_ia()
    return cerrar_combates(guerra, estado)
