"""Las 8 clases y el triangulo de ventajas.

La clase no da estadisticas: esas son del personaje. La clase decide dos
cosas, el cupo que ocupa en la invocacion y la ventaja del triangulo.
"""

from __future__ import annotations

from enum import Enum


class Clase(Enum):
    SABER = "Saber"
    ARCHER = "Archer"
    LANCER = "Lancer"
    RIDER = "Rider"
    CASTER = "Caster"
    ASSASSIN = "Assassin"
    BERSERKER = "Berserker"
    RULER = "Ruler"


# Las 7 clases que llenan los cupos de una guerra normal.
CLASES_BASE = (
    Clase.SABER,
    Clase.ARCHER,
    Clase.LANCER,
    Clase.RIDER,
    Clase.CASTER,
    Clase.ASSASSIN,
    Clase.BERSERKER,
)

# Probabilidad de que un Ruler sea invocado en una guerra. Cuando sale, ocupa
# el cupo de una de las clases base, que no aparece en esa guerra.
PROB_RULER = 0.05

# Triangulo clasico: Saber vence a Lancer, Lancer a Archer, Archer a Saber.
# Rider, Caster, Assassin, Berserker y Ruler quedan neutrales.
VENTAJA_SOBRE: dict[Clase, Clase] = {
    Clase.SABER: Clase.LANCER,
    Clase.LANCER: Clase.ARCHER,
    Clase.ARCHER: Clase.SABER,
}

# Medido con el simulador: el efecto es doble, porque el que tiene ventaja
# pega mas y recibe menos. A +-20% la clase decidia el combate (96% de
# victorias), mas que tres niveles de diferencia. A +-10% pesa claramente sin
# ser absoluta (83%). A +-5% equivale a un nivel de ventaja (71%).
BONO_VENTAJA = 1.10
PENALIZACION_DESVENTAJA = 0.90


def multiplicador_triangulo(atacante: Clase, defensor: Clase) -> float:
    """Multiplicador de dano por el emparejamiento de clases."""
    if VENTAJA_SOBRE.get(atacante) is defensor:
        return BONO_VENTAJA
    if VENTAJA_SOBRE.get(defensor) is atacante:
        return PENALIZACION_DESVENTAJA
    return 1.0
