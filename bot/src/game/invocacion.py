"""La invocacion: que Servant le toca a cada Master.

Una guerra tiene exactamente 7 cupos, uno por clase base. Con un 5% de
probabilidad aparece un Ruler, que **ocupa el cupo de una de las 7 clases
base**: esa clase no aparece en esa guerra.

Dentro de cada cupo, el personaje concreto sale al azar entre los de esa
clase, asi que dos guerras con las mismas clases no son la misma guerra.
"""

from __future__ import annotations

import random

from .clases import CLASES_BASE, PROB_RULER, Clase
from .personajes import Personaje, por_clase
from .servant import Servant

CUPOS = 7


def clases_de_la_guerra(rng: random.Random) -> list[Clase]:
    """Decide las 7 clases que participan, con la tirada del Ruler."""
    clases = list(CLASES_BASE)
    if rng.random() < PROB_RULER:
        desplazada = rng.choice(clases)
        clases.remove(desplazada)
        clases.append(Clase.RULER)
    rng.shuffle(clases)
    return clases


def invocar(
    personajes: list[Personaje], rng: random.Random | None = None
) -> list[Servant]:
    """Devuelve los 7 Servants de una guerra, sin personajes repetidos."""
    rng = rng or random.Random()
    catalogo = por_clase(personajes)
    faltantes = [c for c in CLASES_BASE if not catalogo.get(c)]
    if faltantes:
        raise ValueError(
            "el catalogo no tiene personajes de estas clases: "
            + ", ".join(c.value for c in faltantes)
        )

    invocados: list[Servant] = []
    for clase in clases_de_la_guerra(rng):
        disponibles = catalogo.get(clase, [])
        if not disponibles:
            # Puede pasar si sale Ruler y el catalogo aun no tiene ninguno:
            # entonces el cupo vuelve a la clase que habia sido desplazada.
            continue
        invocados.append(Servant(personaje=rng.choice(disponibles)))

    # Si falto algun cupo, se rellena con clases base que no esten ya dentro.
    usadas = {s.clase for s in invocados}
    for clase in CLASES_BASE:
        if len(invocados) >= CUPOS:
            break
        if clase in usadas:
            continue
        disponibles = catalogo.get(clase, [])
        if disponibles:
            invocados.append(Servant(personaje=rng.choice(disponibles)))

    rng.shuffle(invocados)
    return invocados[:CUPOS]
