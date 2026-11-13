"""Combates contra NPC: entrenamiento del dia.

Cada dia un Master elige pelear entre 0 y 4 combates NPC. Ganar da XP y
puede soltar un objeto; perder gasta el intento y le resta vida inicial a la
batalla contra jugadores de ese mismo dia.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from . import ai, objetos
from .battle import Batalla, Combatiente
from .personajes import SIN_NOBLE_FANTASMA, Personaje
from .servant import Servant
from .textos import IDIOMA_POR_DEFECTO, t
from .tienda import oro_por_npc

COMBATES_POR_DIA = 4

# XP por ganarle al 1.o, 2.o, 3.o y 4.o NPC. Las 4 victorias dan 165 XP.
XP_POR_VICTORIA = (20, 30, 45, 70)

# Vida inicial en la batalla contra jugadores segun derrotas contra NPC.
PENALIZACION_VIDA = {0: 1.00, 1: 0.75, 2: 0.50, 3: 0.25, 4: 0.10}

# Fuerza de cada NPC relativa al Servant del jugador.
#
# Calibrado con el simulador, y el dial es horrible: hay que saberlo antes de
# tocarlo. Medido a cuatro niveles, las victorias del jugador contra una
# Sombra de factor f son 100% hasta 0.80, 98% con 0.85, 96% con 0.88, 92% con
# 0.92, 87% con 0.95, 83% con 0.97, **49% con 1.00** y 14% con 1.03. O sea
# que todo lo que baje de 0.85 es un regalo, todo lo que pase de 1.00 es
# imposible, y los ultimos tres centesimos valen 34 puntos. La banda util es
# 0.85-1.00 y dentro de ella la curva es un escalon.
#
# La buena noticia es que la curva **no depende del nivel** (misma tasa a
# nivel 1 y a nivel 15, +-3 puntos), asi que la escalera significa lo mismo
# durante toda la guerra.
FACTOR_DIFICULTAD = (0.88, 0.93, 0.96, 0.985)

# Cuanto se endurecen los NPC por cada dia de guerra transcurrido, para que
# entrenar rinda mas al principio. Con todo esto la escalera queda asi
# (`python -m src.simulator --semilla 7 npc`):
#
#   dia 1: 97% / 90% / 85% / 75%  ->  ~139 XP
#   dia 7: 91% / 80% / 70% / 68%  ->  ~122 XP
#
# Los cuatro se pueden ganar siempre y ninguno es gratis. Y no entrenar no es
# una opcion: medido, quien no pelea ninguno no gana ninguna guerra.
ENDURECIMIENTO_POR_DIA = 0.01

# Y el tope, que es lo que impide el acantilado. Sin el, el endurecimiento
# empujaba el factor del 4.o NPC por encima de 1.00 y la escalera se rompia
# de un dia para otro: el 4.o pasaba del 84% el dia 3 al 14% el dia 5 y al 5%
# el dia 7. Una Sombra nunca puede ser un espejo mas fuerte que tu.
FACTOR_MAXIMO = 0.99

PROB_OBJETO = {0: 0.10, 1: 0.15, 2: 0.25, 3: 0.40}


@dataclass
class ResultadoNPC:
    gano: bool
    xp: int
    # La ficha del objeto que solto, no su nombre: el nombre depende del
    # idioma y quien lo recibe tiene que guardarse la clave.
    objeto: objetos.Objeto | None
    registro: list[str]
    rival: str = ""
    # El oro para la tienda. Va junto a la XP porque es lo mismo: lo que paga
    # haber ganado. Quien lo cobra es el Cog, igual que con la XP.
    oro: int = 0


def vida_inicial(servant: Servant, derrotas_npc: int) -> int:
    """Vida con la que empieza la batalla contra jugadores."""
    factor = PENALIZACION_VIDA.get(min(derrotas_npc, COMBATES_POR_DIA), 0.10)
    return max(1, int(servant.vida_maxima * factor))


def construir_npc(
    servant: Servant, indice: int, dia: int, idioma: str | None = None
) -> Servant:
    """Crea el rival NPC numero `indice` (0..3) para un dia dado.

    La Sombra es un espejo del Servant del jugador multiplicado por el
    factor de dificultad, y comparte su clase: asi el triangulo queda neutro
    y el entrenamiento mide al jugador, no su emparejamiento.

    Tambien comparte sus habilidades, por la misma razon: si el jugador las
    usara contra una Sombra que no las tiene, entrenar se volveria mas facil
    a partir del nivel 5 y la curva de XP se iria sola.
    """
    factor = min(
        FACTOR_MAXIMO,
        FACTOR_DIFICULTAD[indice] * (1 + ENDURECIMIENTO_POR_DIA * (dia - 1)),
    )
    base = servant.personaje
    sombra = Personaje(
        nombre=t("npc.sombra", idioma, numero=indice + 1),
        clase=base.clase,
        mult_vida=base.mult_vida * factor,
        mult_ataque=base.mult_ataque * factor,
        mult_velocidad=base.mult_velocidad * factor,
        habilidades=base.habilidades,
        noble_fantasma=SIN_NOBLE_FANTASMA,
    )
    # A proposito no se valida el presupuesto: una Sombra no es un personaje
    # jugable, es una vara de medir.
    return Servant(personaje=sombra, nivel=servant.nivel)


def pelear(
    servant: Servant,
    indice: int,
    dia: int,
    rng: random.Random | None = None,
    max_turnos: int = 50,
    idioma: str = IDIOMA_POR_DEFECTO,
) -> ResultadoNPC:
    """Resuelve un combate NPC completo. El resultado es inmediato."""
    rng = rng or random.Random()
    rival = construir_npc(servant, indice, dia, idioma)

    batalla = Batalla(
        [
            Combatiente(id="jugador", nombre=servant.nombre, servant=servant),
            Combatiente(id="npc", nombre=rival.nombre, servant=rival),
        ],
        rng=rng,
        idioma=idioma,
    )

    # Los dos lados los juega la IA: el jugador tambien, porque el combate NPC
    # se resuelve al instante. Si mas adelante se quiere jugar a mano, basta
    # pasar las decisiones del jugador en lugar de pedirlas a `ai.decidir`.
    while not batalla.terminada and batalla.turno < max_turnos:
        decisiones = {
            c.id: ai.decidir(batalla, c, rng) for c in batalla.vivos
        }
        batalla.resolver_turno(decisiones)

    ganador = batalla.ganador()
    gano = ganador is not None and ganador.id == "jugador"
    xp = XP_POR_VICTORIA[indice] if gano else 0
    objeto = None
    if gano and rng.random() < PROB_OBJETO.get(indice, 0.10):
        # Que sale lo sortea el catalogo, pesado por lo comun que es cada
        # objeto; cuanto suelta cada NPC lo decide `PROB_OBJETO`, aqui arriba.
        # Los catalizadores no entran: ver `objetos.sueltos`.
        objeto = objetos.sortear(rng)
    return ResultadoNPC(
        gano=gano,
        xp=xp,
        objeto=objeto,
        registro=batalla.registro,
        rival=rival.nombre,
        oro=oro_por_npc(indice) if gano else 0,
    )
