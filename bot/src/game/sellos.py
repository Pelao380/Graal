"""Los Sellos de Comando: tres milagros por guerra.

Un Sello es el recurso mas escaso del juego y por eso es el que menos reglas
trae. La forma esta copiada del objeto a proposito (ver `objetos.py`):

- **no gasta el turno**, asi que usarlo no es tu decision; despues sigues
  teniendo que elegir tu accion,
- no da mana ni se enfria,
- y lo que hace sale de perillas que el combate ya tenia.

Lo que cambia es de donde viene el tope. Un objeto se compra con oro y el tope
es **uno por batalla**; un Sello no se compra en ninguna parte: son **tres para
toda la guerra** (`war.SELLOS_POR_MASTER`, cinco en la ficha de Jeanne), y
encima **uno por batalla**. Los dos topes viven en el `Master`
(`sellos` y `sellos_en_la_batalla`), porque son suyos y una batalla no sabe de
Masters: los comprueba el Cog antes de llamar, igual que con el inventario.

Por que un Sello da mas que una habilidad, si no cuesta el turno: porque se
acaba. Un objeto se vuelve a comprar y una habilidad se vuelve a enfriar; un
Sello gastado no vuelve, asi que el precio no es el turno, es que te queden
dos. Esa es toda la economia.

**Los tres usos son una lista cerrada** y es a proposito: igual que un rasgo
solo puede mover las perillas de `personajes.py`, un Sello solo puede hacer
una de estas tres cosas, y asi no hay forma de que un Sello invente una regla
nueva de combate.

Lo que **no** es un Sello, aunque estaba propuesto en los documentos: una
accion extra. Un turno se resuelve con todas las decisiones a la vez
(`battle.resolver_turno`), asi que "actua otra vez" no es un efecto, es un
turno dentro de un turno, y eso si seria una regla nueva en el motor. Llenar
la barra de mana es la version de eso que si cabe: no te da un turno de mas,
te deja gastar el que tienes en el Noble Fantasma.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .personajes import Efecto

# Cuantos se pueden gastar en una misma batalla. El tope de la guerra son
# `war.SELLOS_POR_MASTER`; este es el que impide gastarlos los tres en un
# turno, que convertiria tres decisiones de la guerra en una sola.
SELLOS_POR_BATALLA = 1

# Cuanto cura el Sello, en parte de la vida maxima. **Numero razonado y no
# medido**, como `objetos.VALOR_POR_EFECTO_DE_OBJETO`, y por la misma razon: la
# IA no usa Sellos, asi que el simulador no puede decir si estan bien. La
# referencia es la habilidad de curar (0.12 de la vida maxima, gastando el
# turno): un Sello cura mas del triple y no gasta nada, y a cambio solo hay
# tres en toda la guerra. Esta en puntos-abiertos.md junto al de los objetos.
CURACION_DEL_SELLO = 0.40


class Uso(Enum):
    """Lo que se le puede pedir a un Sello. Lista cerrada."""

    # El confirmado desde el principio: llena la barra para que el Noble
    # Fantasma se pueda lanzar **este** turno.
    MANA = "mana"
    CURAR = "curar"
    # Apaga los enfriamientos: tus habilidades vuelven a estar listas. Es el
    # unico que no se nota en ningun numero del combatiente, y el mas
    # interesante de los tres, porque deja repetir la habilidad buena.
    ENFRIAMIENTOS = "enfriamientos"


@dataclass(frozen=True)
class Sello:
    """Un uso concreto, con el nombre de sus frases y el efecto que toca.

    `efecto`, `valor` y `turnos` estan aqui para que `CURAR` pase por el mismo
    `battle._aplicar_efecto` que una habilidad o un objeto, sin una segunda
    copia de la misma cuenta. Los otros dos usos no son un efecto de los diez
    (el mana no se suma, se llena; y los enfriamientos no son un bono), asi que
    los resuelve `battle.usar_sello` en dos lineas.
    """

    uso: Uso
    efecto: Efecto = Efecto.NINGUNO
    valor: float = 0.0
    turnos: int = 0

    @property
    def clave(self) -> str:
        return self.uso.value

    def nombre_para(self, idioma: str) -> str:
        from .textos import t

        return t(f"sello.{self.clave}.nombre", idioma)

    def descripcion(self, idioma: str) -> str:
        from .textos import t

        return t(f"sello.{self.clave}.descripcion", idioma)


SELLOS = {
    Uso.MANA: Sello(uso=Uso.MANA),
    Uso.CURAR: Sello(uso=Uso.CURAR, efecto=Efecto.CURAR, valor=CURACION_DEL_SELLO),
    Uso.ENFRIAMIENTOS: Sello(uso=Uso.ENFRIAMIENTOS),
}


def sello(clave: str) -> Sello | None:
    """El Sello de una clave, o `None` si no es ninguno de los tres."""
    try:
        return SELLOS[Uso(clave)]
    except (ValueError, KeyError):
        return None


def lista() -> list[Sello]:
    """Los tres, siempre en el mismo orden."""
    return [SELLOS[u] for u in Uso]
