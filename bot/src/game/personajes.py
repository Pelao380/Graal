"""Fichas de personaje: estadisticas, rasgo, habilidades y Noble Fantasma.

Cada Servant invocado es un personaje concreto. Las estadisticas y el rasgo
son suyos, no de su clase.

Los personajes viven en `data/personajes.json`, no en el codigo: se pueden
anadir, corregir o retirar sin tocar el juego.

Presupuesto de estadisticas
---------------------------
Para que ningun personaje nazca roto, las tres estadisticas se expresan como
multiplicadores sobre una base comun y **deben sumar 3.00**. Un personaje con
mas vida tiene que pagarlo en ataque o en velocidad. `validar()` lo comprueba
y revienta si alguien se pasa, asi que el error se ve al cargar y no en medio
de una guerra.

Habilidades
-----------
Cada personaje tiene 3, y cada una es un solo efecto de una lista cerrada
(`Efecto`), sobre un solo objetivo (`Objetivo`). Igual que con los rasgos, una
habilidad solo puede mover las perillas que existen aqui: asi un personaje
nuevo no puede inventar una regla que rompa el combate. Los valores salen del
importador, que traduce los efectos de FGO; cuanto pesan en el combate se
decide en `battle.py`, que es donde viven los numeros de balance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .clases import Clase
from .textos import idioma_valido, t, turnos as turnos_texto

DATOS = Path(__file__).resolve().parent.parent.parent / "data"

# El plantel completo, generado desde el export de Atlas Academy con
# tools/importar_servants.py. No se edita a mano.
RUTA_GENERADOS = DATOS / "personajes_generados.json"

# Los retoques escritos a mano (rasgos, habilidades, Nobles Fantasmas) que se
# aplican encima del plantel generado, emparejados por collectionNo. Asi
# reimportar el plantel no borra el trabajo a mano.
RUTA_CATALOGO = DATOS / "personajes.json"

# Base comun de nivel 1. Un personaje de 1.00/1.00/1.00 tiene exactamente esto.
BASE_VIDA = 1000
BASE_ATAQUE = 100
BASE_VELOCIDAD = 50

# Presupuesto: los tres multiplicadores suman esto.
PRESUPUESTO = 3.00
TOLERANCIA = 0.001

# Ningun multiplicador puede salirse de aqui, para que nada sea injugable ni
# absurdo aunque el presupuesto cuadre.
MULTIPLICADOR_MINIMO = 0.55
MULTIPLICADOR_MAXIMO = 1.35

# Crecimiento por nivel, proporcional a la ficha: un personaje resistente
# sigue siendo resistente al subir. Es plano a proposito: con un crecimiento
# fuerte, el nivel decide el combate solo y el triangulo deja de importar.
CRECIMIENTO_VIDA = 0.03
CRECIMIENTO_ATAQUE = 0.03
CRECIMIENTO_VELOCIDAD = 0.02


class Efecto(Enum):
    """Lo que puede hacer una habilidad. Es una lista cerrada a proposito.

    Cada efecto mueve una perilla que el combate ya tiene: el ataque, la
    reduccion de dano, la probabilidad de critico, el mana y la vida. Un
    efecto de FGO que no se pueda traducir a una de estas entra como NINGUNO
    y la habilidad solo gasta el turno, hasta que decidamos que hacer con el.

    Los cinco ultimos son del 2026-11-09 y son los que apuntan al rival o le
    cambian el final a un golpe:

    - EVASION esquiva el proximo golpe que te llegue, y se gasta con el.
    - AGUANTAR no deja que un golpe te tumbe: te quedas con un resto de vida.
    - BAJAR_ATAQUE, BAJAR_DEFENSA y BAJAR_MANA son los tres efectos negativos,
      y van al rival. Ninguno necesita reglas nuevas en el combate, porque los
      tres son la perilla de siempre al reves: los dos primeros se aplican
      como un bono de ATAQUE o DEFENSA **con el valor en negativo** sobre el
      otro, y las dos cuentas que ya existen (`ataque_actual` y el escudo de
      `_danar`) los leen igual; BAJAR_MANA es el espejo exacto de MANA, que
      tampoco era un bono: el mana es un numero y bajarlo es restar. Lo que si
      hizo falta es un suelo para los dos bonos, para que apilarlos no deje a
      nadie sin ataque.
    """

    NINGUNO = "ninguno"
    ATAQUE = "ataque"
    DEFENSA = "defensa"
    CRITICO = "critico"
    MANA = "mana"
    CURAR = "curar"
    EVASION = "evasion"
    AGUANTAR = "aguantar"
    BAJAR_ATAQUE = "bajar_ataque"
    BAJAR_DEFENSA = "bajar_defensa"
    BAJAR_MANA = "bajar_mana"


# Los que le pasan al rival, no a quien usa la habilidad. Solo sirven para
# saber que una habilidad es un ataque y no un regalo: la IA no se los echa a
# si misma y el texto los cuenta de otra forma.
EFECTOS_NEGATIVOS = (
    Efecto.BAJAR_ATAQUE,
    Efecto.BAJAR_DEFENSA,
    Efecto.BAJAR_MANA,
)

# A que bono se traduce cada efecto negativo **de los que son un bono**. El
# combate no sabe de efectos negativos: sabe de bonos de ataque y de defensa,
# y estos entran ahi con el signo cambiado. BAJAR_MANA no esta porque no es un
# bono: es instantaneo, como el MANA del que es espejo.
BONO_DEL_NEGATIVO = {
    Efecto.BAJAR_ATAQUE: Efecto.ATAQUE,
    Efecto.BAJAR_DEFENSA: Efecto.DEFENSA,
}


class Objetivo(Enum):
    """A quien se le puede dar una habilidad.

    En Graal no hay equipos: las alianzas son verbales y una batalla es de
    todos contra todos. Asi que "aliado" no es un bando, es cualquiera que el
    Master elija, y por eso un beneficio se puede regalar a quien quieras,
    con todo lo que eso tiene de jugoso para una traicion.
    """

    UNO_MISMO = "uno_mismo"  # solo a su portador
    ALIADO = "aliado"  # a quien elija el Master, incluido el mismo
    OTRO = "otro"  # a quien elija el Master, menos el mismo


# Los que ocurren de una vez y no duran turnos. BAJAR_MANA esta aqui por la
# misma razon que MANA: el mana es un numero, y restarlo pasa y se acaba.
EFECTOS_INSTANTANEOS = (Efecto.MANA, Efecto.CURAR, Efecto.BAJAR_MANA)

# Cuanto da cada efecto y cuanto dura. Son numeros del juego, no del
# personaje: una habilidad de ataque es la misma para todos, "el siguiente
# turno pegas x2.5". Los valores que trae FGO se descartan a proposito, porque
# estan calibrados para un juego donde usar una habilidad no cuesta el turno:
# alli un +9% de ataque durante 3 turnos tiene sentido, y aqui devuelve un
# tercio del ataque que se dejo de hacer (ver docs/decisiones.md).
#
# Los cinco estan puestos para que cada uso devuelva alrededor de un ataque y
# medio, que es lo que cuesta gastar el turno y algo mas. Una ficha escrita a
# mano puede traer su propio `valor` o `turnos` si algun personaje lo merece.
VALOR_POR_EFECTO = {
    Efecto.ATAQUE: 1.50,  # +150% de dano: pega x2.5
    Efecto.DEFENSA: 0.35,  # recibe un tercio menos
    Efecto.CRITICO: 0.45,  # +45 puntos de probabilidad, sobre el 15% de base
    # 60 es el unico que no se puede afinar fino, y conviene saber por que: la
    # IA solo usa una habilidad que devuelva mas de un ataque, y con la cuenta
    # de `ai._cuanto_paga` eso son exactamente 55 de mana. Por debajo no la usa
    # nunca y el efecto es letra muerta; por encima sube a saltos, porque el
    # mana esta cuantizado por turnos. Espejo a nivel 5: 55 -> 51.4% (o sea
    # "no la usa"), 60 -> 68.2%, 70 -> 62.6%, 100 -> 71.9%.
    #
    # Valio el 23.9% hasta que el Noble Fantasma dejo de tener tope de uno por
    # combate; ver "El Noble Fantasma se puede repetir" en docs/decisiones.md.
    Efecto.MANA: 60.0,
    Efecto.CURAR: 0.12,  # 12% de la vida maxima
    # Cuantos golpes esquiva. Uno, y por eso dura dos turnos: si esquivara
    # todo lo que llega mientras esta puesto, en una batalla de cuatro seria
    # tres ataques por el precio de uno. Medido: 62.1% en duelo espejo, y da
    # igual que dure 2, 3 o 5 turnos, porque lo que la acaba es el golpe que
    # esquiva y no el reloj.
    Efecto.EVASION: 1.0,
    # Con cuanta vida te quedas cuando un golpe te habria tumbado. Es una
    # parte de la maxima, como curar, pero no se cobra hasta que hace falta.
    #
    # Medido en duelo espejo (nivel 15, 40 personajes): 0.25 -> 54.5%, 0.30 ->
    # 64.8%, 0.35 -> 71.6%. 0.25 no paga el turno que cuesta y 0.35 pasa de lo
    # que da subirse el ataque (68.2%), asi que 0.30.
    Efecto.AGUANTAR: 0.30,
    # Los dos negativos, y **el intuitivo estaba mal**. Parecia que tenian que
    # dar menos que su version en positivo, porque apuntan a un rival y no a
    # los tres de una batalla de cuatro. Medido, es al contrario: un debuff
    # tiene que dar **mas**, porque el turno que gastas en ponerlo es un ataque
    # que no haces, y el bono no multiplica ese turno.
    #
    # Y los dos no se parecen tanto como parece. Bajarle el ataque al rival te
    # protege hagas tu lo que hagas, incluso el turno que gastas; bajarle la
    # defensa solo se cobra en los turnos en que le pegas. Por eso uno paga con
    # 0.40 y el otro necesita 0.60.
    #
    # La medida que decidio los dos numeros no es el duelo de una habilidad
    # sola, que engana: es **cada personaje que la lleva contra si mismo con
    # esa habilidad muerta**, con su kit entero y cuatro semillas (la
    # desviacion entre semillas es de un punto, asi que esto si es senal).
    # Porque una habilidad nueva no se compara con no hacer nada: compite con
    # las otras dos del personaje por el mismo turno.
    #
    #   bajar_ataque  0.40 -> 41.0%  (llevarla es **peor** que el hueco vacio)
    #   bajar_ataque  0.45 -> 46.3%
    #   bajar_ataque  0.50 -> 66.4%
    #   bajar_ataque  0.55 -> 92.9%  (la IA la prefiere a subirse el ataque)
    #   bajar_ataque  0.70 -> 94.6%
    #
    # El escalon de 0.50 a 0.55 es el umbral de la IA: 0.55 x 3 = 1.65 pasa de
    # los 1.50 que da subirse el ataque, asi que la elige primero y arrasa.
    #
    # **Y aun asi se queda en 0.40**, que es el unico numero de todo el combate
    # que esta puesto a sabiendas de que la IA lo juega regular. Las dos
    # medidas se contradicen y la regla de la casa desempata: la buena es la
    # del plantel.
    #
    #   bajar_ataque 0.40 -> plantel: desviacion 17.6%, 146 fuera, maximo 91.7%
    #   bajar_ataque 0.50 -> plantel: desviacion 18.3%, 158 fuera, maximo 97.2%
    #
    # O sea que el valor que hace que la habilidad pague su turno es el que
    # desparrama el plantel y corona a alguien al 97%. Se queda el que no
    # rompe la mesa, y lo que queda por arreglar no es este numero: es que la
    # IA mide mal la mitigacion, que es la misma razon por la que defenderse es
    # una accion debil. Esta en puntos-abiertos.md.
    #
    # 0.70 y 0.80 dan lo mismo que 0.60, y no es casualidad: `SUELO_BONO` de
    # battle.py esta en -0.60, asi que ahi topa.
    #
    # Y aun asi bajar_defensa se queda en 0.50 y no en 0.60, porque el duelo
    # espejo mide **una** habilidad y el plantel mide al personaje entero. Con
    # 0.60, Elisabeth Bathory (ataque + bajar_defensa + aguantar) ganaba el
    # **100.0%** de sus duelos a nivel 15: los multiplicadores de dano se
    # apilan y ella tiene los dos. Medido en el plantel a nivel 15:
    #
    #   0.60 -> desviacion 18.3%, 162 fuera de la banda, maximo 100.0%
    #   0.50 -> desviacion 17.6%, 146 fuera de la banda, maximo  91.7%
    #   0.45 -> desviacion 17.8%, 142 fuera de la banda, maximo  93.1%
    #
    # 0.50 es el unico que paga el turno (54.5% en duelo, o sea por encima del
    # 50% que da no usarla) sin dejar a nadie invencible. Es la regla de la
    # casa en una linea: la medida buena es la del plantel, no la de dos
    # personajes.
    Efecto.BAJAR_ATAQUE: 0.40,  # el rival pega un 40% menos
    Efecto.BAJAR_DEFENSA: 0.50,  # y recibe un 50% mas
    # Cuanto mana le quitas. El espejo de MANA, que da 60, y por eso se midio
    # empezando por 60: ver mas abajo.
    Efecto.BAJAR_MANA: 60.0,
}

TURNOS_POR_EFECTO = {
    Efecto.ATAQUE: 1,  # solo el turno siguiente, y pega como tres golpes
    Efecto.DEFENSA: 3,  # aguantar poco no paga el turno: tiene que durar
    Efecto.CRITICO: 3,
    Efecto.MANA: 0,
    Efecto.CURAR: 0,
    # No es "dos turnos esquivando": es un golpe esquivado, y dos turnos para
    # que llegue. Usar la habilidad gasta tu turno sin saber quien te va a
    # pegar, asi que con un solo turno de ventana seria una apuesta a ciegas.
    Efecto.EVASION: 2,
    # El seguro de vida dura medio combate. No se gasta solo: se gasta cuando
    # te salva.
    Efecto.AGUANTAR: 5,
    Efecto.BAJAR_ATAQUE: 3,
    Efecto.BAJAR_DEFENSA: 3,
    Efecto.BAJAR_MANA: 0,  # instantaneo, como MANA
}

# Cada cuanto se puede repetir una habilidad, por efecto. Un enfriamiento de
# N significa que la habilidad vuelve N turnos despues de usarse: con 2 se usa
# en los turnos 1, 4 y 7 de un combate, con 3 en el 1, 5 y 9, y con 5 en el 1
# y el 7. Los combates duran unos 9 turnos.
#
# FGO usa de 4 a 12 turnos, casi todos 7 u 8, que en nuestros combates seria
# "una vez por combate". Subir ataque o defensa es el efecto mas pequeno, asi
# que se repite; el critico es el mas violento y la curacion deshace el dano
# de un turno entero, asi que los dos se pagan caro.
ENFRIAMIENTO_POR_EFECTO = {
    Efecto.ATAQUE: 2,
    Efecto.DEFENSA: 2,
    Efecto.MANA: 3,
    Efecto.CRITICO: 5,
    Efecto.CURAR: 5,
    Efecto.NINGUNO: 2,
    # Esquivar un golpe es lo mas parecido a curarse que hay, porque deshace
    # un ataque entero, asi que se paga igual de caro. Aguantar es un seguro
    # de vida: una vez y media por combate.
    Efecto.EVASION: 5,
    Efecto.AGUANTAR: 5,
    # Los negativos se repiten como sus positivos, porque dan menos.
    Efecto.BAJAR_ATAQUE: 2,
    Efecto.BAJAR_DEFENSA: 2,
    # Quitar mana es el espejo de darselo, asi que se paga igual: 3.
    Efecto.BAJAR_MANA: 3,
}

# Topes de la ficha, para que ningun dato raro entre al combate. Lo que vale
# cada efecto dentro del combate se escala en battle.py.
TURNOS_MAXIMOS = 5
MANA_MAXIMO_HABILIDAD = 100
VALOR_MAXIMO = 3.0  # x4 de dano es lo mas que puede dar un bono


@dataclass(frozen=True)
class Habilidad:
    """Una de las 3 habilidades de un personaje.

    `valor` se lee segun el efecto: una fraccion para ATAQUE, DEFENSA,
    CRITICO (puntos de probabilidad) y CURAR (parte de la vida maxima), y
    puntos de mana para MANA. `turnos` es cuanto dura, y no cuenta el turno en
    que se usa, porque usarla ya gasta ese turno.

    Los tres salen de las tablas de arriba segun el efecto, asi que la ficha
    normal solo trae el nombre, el efecto y el objetivo. Un 0 significa "el de
    la tabla"; una ficha escrita a mano puede traer el suyo para un personaje
    que lo merezca.
    """

    nombre: str = ""
    efecto: Efecto = Efecto.NINGUNO
    objetivo: Objetivo = Objetivo.UNO_MISMO
    valor: float = 0.0
    turnos: int = 0
    enfriamiento: int = 0
    # El nombre en ingles, para los que se escribieron a mano en espanol. Los
    # que vienen del importador ya estan en ingles y no lo necesitan.
    nombre_en: str = ""

    def nombre_para(self, idioma: str | None = None) -> str:
        """El nombre en el idioma pedido, o el que haya."""
        if idioma_valido(idioma) == "en" and self.nombre_en:
            return self.nombre_en
        return self.nombre

    def __post_init__(self) -> None:
        # Es frozen, asi que los valores por defecto se rellenan aqui a mano.
        if not self.valor:
            object.__setattr__(self, "valor", VALOR_POR_EFECTO.get(self.efecto, 0.0))
        if not self.turnos:
            object.__setattr__(self, "turnos", TURNOS_POR_EFECTO.get(self.efecto, 0))

    @property
    def instantanea(self) -> bool:
        return self.efecto in EFECTOS_INSTANTANEOS

    @property
    def turnos_de_enfriamiento(self) -> int:
        return self.enfriamiento or ENFRIAMIENTO_POR_EFECTO[self.efecto]

    @property
    def negativa(self) -> bool:
        """Si lo que hace es ponerselo al rival en vez de a si mismo."""
        return self.efecto in EFECTOS_NEGATIVOS

    @property
    def hace_algo(self) -> bool:
        return self.efecto is not Efecto.NINGUNO and self.valor > 0

    def validar(self) -> None:
        if self.efecto in (Efecto.MANA, Efecto.BAJAR_MANA):
            if not 0 <= self.valor <= MANA_MAXIMO_HABILIDAD:
                raise ValueError(
                    f"la habilidad {self.nombre}: {self.valor} de mana esta fuera "
                    f"de 0-{MANA_MAXIMO_HABILIDAD}"
                )
        elif not 0 <= self.valor <= VALOR_MAXIMO:
            raise ValueError(
                f"la habilidad {self.nombre}: su valor es {self.valor} y los "
                f"efectos que no son de mana van de 0 a {VALOR_MAXIMO}"
            )
        if not 0 <= self.turnos <= TURNOS_MAXIMOS:
            raise ValueError(
                f"la habilidad {self.nombre}: dura {self.turnos} turnos y el "
                f"maximo es {TURNOS_MAXIMOS}"
            )
        if self.instantanea and self.turnos:
            raise ValueError(
                f"la habilidad {self.nombre}: un efecto de {self.efecto.value} "
                f"ocurre de una vez y no puede durar turnos"
            )
        if not self.instantanea and self.hace_algo and not self.turnos:
            raise ValueError(
                f"la habilidad {self.nombre}: un efecto de {self.efecto.value} "
                f"tiene que durar al menos un turno"
            )

    def descripcion(self, idioma: str | None = None) -> str:
        """Como se cuenta en Discord. Sin el nombre, que va aparte."""
        if not self.hace_algo:
            return t("ficha.habilidad_sin_efecto", idioma)
        a_quien = t(
            {
                Objetivo.UNO_MISMO: "ficha.objetivo_uno_mismo",
                Objetivo.ALIADO: "ficha.objetivo_aliado",
                Objetivo.OTRO: "ficha.objetivo_otro",
            }[self.objetivo],
            idioma,
        )
        if self.efecto is Efecto.MANA:
            que = t("ficha.efecto_mana", idioma, mana=int(self.valor))
        elif self.efecto is Efecto.BAJAR_MANA:
            que = t("ficha.efecto_bajar_mana", idioma, mana=int(self.valor))
        elif self.efecto is Efecto.CURAR:
            que = t(
                "ficha.efecto_curar", idioma, porcentaje=f"{self.valor * 100:.0f}"
            )
        elif self.efecto is Efecto.ATAQUE:
            que = t("ficha.efecto_ataque", idioma, factor=f"{1 + self.valor:.2g}")
        elif self.efecto is Efecto.DEFENSA:
            que = t(
                "ficha.efecto_defensa", idioma, porcentaje=f"{self.valor * 100:.0f}"
            )
        elif self.efecto is Efecto.EVASION:
            que = t("ficha.efecto_evasion", idioma)
        elif self.efecto is Efecto.AGUANTAR:
            que = t(
                "ficha.efecto_aguantar", idioma, porcentaje=f"{self.valor * 100:.0f}"
            )
        elif self.efecto is Efecto.BAJAR_ATAQUE:
            que = t(
                "ficha.efecto_bajar_ataque",
                idioma,
                porcentaje=f"{self.valor * 100:.0f}",
            )
        elif self.efecto is Efecto.BAJAR_DEFENSA:
            que = t(
                "ficha.efecto_bajar_defensa",
                idioma,
                porcentaje=f"{self.valor * 100:.0f}",
            )
        else:
            que = t("ficha.efecto_critico", idioma, puntos=f"{self.valor * 100:.0f}")

        if self.instantanea:
            return t(
                "ficha.habilidad_instantanea",
                idioma,
                que=que,
                a_quien=a_quien,
                enfriamiento=self.turnos_de_enfriamiento,
            )
        return t(
            "ficha.habilidad_con_duracion",
            idioma,
            que=que,
            a_quien=a_quien,
            duracion=turnos_texto(self.turnos, idioma),
            enfriamiento=self.turnos_de_enfriamiento,
        )


SIN_HABILIDAD = Habilidad()
SIN_HABILIDADES = (SIN_HABILIDAD, SIN_HABILIDAD, SIN_HABILIDAD)

# Atlas Academy tapa con interrogantes lo que en FGO es un secreto de la
# historia: siete personajes traen el nombre del Noble Fantasma como "???" y
# el rango como "？" (y dos mas traen tapado solo el tipo, que no se ensena).
# No es un dato que falte, es un dato escondido a proposito, asi que no se
# escribe a mano: se limpia al leerlo y la ficha ensena el Noble Fantasma sin
# nombre. El Servant lo sigue teniendo y lo sigue lanzando.
MARCAS_TAPADAS = ("?", "？")


def _tapado(texto: str) -> bool:
    """Si lo que trae el dato es un interrogante y no un nombre."""
    limpio = texto.strip()
    return bool(limpio) and all(c in MARCAS_TAPADAS for c in limpio)


@dataclass(frozen=True)
class NobleFantasma:
    """El Noble Fantasma de un personaje.

    De los datos salen el nombre, el rango (A++, EX) y el tipo
    (Anti-Personnel, Anti-Army), que son suyos y no se traducen, como los
    nombres propios. Lo que hace en combate no sale de aqui: hoy todos pegan
    igual, x3 a un objetivo por 100 de mana, y eso lo dicen `battle.py` y el
    rasgo del personaje. Cuando cada uno tenga su efecto, vivira aqui.
    """

    nombre: str = ""
    rango: str = ""
    tipo: str = ""
    # El nombre en ingles, para los que se escribieron a mano en espanol.
    nombre_en: str = ""
    # El dato traia el nombre tapado con interrogantes. Lo tiene, no sabemos
    # como se llama: ver MARCAS_TAPADAS.
    oculto: bool = False

    def nombre_para(self, idioma: str | None = None) -> str:
        if idioma_valido(idioma) == "en" and self.nombre_en:
            return self.nombre_en
        return self.nombre

    def __bool__(self) -> bool:
        """Si el personaje tiene Noble Fantasma, con nombre o sin el.

        Uno oculto cuenta: la ficha tiene que contar lo que hace, y lo unico
        que no puede contar es como se llama. El que de verdad no tiene es
        `SIN_NOBLE_FANTASMA`, que es el de las Sombras.
        """
        return bool(self.nombre) or self.oculto


SIN_NOBLE_FANTASMA = NobleFantasma()


def noble_fantasma_desde(dato: object) -> NobleFantasma:
    """Lee el Noble Fantasma de la ficha: el nombre a secas o completo."""
    if isinstance(dato, NobleFantasma):
        return dato
    if not dato:
        return SIN_NOBLE_FANTASMA
    if isinstance(dato, str):
        return NobleFantasma(nombre=dato)
    if not isinstance(dato, dict):
        raise ValueError(f"no se entiende el Noble Fantasma {dato!r}")
    nombre = dato.get("nombre", "")
    rango = dato.get("rango", "")
    # Un nombre tapado se queda en nada y el rango se va con el: "??? (rango
    # ？)" no es informacion, es ruido. Ver MARCAS_TAPADAS.
    oculto = _tapado(nombre)
    if oculto:
        nombre, rango = "", ""
    if _tapado(rango):
        rango = ""
    return NobleFantasma(
        nombre=nombre,
        rango=rango,
        tipo=dato.get("tipo", ""),
        nombre_en=dato.get("nombre_en", ""),
        oculto=oculto or bool(dato.get("oculto")),
    )


def _mezclar_noble_fantasma(generado: object, retoque: object) -> object:
    """Igual que con las habilidades: el nombre a mano, el resto heredado."""
    if retoque is None or retoque == "":
        return generado
    if isinstance(generado, dict):
        heredado = {
            "nombre_en": generado.get("nombre_en") or generado.get("nombre", "")
        }
        if isinstance(retoque, str):
            return {**generado, **heredado, "nombre": retoque}
        if isinstance(retoque, dict):
            if retoque.get("nombre"):
                return {**generado, **heredado, **retoque}
            return {**generado, **retoque}
    return retoque


def habilidad_desde(dato: object) -> Habilidad:
    """Lee una habilidad de la ficha.

    Admite el nombre a secas, que es una habilidad sin efecto todavia, o un
    diccionario con lo que traduce el importador.
    """
    if isinstance(dato, Habilidad):
        return dato
    if dato is None:
        return SIN_HABILIDAD
    if isinstance(dato, str):
        return Habilidad(nombre=dato)
    if not isinstance(dato, dict):
        raise ValueError(f"no se entiende la habilidad {dato!r}")
    h = Habilidad(
        nombre=dato.get("nombre", ""),
        efecto=Efecto(dato.get("efecto", "ninguno")),
        objetivo=Objetivo(dato.get("objetivo", "uno_mismo")),
        valor=float(dato.get("valor", 0.0)),
        turnos=int(dato.get("turnos", 0)),
        enfriamiento=int(dato.get("enfriamiento", 0)),
        nombre_en=dato.get("nombre_en", ""),
    )
    h.validar()
    return h


def _mezclar_habilidad(generada: object, retoque: object) -> object:
    """Aplica un retoque a mano sobre la habilidad generada, hueco por hueco.

    Un retoque que solo trae el nombre cambia el nombre y conserva el efecto
    que salio de los datos, que es el caso normal: quien reescribe "Instinto"
    en espanol no quiere perder lo que hace. Y el nombre que venia de los
    datos, que esta en ingles, se guarda como `nombre_en`: asi renombrar al
    espanol no deja la guerra en ingles sin nombre.
    """
    if retoque is None or retoque == "":
        return generada
    if isinstance(generada, dict):
        heredado = {"nombre_en": generada.get("nombre_en") or generada.get("nombre", "")}
        if isinstance(retoque, str):
            return {**generada, **heredado, "nombre": retoque}
        if isinstance(retoque, dict):
            if retoque.get("nombre"):
                return {**generada, **heredado, **retoque}
            return {**generada, **retoque}
    return retoque


@dataclass(frozen=True)
class Rasgo:
    """El rasgo propio de un personaje, como un juego de perillas.

    Un personaje nuevo solo puede mover estas perillas, asi que no puede
    inventar una regla que rompa el combate.
    """

    descripcion: str = ""
    # La misma frase en ingles. Si falta, se usa la otra: mas vale leerla en
    # el idioma equivocado que no leerla.
    descripcion_en: str = ""
    mana_inicial: int = 20
    mana_extra_ataque: int = 0
    costo_noble_fantasma: int = 100
    prob_evasion: float = 0.10
    prob_segunda_defensa: float = 0.30
    puede_defender: bool = True
    sellos: int = 3
    ataca_primero_si_el_blanco_no_defiende: bool = False
    objetivo_al_azar: bool = False

    def texto(self, idioma: str | None = None) -> str:
        """La descripcion en el idioma pedido, o la que haya."""
        if idioma_valido(idioma) == "en" and self.descripcion_en:
            return self.descripcion_en
        return self.descripcion


RASGO_NEUTRO = Rasgo()


@dataclass(frozen=True)
class Personaje:
    nombre: str
    clase: Clase
    mult_vida: float = 1.0
    mult_ataque: float = 1.0
    mult_velocidad: float = 1.0
    rasgo: Rasgo = RASGO_NEUTRO
    habilidades: tuple[Habilidad, Habilidad, Habilidad] = SIN_HABILIDADES
    noble_fantasma: NobleFantasma = SIN_NOBLE_FANTASMA
    # Identificador en los datos de Atlas Academy. Es la clave con la que se
    # emparejan los retoques a mano, porque no depende del idioma ni cambia.
    collection_no: int | None = None
    rareza: int = 0
    # Las URLs del arte de carta, una por ascension, en orden: el indice 0 es
    # la ascension 1. Es una tupla y no un diccionario porque `Personaje` es
    # frozen y se puede querer hashear, y un dict no se puede.
    #
    # Aqui solo viven las URLs. Que ascension le toca a un Servant lo dice
    # `Servant.ascension`, y abrir la imagen no lo hace nadie en `src/`: ver
    # la regla del arte en docs/decisiones.md.
    imagenes: tuple[str, ...] = ()

    # --- estadisticas ---

    def vida(self, nivel: int = 1) -> int:
        return int(BASE_VIDA * self.mult_vida * (1 + CRECIMIENTO_VIDA * (nivel - 1)))

    def ataque(self, nivel: int = 1) -> int:
        return int(
            BASE_ATAQUE * self.mult_ataque * (1 + CRECIMIENTO_ATAQUE * (nivel - 1))
        )

    def velocidad(self, nivel: int = 1) -> int:
        return int(
            BASE_VELOCIDAD
            * self.mult_velocidad
            * (1 + CRECIMIENTO_VELOCIDAD * (nivel - 1))
        )

    @property
    def presupuesto(self) -> float:
        return self.mult_vida + self.mult_ataque + self.mult_velocidad

    def validar(self) -> None:
        if abs(self.presupuesto - PRESUPUESTO) > TOLERANCIA:
            raise ValueError(
                f"{self.nombre}: sus multiplicadores suman {self.presupuesto:.3f} "
                f"y deben sumar {PRESUPUESTO:.2f}"
            )
        for etiqueta, m in (
            ("vida", self.mult_vida),
            ("ataque", self.mult_ataque),
            ("velocidad", self.mult_velocidad),
        ):
            if not MULTIPLICADOR_MINIMO <= m <= MULTIPLICADOR_MAXIMO:
                raise ValueError(
                    f"{self.nombre}: su multiplicador de {etiqueta} es {m}, "
                    f"fuera del rango permitido "
                    f"({MULTIPLICADOR_MINIMO}-{MULTIPLICADOR_MAXIMO})"
                )
        if len(self.habilidades) != 3:
            raise ValueError(f"{self.nombre}: debe tener exactamente 3 habilidades")
        for h in self.habilidades:
            h.validar()


def desde_dict(d: dict) -> Personaje:
    faltan = [c for c in ("nombre", "clase", "vida", "ataque", "velocidad") if c not in d]
    if faltan:
        raise ValueError(
            f"la ficha {d.get('nombre') or d.get('collectionNo') or '?'} no tiene "
            f"{', '.join(faltan)}. Un retoque a mano necesita que el personaje "
            f"exista en el plantel generado, o traer sus propias estadisticas."
        )
    rasgo_bruto = d.get("rasgo") or {}
    rasgo = Rasgo(**rasgo_bruto) if rasgo_bruto else RASGO_NEUTRO
    brutas = list(d.get("habilidades") or [])
    brutas += [None] * (3 - len(brutas))
    habilidades = tuple(habilidad_desde(h) for h in brutas[:3])
    p = Personaje(
        nombre=d["nombre"],
        clase=Clase(d["clase"]),
        mult_vida=float(d["vida"]),
        mult_ataque=float(d["ataque"]),
        mult_velocidad=float(d["velocidad"]),
        rasgo=rasgo,
        habilidades=habilidades,
        noble_fantasma=noble_fantasma_desde(d.get("noble_fantasma")),
        collection_no=d.get("collectionNo"),
        rareza=int(d.get("rareza", 0)),
        imagenes=imagenes_desde(d.get("imagenes")),
    )
    p.validar()
    return p


def imagenes_desde(bruto: object) -> tuple[str, ...]:
    """Las 4 URLs del arte, en orden, desde el `{"1": url, ...}` del plantel.

    Se queda corta si faltan ascensiones y vacia si no hay ninguna: un
    personaje sin arte tiene que seguir entrando en el juego, porque el arte
    es un adorno y las estadisticas no.
    """
    if not isinstance(bruto, dict):
        return ()
    urls = []
    for n in ("1", "2", "3", "4"):
        url = bruto.get(n)
        if not isinstance(url, str) or not url:
            break
        urls.append(url)
    return tuple(urls)


def _clave(d: dict) -> object:
    """Con que se empareja una ficha: el collectionNo si lo tiene."""
    return d.get("collectionNo") if d.get("collectionNo") is not None else d.get("nombre")


def _leer(archivo: Path) -> list[dict]:
    if not archivo.exists():
        return []
    return json.loads(archivo.read_text(encoding="utf-8"))["personajes"]


def cargar(
    ruta: Path | str | None = None, ruta_generados: Path | str | None = None
) -> list[Personaje]:
    """Carga el plantel y valida cada ficha.

    Primero el plantel generado desde los datos de Atlas Academy, y encima los
    retoques a mano de `personajes.json`, emparejados por `collectionNo`. Un
    retoque solo tiene que traer lo que cambia; el resto lo hereda. Si no hay
    plantel generado, se usan solo los retoques, que entonces deben traer sus
    estadisticas.
    """
    fichas: dict[object, dict] = {}
    for d in _leer(Path(ruta_generados or RUTA_GENERADOS)):
        fichas[_clave(d)] = dict(d)
    for d in _leer(Path(ruta or RUTA_CATALOGO)):
        clave = _clave(d)
        if clave in fichas:
            ficha = fichas[clave]
            # Las habilidades se mezclan hueco por hueco, no se reemplazan en
            # bloque: un retoque que solo pone el nombre en espanol conserva el
            # efecto que trajo el importador.
            generadas = list(ficha.get("habilidades") or [None, None, None])
            retoques = list(d.get("habilidades") or [])
            ficha["noble_fantasma"] = _mezclar_noble_fantasma(
                ficha.get("noble_fantasma"), d.get("noble_fantasma")
            )
            np_mezclado = ficha["noble_fantasma"]
            ficha.update(d)
            ficha["noble_fantasma"] = np_mezclado
            if retoques:
                generadas += [None] * (3 - len(generadas))
                retoques += [None] * (3 - len(retoques))
                ficha["habilidades"] = [
                    _mezclar_habilidad(g, r)
                    for g, r in zip(generadas[:3], retoques[:3])
                ]
        else:
            fichas[clave] = dict(d)

    personajes = [desde_dict(d) for d in fichas.values()]
    nombres = [p.nombre for p in personajes]
    repetidos = {n for n in nombres if nombres.count(n) > 1}
    if repetidos:
        raise ValueError(f"personajes repetidos en el plantel: {sorted(repetidos)}")
    return personajes


def por_clase(personajes: list[Personaje]) -> dict[Clase, list[Personaje]]:
    agrupados: dict[Clase, list[Personaje]] = {}
    for p in personajes:
        agrupados.setdefault(p.clase, []).append(p)
    return agrupados

