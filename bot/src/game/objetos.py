"""Los objetos que un Master puede llevar, y su inventario.

Esto es el equivalente de `personajes.py` para los objetos, y sigue las mismas
tres reglas de la casa, que aqui valen por lo mismo:

**Un objeto hace una sola cosa, de una lista cerrada.** Nada de objetos que
inventen una regla nueva: cada uno mueve una perilla que el juego ya tiene. Por
eso los de combate reusan los cinco efectos de `personajes.Efecto` y no definen
ninguno propio.

**Los datos dicen que efecto tiene; el juego dice cuanto da.** El catalogo
(`bot/data/objetos.json`) trae el nombre y el efecto; las magnitudes estan
aqui, en `VALOR_POR_EFECTO_DE_OBJETO`. Asi un objeto nuevo no puede traer un
numero roto, y afinar el balance se hace en un sitio.

**Se valida al cargar.** Un objeto que no cuadra no entra, igual que un
personaje que no suma 3.00.

## Los tres momentos

Un objeto se usa en un momento y solo en uno, y de el sale que puede hacer:

- `COMBATE`: dentro de una batalla. Los cinco efectos de siempre (ataque,
  defensa, critico, mana, curar). **Usarlo no cuesta el turno**, al contrario
  que una habilidad: atacas igual. Eso es lo que los hace valer la pena, y por
  eso son escasos (`OBJETOS_POR_BATALLA`).
- `PREPARACION`: durante el dia, antes de las batallas. Su lista cerrada es
  `EfectoFuera`, y son cosas que el dia ya sabe hacer: dar XP, quitar la
  penalizacion de vida por perder contra un NPC, dar un combate NPC mas.
- `INVOCACION`: los catalizadores, que apuntan la invocacion a una clase o a
  un Servant concreto. Se compran con griales en `tienda.py`. **Lo que pasa al
  usarlos esta sin cerrar**: Cristopher va a explicar la mecanica. Aqui esta
  la forma (a que apunta cada uno) y en la tienda el precio, para que el
  catalogo, el inventario y la compra ya los sepan llevar.

## Los catalizadores de Servant no estan en el catalogo

Los de clase son 8 y estan en `objetos.json` como cualquier otro. Los de
Servant serian 348, uno por personaje, asi que **se arman al pedirlos**
(`catalizador_de_servant`) y su clave lleva el numero dentro:
`catalizador_servant:91`. `objeto()` sabe reconocer esa forma, asi que un
inventario guardado con uno dentro se lee igual que cualquier otro.

La clave lleva el `collectionNo` y no el nombre por lo mismo que siempre: los
nombres no son unicos (hay dos Cu Chulainn) y se traducen.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .clases import Clase
from .personajes import Efecto

RUTA_CATALOGO = Path(__file__).resolve().parent.parent.parent / "data" / "objetos.json"


class Momento(Enum):
    """Cuando se puede usar un objeto. De aqui sale que puede hacer."""

    COMBATE = "combate"
    PREPARACION = "preparacion"
    INVOCACION = "invocacion"


class EfectoFuera(Enum):
    """Lo que puede hacer un objeto de preparacion. Lista cerrada.

    Las tres son cosas que el dia ya sabe hacer, asi que ningun objeto de
    estos necesita codigo nuevo en el combate:

    - `XP`: experiencia, la misma moneda que da entrenar.
    - `CURAR_ANTES`: borra las derrotas contra NPC del dia, que es lo que te
      quita vida en la batalla (ver `npc.vida_inicial`). Es la red para el que
      entreno mal y no quiere ir a la batalla a medias.
    - `COMBATE_EXTRA`: un intento de entrenamiento mas, por encima de los 4.
    """

    XP = "xp"
    CURAR_ANTES = "curar_antes"
    COMBATE_EXTRA = "combate_extra"


# --- cuanto da cada cosa: numeros del juego, no del catalogo ---

# Un objeto de combate **no cuesta el turno** y una habilidad si. Esa es la
# diferencia que manda: los valores de `personajes.VALOR_POR_EFECTO` son
# grandes (x2.5 al ataque) precisamente porque pagan el ataque que dejas de
# hacer. Un objeto no paga nada, asi que con los mismos numeros seria una
# habilidad gratis, o sea estrictamente mejor que cualquier habilidad.
#
# Se parte de dos tercios del valor de la habilidad y se mide. La escasez hace
# el resto: uno por batalla.
FRACCION_DE_LA_HABILIDAD = 2 / 3

# Los cuatro efectos del 2026-11-09 (esquivar, aguantar, y los dos negativos)
# **no estan aqui a proposito**, y por eso un objeto no puede tenerlos: un
# objeto no cuesta el turno, asi que un frasco que esquiva un golpe o que le
# baja la defensa al rival seria una habilidad gratis, y esos cuatro son justo
# los que peor aguantan ser gratis. Si algun dia entran, primero hay que medir
# los objetos, que es lo unico del combate que sigue sin medir.
VALOR_POR_EFECTO_DE_OBJETO = {
    Efecto.ATAQUE: 1.00,  # pega x2 el turno siguiente (la habilidad da x2.5)
    Efecto.DEFENSA: 0.25,  # recibe un cuarto menos (la habilidad, un tercio)
    Efecto.CRITICO: 0.30,  # +30 puntos de probabilidad
    Efecto.MANA: 40.0,  # 40 de los 100 del Noble Fantasma
    Efecto.CURAR: 0.20,  # 20% de la vida maxima: mas que la habilidad, porque
    # curar no se beneficia de durar turnos y es lo que
    # de verdad te salva de caer
}

TURNOS_POR_EFECTO_DE_OBJETO = {
    Efecto.ATAQUE: 1,
    Efecto.DEFENSA: 3,
    Efecto.CRITICO: 3,
    Efecto.MANA: 0,
    Efecto.CURAR: 0,
}

VALOR_POR_EFECTO_FUERA = {
    EfectoFuera.XP: 25,  # algo mas de lo que da ganar un combate NPC
    EfectoFuera.CURAR_ANTES: 0,  # no necesita numero: borra las derrotas
    EfectoFuera.COMBATE_EXTRA: 1,
}

# Cuantos objetos se pueden usar en una batalla. Es lo que los mantiene siendo
# una decision: con uno, usarlo es elegir el turno en el que lo usas.
OBJETOS_POR_BATALLA = 1

# Cuantos caben en el inventario, contando repetidos. No es realismo, es que
# el menu de Discord no puede ensenar una lista infinita: un desplegable
# aguanta 25 opciones.
TOPE_INVENTARIO = 25

# La probabilidad de que ganar suelte algo **no esta aqui**: la tiene `npc.py`
# en `PROB_OBJETO`, y ademas por NPC (el 4.º suelta el 40% de las veces y el
# 1.º el 10%), que es mejor que un numero plano porque premia pelear arriba.
# Aqui solo se sortea **que** sale cuando ya se decidio que sale algo.


@dataclass(frozen=True)
class Objeto:
    """Un objeto del catalogo. Es una ficha, no una posesion.

    Lo que un Master tiene es un `Inventario`, que guarda cuantos lleva de
    cada clave. La `clave` es el identificador estable, el equivalente del
    `collection_no` de un personaje: los nombres se traducen y el nombre no
    sirve de clave.
    """

    clave: str
    momento: Momento
    # Solo uno de los tres, segun el momento.
    efecto: Efecto | None = None  # COMBATE
    efecto_fuera: EfectoFuera | None = None  # PREPARACION
    clase: Clase | None = None  # INVOCACION, si apunta a una clase
    collection_no: int | None = None  # INVOCACION, si apunta a un Servant
    # Cuanto pesa en la suelta. Mas peso, mas comun.
    peso: int = 10

    @property
    def valor(self) -> float:
        """Cuanto da, segun su efecto. Sale del juego, no del catalogo."""
        if self.efecto is not None:
            return VALOR_POR_EFECTO_DE_OBJETO.get(self.efecto, 0.0)
        if self.efecto_fuera is not None:
            return float(VALOR_POR_EFECTO_FUERA.get(self.efecto_fuera, 0))
        return 0.0

    @property
    def turnos(self) -> int:
        if self.efecto is None:
            return 0
        return TURNOS_POR_EFECTO_DE_OBJETO.get(self.efecto, 0)

    @property
    def instantaneo(self) -> bool:
        return self.turnos == 0

    @property
    def es_catalizador_de_servant(self) -> bool:
        return self.momento is Momento.INVOCACION and self.collection_no is not None

    @property
    def clave_de_texto(self) -> str:
        """La clave con la que buscar su nombre en los textos.

        Para casi todos es su propia clave. Los catalizadores de Servant
        comparten una sola frase con un hueco para el nombre, porque son 348 y
        no se van a traducir uno por uno.
        """
        if self.es_catalizador_de_servant:
            return PREFIJO_CATALIZADOR_SERVANT
        return self.clave

    def nombre_para(self, idioma: str | None = None) -> str:
        """El nombre que lee el jugador, de `textos.json`.

        Ninguna frase que lea el jugador se escribe en el codigo ni en el
        catalogo: el catalogo trae la clave y el texto vive en los textos.
        """
        from .textos import t

        return t(
            f"objeto.{self.clave_de_texto}.nombre", idioma, servant=self._servant()
        )

    def descripcion(self, idioma: str | None = None) -> str:
        from .textos import t

        return t(
            f"objeto.{self.clave_de_texto}.desc",
            idioma,
            valor=self._valor_legible(),
            servant=self._servant(),
        )

    def _servant(self) -> str:
        """El nombre del Servant al que apunta, si apunta a uno.

        Se busca en el plantel por `collectionNo`. Si el plantel ya no lo
        tiene (se reimporto y el personaje se cayo), se ensena el numero: es
        feo, pero es mejor que reventar al abrir el inventario.
        """
        if self.collection_no is None:
            return ""
        return _nombre_del_plantel(self.collection_no) or f"#{self.collection_no}"

    def _valor_legible(self) -> str:
        """El valor como lo lee una persona: 100% en vez de 1.0."""
        if self.efecto in (Efecto.ATAQUE, Efecto.DEFENSA, Efecto.CRITICO, Efecto.CURAR):
            return f"{self.valor * 100:.0f}"
        return f"{self.valor:.0f}"

    def validar(self) -> None:
        """Un objeto que no cuadra no entra. Igual que un personaje."""
        cuales = [
            x
            for x in (self.efecto, self.efecto_fuera, self.clase, self.collection_no)
            if x is not None
        ]
        if len(cuales) != 1:
            raise ValueError(
                f"el objeto {self.clave} hace {len(cuales)} cosas y un objeto "
                f"hace una sola: efecto, efecto_fuera, clase o collection_no"
            )
        esperado = {
            Momento.COMBATE: self.efecto is not None,
            Momento.PREPARACION: self.efecto_fuera is not None,
            Momento.INVOCACION: self.clase is not None
            or self.collection_no is not None,
        }[self.momento]
        if not esperado:
            raise ValueError(
                f"el objeto {self.clave} se usa en {self.momento.value} pero no "
                f"hace nada de lo que ese momento permite"
            )
        if self.efecto is Efecto.NINGUNO:
            raise ValueError(
                f"el objeto {self.clave} no hace nada: NINGUNO vale para una "
                f"habilidad de FGO que no supimos traducir, no para un objeto"
            )
        if self.peso < 0:
            raise ValueError(f"el objeto {self.clave}: el peso no puede ser negativo")


# --- el catalogo ---


def objeto_desde(d: dict) -> Objeto:
    momento = Momento(d["momento"])
    o = Objeto(
        clave=d["clave"],
        momento=momento,
        efecto=Efecto(d["efecto"]) if d.get("efecto") else None,
        efecto_fuera=EfectoFuera(d["efecto_fuera"]) if d.get("efecto_fuera") else None,
        clase=Clase(d["clase"]) if d.get("clase") else None,
        collection_no=d.get("collectionNo"),
        peso=int(d.get("peso", 10)),
    )
    o.validar()
    return o


def cargar(ruta: Path | str | None = None) -> list[Objeto]:
    """Carga el catalogo y valida cada objeto."""
    camino = Path(ruta or RUTA_CATALOGO)
    if not camino.exists():
        return []
    bruto = json.loads(camino.read_text(encoding="utf-8"))
    objetos = [objeto_desde(d) for d in bruto.get("objetos", [])]
    claves = Counter(o.clave for o in objetos)
    repetidas = [c for c, n in claves.items() if n > 1]
    if repetidas:
        raise ValueError(
            f"hay claves de objeto repetidas: {', '.join(sorted(repetidas))}. "
            f"La clave es el identificador y tiene que ser unica."
        )
    return objetos


CATALOGO = cargar()
POR_CLAVE = {o.clave: o for o in CATALOGO}

# --- los catalizadores ---

# La clave de un catalizador de Servant es este prefijo, dos puntos y el
# collectionNo: `catalizador_servant:91`. Es la unica clave de objeto que se
# arma y no se lee del catalogo, porque serian 348 fichas iguales.
PREFIJO_CATALIZADOR_SERVANT = "catalizador_servant"
SEPARADOR_DE_CLAVE = ":"

# El plantel, solo si hace falta. Un catalizador de Servant necesita el nombre
# del personaje para poder ensenarse, y cargar 348 fichas para eso solo tiene
# sentido si alguien tiene uno. Se guarda en cuanto se carga una vez.
_PLANTEL: dict[int, str] | None = None


def _nombre_del_plantel(collection_no: int) -> str | None:
    global _PLANTEL
    if _PLANTEL is None:
        from .personajes import cargar as cargar_plantel

        _PLANTEL = {
            p.collection_no: p.nombre
            for p in cargar_plantel()
            if p.collection_no is not None
        }
    return _PLANTEL.get(collection_no)


def catalizador_de_clase(clase: Clase) -> Objeto | None:
    """El catalizador que apunta a esa clase. Esta en el catalogo."""
    for o in CATALOGO:
        if o.momento is Momento.INVOCACION and o.clase is clase:
            return o
    return None


def catalizador_de_servant(collection_no: int) -> Objeto | None:
    """El catalizador que apunta a ese Servant. Se arma al pedirlo.

    Devuelve `None` si el numero no esta en el plantel: comprar un catalizador
    de un Servant que no existe seria pagar 5 griales por nada, y 5 griales son
    tres guerras ganadas.
    """
    if collection_no is None or _nombre_del_plantel(int(collection_no)) is None:
        return None
    return Objeto(
        clave=(
            f"{PREFIJO_CATALIZADOR_SERVANT}{SEPARADOR_DE_CLAVE}{int(collection_no)}"
        ),
        momento=Momento.INVOCACION,
        collection_no=int(collection_no),
        peso=0,  # no se suelta, se compra
    )


def objeto(clave: str) -> Objeto | None:
    """La ficha de una clave, sea del catalogo o armada.

    Los catalizadores de Servant no estan en el catalogo, asi que se
    reconocen por la forma de la clave. Que esto viva aqui y no en cada sitio
    que lee un inventario es lo que hace que `Inventario.lista()`,
    `usar_objeto_en_combate` y la tienda no tengan que saber nada del caso
    especial.
    """
    directo = POR_CLAVE.get(clave)
    if directo is not None:
        return directo
    prefijo = f"{PREFIJO_CATALIZADOR_SERVANT}{SEPARADOR_DE_CLAVE}"
    if not clave.startswith(prefijo):
        return None
    resto = clave[len(prefijo) :]
    if not resto.isdigit():
        return None
    return catalizador_de_servant(int(resto))


def sueltos(momento: Momento | None = None) -> list[Objeto]:
    """Los que pueden salir de una suelta.

    Los catalizadores **no** se sueltan al entrenar: apuntan la invocacion, y
    la invocacion es del dia 1, asi que ganarlos entrenando llegaria tarde.
    Como se consiguen esta sin decidir, con la mecanica.
    """
    fuera = [o for o in CATALOGO if o.momento is not Momento.INVOCACION]
    if momento is None:
        return fuera
    return [o for o in fuera if o.momento is momento]


def sortear(rng: random.Random, momento: Momento | None = None) -> Objeto | None:
    """Un objeto al azar, pesado por `peso`. `None` si no hay catalogo."""
    posibles = sueltos(momento)
    if not posibles:
        return None
    return rng.choices(posibles, weights=[o.peso for o in posibles], k=1)[0]


# --- el inventario ---


@dataclass
class Inventario:
    """Lo que lleva un Master. Cuenta repetidos y tiene tope.

    Guarda claves y no `Objeto` a proposito: es lo que se guarda en la base de
    datos, y asi un catalogo que cambie no deja inventarios con fichas que ya
    no existen dentro. Al leer se buscan en el catalogo, y una clave que ya no
    este simplemente no se ve.
    """

    cuantos: dict[str, int] = field(default_factory=dict)
    # Cuantos ha usado en la batalla de hoy. Se reinicia con el dia.
    usados_en_la_batalla: int = 0

    @property
    def total(self) -> int:
        return sum(self.cuantos.values())

    @property
    def lleno(self) -> bool:
        return self.total >= TOPE_INVENTARIO

    @property
    def vacio(self) -> bool:
        return self.total == 0

    def cuantos_de(self, clave: str) -> int:
        return self.cuantos.get(clave, 0)

    def tiene(self, clave: str) -> bool:
        return self.cuantos_de(clave) > 0

    def anadir(self, clave: str, cuantos: int = 1) -> bool:
        """Mete objetos. Devuelve `False` si no cabian y no mete nada.

        No revienta cuando esta lleno: una suelta que llega con el inventario
        a tope no puede romperle el dia a nadie. Quien llame decide si lo
        cuenta o se calla.
        """
        if cuantos <= 0 or self.total + cuantos > TOPE_INVENTARIO:
            return False
        self.cuantos[clave] = self.cuantos_de(clave) + cuantos
        return True

    def quitar(self, clave: str, cuantos: int = 1) -> bool:
        """Saca objetos. Devuelve `False` si no los tenia."""
        if cuantos <= 0 or self.cuantos_de(clave) < cuantos:
            return False
        resto = self.cuantos_de(clave) - cuantos
        if resto:
            self.cuantos[clave] = resto
        else:
            # Se borra la clave en vez de dejarla en 0: asi `lista()` y la
            # base de datos no arrastran objetos que no se tienen.
            del self.cuantos[clave]
        return True

    def lista(self, momento: Momento | None = None) -> list[tuple[Objeto, int]]:
        """Lo que lleva, con su ficha y cuantos, en orden estable.

        Las claves que ya no estan en el catalogo se saltan: el catalogo puede
        cambiar y un inventario guardado no tiene por que saberlo.
        """
        fichas = []
        for clave, n in self.cuantos.items():
            o = objeto(clave)
            if o is not None and (momento is None or o.momento is momento):
                fichas.append((o, n))
        fichas.sort(key=lambda x: (x[0].momento.value, x[0].clave))
        return fichas

    @property
    def puede_usar_en_la_batalla(self) -> bool:
        return self.usados_en_la_batalla < OBJETOS_POR_BATALLA

    def nueva_batalla(self) -> None:
        self.usados_en_la_batalla = 0
