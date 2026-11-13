"""La tienda y las dos monedas: oro y griales.

Logica pura, sin Discord. Aqui estan los precios, lo que paga cada cosa y las
comprobaciones de una compra; quien aprieta el boton es el Cog.

## Por que dos monedas y no una

Las dos monedas no son dos formas de lo mismo: **miden cosas distintas y por
eso duran distinto**.

- **El oro mide lo que trabajaste en esta guerra.** Lo da ganarle a un NPC de
  entrenamiento y ganar una batalla, y **se pierde cuando la guerra acaba**.
  Compra objetos de combate y de preparacion, que tambien son de esta guerra.
  Guardarlo entre guerras lo convertiria en una cuenta de ahorros: el que
  llevara diez guerras empezaria la once con todo comprado, y una guerra nueva
  dejaria de empezar empatada.
- **Los griales miden las guerras que ganaste.** Solo los da ganar una guerra,
  **y se quedan en la cuenta del Master para siempre**. Compran catalizadores,
  que apuntan la invocacion: lo unico que vale la pena arrastrar de una guerra
  a la siguiente es el derecho a elegir con quien entras en la proxima.

Por eso el oro vive en el `Master` (que muere con la guerra) y los griales en
una `Cuenta` (que vive en la tabla `cuentas`, por usuario y no por guerra).

## El grial lo paga `Guerra.grial()`, no `ganador()`

Y eso **cierra el agujero** mas obvio de todo esto: una guerra necesita 4
personas de verdad para entregar el Grial (`MINIMO_HUMANOS_PARA_GRIAL`), asi
que abrir una guerra solo contra 6 bots, ganarla y cobrar no se puede. No hubo
que inventar la regla porque ya estaba; solo hay que acordarse de pagar por
donde se entrega el Grial y no por donde queda uno en pie.

## Los precios: de donde salen los numeros

**Lo que no cuesta el turno se paga con oro.** El precio de un objeto sigue lo
que da, con dos excepciones razonadas que estan en el comentario de cada una:
el critico es el efecto mas flojo que tenemos y el reloj de arena tiene que
costar **mas** de lo que devuelve, o seria una maquina de hacer oro.

**Medido** con `python -m src.simulator --semilla 7 economia -n 200`: una
guerra de 4 personas dura 3.9 dias y deja **216 de oro de media** por Master
(90 el decil bajo, 195 la mediana, 400 el decil alto), y sale igual con 1 o
con 7 personas en la mesa (206 y 220), porque el oro sale casi todo de
entrenar. Con eso se compran de 3 a 5 objetos, y en una guerra de 4 dias solo
se pueden **usar** 4 objetos de combate (uno por batalla). O sea: da justo
para ir armado a tus batallas y poco mas, que es lo que se buscaba. Comprarlo
todo cuesta 450, dos guerras: inalcanzable a proposito.

Lo que esto **no** mide es si los valores de los objetos estan bien, porque la
IA no los usa. Eso sigue abierto y esta en `puntos-abiertos.md`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .clases import Clase
from .objetos import (
    Momento,
    Objeto,
    TOPE_INVENTARIO,
    catalizador_de_clase,
    catalizador_de_servant,
    objeto,
)

# --- lo que paga cada cosa ---

# Oro por ganarle a cada NPC de la escalera, por indice (0 es el primero). Va
# de menos a mas como la XP y como la probabilidad de suelta: pelear arriba
# tiene que pagar mas, o nadie pelearia arriba.
ORO_POR_NPC = {0: 10, 1: 15, 2: 20, 3: 30}
ORO_POR_NPC_POR_DEFECTO = 10

# Oro por salir en pie de una batalla que tumbo a alguien. Es mas que el NPC
# mas duro porque es mas raro: hay una batalla al dia como mucho, y a veces
# ninguna. Una batalla que acaba en empate (nadie cayo) no paga: lo que se
# cobra es ganar, no estar.
ORO_POR_BATALLA_GANADA = 50

# Griales por ganar una guerra que entrega el Grial. Con esto, ganar una
# guerra es exactamente un catalizador de clase, y uno de Servant son tres
# guerras: lo justo para que la diferencia entre 2 y 5 se note de verdad.
GRIALES_POR_GUERRA = 2


class Moneda(Enum):
    ORO = "oro"
    GRIALES = "griales"


# --- los precios ---

# Un objeto por clave. No esta en `objetos.json` a proposito: el precio es un
# numero de balance, y los numeros de balance viven en el codigo, como
# `VALOR_POR_EFECTO_DE_OBJETO`. El catalogo dice que hay; el juego, cuanto vale.
PRECIO_EN_ORO = {
    # Combate. Referencia medida (ver la cabecera): una guerra deja 216 de oro
    # de media, y solo se puede usar un objeto por batalla, o sea 4 en toda la
    # guerra. A estos precios eso son 3 o 4 objetos: se puede ir armado a cada
    # batalla, pero no armado y sobrado.
    "ojo_certero": 40,  # el critico es el efecto mas flojo que tenemos (ver
    # `puntos-abiertos.md`), asi que es el mas barato
    "piedra_furia": 50,
    "escama_guardian": 50,
    "gema_mana": 70,  # 40 de los 100 del Noble Fantasma: lo que mas acerca el
    # turno que de verdad decide una batalla
    "elixir": 70,  # lo unico que te saca de caer
    # Preparacion.
    "vendaje": 40,  # situacional: solo vale si entrenaste mal
    "tomo_saber": 60,  # 25 de XP, algo mas que ganar un NPC
    "reloj_arena": 70,  # **tiene que costar mas de 30**, que es lo que paga el
    # NPC mas duro: si costara menos, comprarlo y pelear
    # daria oro, y una tienda que fabrica oro no es una
    # tienda. Se compra por la XP y el objeto, no por el oro.
}

# En griales, y estos los puso Cristopher: una clase, 2; un Servant, 5.
PRECIO_CATALIZADOR_CLASE = 2
PRECIO_CATALIZADOR_SERVANT = 5


def precio_de(o: Objeto) -> tuple[int, Moneda] | None:
    """Lo que cuesta y en que moneda. `None` si no se vende."""
    if o.momento is Momento.INVOCACION:
        if o.clase is not None:
            return PRECIO_CATALIZADOR_CLASE, Moneda.GRIALES
        return PRECIO_CATALIZADOR_SERVANT, Moneda.GRIALES
    oro = PRECIO_EN_ORO.get(o.clave)
    return (oro, Moneda.ORO) if oro is not None else None


def a_la_venta(momento: Momento | None = None) -> list[Objeto]:
    """Lo que se compra con oro, en orden de precio y luego de clave.

    Los catalizadores no salen aqui: no son una lista cerrada (hay uno por
    cada Servant del plantel) y se pagan con otra moneda, asi que el menu los
    ofrece por su lado.
    """
    fichas = []
    for clave in PRECIO_EN_ORO:
        o = objeto(clave)
        if o is None:
            # Una clave con precio que ya no esta en el catalogo. No es un
            # error que valga reventar: simplemente no se vende.
            continue
        if momento is None or o.momento is momento:
            fichas.append(o)
    fichas.sort(key=lambda o: (PRECIO_EN_ORO[o.clave], o.clave))
    return fichas


# --- la cuenta: lo unico que sobrevive a una guerra ---


@dataclass
class Cuenta:
    """Los griales de un Master, fuera de cualquier guerra.

    Es lo unico del juego que no muere con la guerra, asi que va en su propia
    tabla (`cuentas`, por `usuario_id`) y no dentro de la guerra. Una cuenta
    que no existe todavia es una cuenta a 0: no hay que crearla para poder
    preguntarle.
    """

    usuario_id: str
    griales: int = 0
    # Cuantas guerras gano. No se gasta, es para poder ensenarlo.
    guerras_ganadas: int = 0

    def puede_pagar(self, cuantos: int) -> bool:
        return self.griales >= cuantos

    def cobrar(self, cuantos: int) -> bool:
        """Quita griales. `False` si no llegaban, y entonces no quita nada."""
        if cuantos < 0 or not self.puede_pagar(cuantos):
            return False
        self.griales -= cuantos
        return True

    def ingresar(self, cuantos: int) -> None:
        if cuantos > 0:
            self.griales += cuantos

    def ganar_guerra(self, griales: int = GRIALES_POR_GUERRA) -> int:
        """Apunta una guerra ganada y paga. Devuelve lo que pago."""
        self.guerras_ganadas += 1
        self.ingresar(griales)
        return max(0, griales)


# --- comprar ---


class Fallo(Enum):
    """Por que no se pudo comprar. Cada uno tiene su frase."""

    NO_SE_VENDE = "no_se_vende"
    SIN_ORO = "sin_oro"
    SIN_GRIALES = "sin_griales"
    INVENTARIO_LLENO = "inventario_lleno"
    NO_EXISTE = "no_existe"


@dataclass(frozen=True)
class Compra:
    """Como fue el intento. `ok` y nada mas no basta: hay que poder decir por que."""

    ok: bool
    objeto: Objeto | None = None
    pagado: int = 0
    moneda: Moneda | None = None
    fallo: Fallo | None = None


def comprar_con_oro(master, clave: str) -> Compra:
    """Compra un objeto de oro y lo mete en el inventario.

    El orden importa, y es el mismo de `usar_objeto_en_preparacion`: primero
    se comprueba **todo**, y solo despues se cobra y se entrega. Asi no hay
    forma de cobrar sin entregar, que es el unico error de una tienda que de
    verdad enfada.
    """
    o = objeto(clave)
    if o is None:
        return Compra(ok=False, fallo=Fallo.NO_EXISTE)
    tarifa = precio_de(o)
    if tarifa is None or tarifa[1] is not Moneda.ORO:
        return Compra(ok=False, objeto=o, fallo=Fallo.NO_SE_VENDE)
    cuanto, moneda = tarifa
    if master.oro < cuanto:
        return Compra(ok=False, objeto=o, fallo=Fallo.SIN_ORO)
    if master.inventario.lleno:
        return Compra(ok=False, objeto=o, fallo=Fallo.INVENTARIO_LLENO)
    if not master.inventario.anadir(clave):
        return Compra(ok=False, objeto=o, fallo=Fallo.INVENTARIO_LLENO)
    master.oro -= cuanto
    return Compra(ok=True, objeto=o, pagado=cuanto, moneda=moneda)


def comprar_catalizador(master, cuenta: Cuenta, o: Objeto | None) -> Compra:
    """Compra un catalizador con griales. Mismo orden: comprobar, cobrar, dar.

    Se le pasa la ficha ya armada (`catalizador_de_clase` /
    `catalizador_de_servant`) en vez de una clave, porque los de Servant no
    estan en el catalogo: hay 348 y se arman al pedirlos.
    """
    if o is None or o.momento is not Momento.INVOCACION:
        return Compra(ok=False, objeto=o, fallo=Fallo.NO_SE_VENDE)
    tarifa = precio_de(o)
    if tarifa is None:
        return Compra(ok=False, objeto=o, fallo=Fallo.NO_SE_VENDE)
    cuanto, moneda = tarifa
    if not cuenta.puede_pagar(cuanto):
        return Compra(ok=False, objeto=o, fallo=Fallo.SIN_GRIALES)
    if master.inventario.lleno:
        return Compra(ok=False, objeto=o, fallo=Fallo.INVENTARIO_LLENO)
    if not master.inventario.anadir(o.clave):
        return Compra(ok=False, objeto=o, fallo=Fallo.INVENTARIO_LLENO)
    cuenta.cobrar(cuanto)
    return Compra(ok=True, objeto=o, pagado=cuanto, moneda=moneda)


# --- lo que paga el juego ---


def oro_por_npc(indice: int) -> int:
    return ORO_POR_NPC.get(indice, ORO_POR_NPC_POR_DEFECTO)


__all__ = [
    "Compra",
    "Cuenta",
    "Fallo",
    "GRIALES_POR_GUERRA",
    "Moneda",
    "ORO_POR_BATALLA_GANADA",
    "ORO_POR_NPC",
    "PRECIO_CATALIZADOR_CLASE",
    "PRECIO_CATALIZADOR_SERVANT",
    "PRECIO_EN_ORO",
    "TOPE_INVENTARIO",
    "a_la_venta",
    "catalizador_de_clase",
    "catalizador_de_servant",
    "comprar_catalizador",
    "comprar_con_oro",
    "oro_por_npc",
    "precio_de",
]
