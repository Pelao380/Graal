"""Servants invocados: una ficha de personaje mas nivel y experiencia.

Las estadisticas y el rasgo son del personaje (ver personajes.py). Aqui solo
vive la progresion.
"""

from __future__ import annotations

from dataclasses import dataclass

from .clases import Clase
from .personajes import Habilidad, NobleFantasma, Personaje, Rasgo

NIVEL_MAXIMO = 15

# Niveles en los que se desbloquea cada habilidad.
NIVELES_HABILIDAD = (5, 10, 15)

# Mana: los valores por defecto. Un rasgo puede cambiarlos por personaje.
MANA_INICIAL = 20
MANA_POR_ATAQUE = 15
MANA_POR_DEFENSA = 20
COSTO_NOBLE_FANTASMA = 100

# Una habilidad no cuesta mana, pero tampoco deja al Servant a cero: da
# menos que atacar, porque atacar ademas hace dano.
#
# Medido: sin esto, gastar el turno en una habilidad costaba el ataque *y* los
# 15 de mana, o sea retrasar el Noble Fantasma, y ninguna habilidad de ataque
# pagaba lo que cuesta (ver docs/decisiones.md).
MANA_POR_HABILIDAD = 10


def xp_para_subir(nivel: int) -> int:
    """XP necesaria para pasar del nivel n al n+1: 20 + 5*n."""
    return 20 + 5 * nivel


def xp_acumulada(nivel: int) -> int:
    """XP total necesaria para alcanzar un nivel desde el 1."""
    return sum(xp_para_subir(n) for n in range(1, nivel))


@dataclass
class Servant:
    personaje: Personaje
    nivel: int = 1
    xp: int = 0

    # --- lo que define el personaje ---

    @property
    def nombre(self) -> str:
        return self.personaje.nombre

    @property
    def clase(self) -> Clase:
        return self.personaje.clase

    @property
    def rasgo(self) -> Rasgo:
        return self.personaje.rasgo

    @property
    def noble_fantasma(self) -> NobleFantasma:
        return self.personaje.noble_fantasma

    def nivel_de_habilidad(self, numero: int) -> int:
        """A que nivel se desbloquea la habilidad `numero` (1, 2 o 3)."""
        return NIVELES_HABILIDAD[numero - 1]

    @property
    def todas_las_habilidades(self) -> list[tuple[int, Habilidad, bool]]:
        """Las tres, con su numero y si ya estan desbloqueadas.

        Para la ficha: un Master quiere saber lo que le viene, no solo lo que
        tiene.
        """
        return [
            (n, h, self.nivel >= self.nivel_de_habilidad(n))
            for n, h in enumerate(self.personaje.habilidades, 1)
        ]

    @property
    def ascension(self) -> str:
        """Que ascension le toca por nivel: "1", "2", "3" o "4".

        En FGO la ascension es el personaje cambiando de aspecto al progresar,
        y hay cuatro. Las bandas son 1-4, 5-9, 10-14 y 15, que **son los mismos
        cortes que `NIVELES_HABILIDAD`**: el aspecto cambia justo cuando se
        desbloquea una habilidad, asi que subir de nivel se nota en la ficha y
        en el dibujo a la vez. Por eso se cuenta desde ahi en lugar de repetir
        los numeros: si alguna vez se mueven los niveles de habilidad, esto se
        mueve con ellos y no queda a medio camino.

        Devuelve texto porque es la clave del diccionario `imagenes` del
        plantel, que viene de un JSON.

        Ojo: esto es solo el numero. **Nada en `src/` abre la imagen**, que es
        la regla del arte (ver docs/decisiones.md y tests/test_arte.py).
        """
        desbloqueadas = sum(1 for n in NIVELES_HABILIDAD if self.nivel >= n)
        return str(1 + desbloqueadas)

    @property
    def imagen(self) -> str:
        """La URL del arte que le toca por nivel, o "" si no la tiene.

        Devuelve una URL de Atlas Academy, no un archivo: el bot **enlaza** el
        arte, nunca lo sube. La diferencia importa y esta explicada en
        docs/decisiones.md.

        Cae a la ultima ascension que si tenga en lugar de quedarse sin nada:
        un personaje al que le falte la cuarta es mejor que se vea con la
        tercera que que se quede en blanco al llegar al nivel 15.
        """
        if not self.personaje.imagenes:
            return ""
        indice = min(int(self.ascension), len(self.personaje.imagenes)) - 1
        return self.personaje.imagenes[indice]

    # --- estadisticas segun nivel ---

    @property
    def vida_maxima(self) -> int:
        return self.personaje.vida(self.nivel)

    @property
    def ataque(self) -> int:
        return self.personaje.ataque(self.nivel)

    @property
    def velocidad(self) -> int:
        return self.personaje.velocidad(self.nivel)

    @property
    def habilidades_desbloqueadas(self) -> int:
        return sum(1 for n in NIVELES_HABILIDAD if self.nivel >= n)

    @property
    def habilidades(self) -> list[Habilidad]:
        """Las habilidades que ya tiene desbloqueadas, en orden."""
        return list(self.personaje.habilidades[: self.habilidades_desbloqueadas])

    def habilidad(self, numero: int) -> Habilidad | None:
        """La habilidad `numero` (1, 2 o 3), si ya esta desbloqueada."""
        if not 1 <= numero <= self.habilidades_desbloqueadas:
            return None
        return self.personaje.habilidades[numero - 1]

    @property
    def nombres_habilidades(self) -> list[str]:
        return [h.nombre for h in self.habilidades]

    # --- progresion ---

    def ganar_xp(self, cantidad: int) -> list[int]:
        """Suma XP y sube de nivel las veces que corresponda.

        Devuelve la lista de niveles alcanzados, para poder anunciarlos.
        """
        if cantidad <= 0:
            return []
        self.xp += cantidad
        subidas: list[int] = []
        while self.nivel < NIVEL_MAXIMO and self.xp >= xp_para_subir(self.nivel):
            self.xp -= xp_para_subir(self.nivel)
            self.nivel += 1
            subidas.append(self.nivel)
        if self.nivel >= NIVEL_MAXIMO:
            self.xp = 0
        return subidas

