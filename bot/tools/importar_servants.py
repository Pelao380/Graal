"""Convierte el export de Atlas Academy en nuestro formato de personajes.

Uso, desde la carpeta bot/:

    python tools/importar_servants.py
    python tools/importar_servants.py --entrada data/basic_servant.json

Lee `data/basic_servant.json` (el export de Atlas Academy) y escribe
`data/personajes_generados.json` con una ficha por personaje de nuestras 8
clases. Es idempotente: se puede volver a correr cuando salga un personaje
nuevo y el resultado solo cambia en lo que cambio el juego.

Por que no copiamos las estadisticas tal cual
---------------------------------------------
Las de FGO estan ordenadas por rareza, no por equilibrio: un 5* tiene cerca
del doble de ataque que un 1*. Copiarlas haria que la rareza decidiera cada
combate. Tampoco existe la velocidad: FGO no la tiene.

Lo que si conservamos es la **proporcion** entre vida y ataque de cada
personaje, que es su caracter: Jeanne aguanta, Heracles pega. La magnitud es
nuestra, y sale del presupuesto de 3.00.

El reparto
----------
1. La velocidad la da la clase (tabla de abajo).
2. Lo que sobra del presupuesto, 3.00 menos la velocidad, se reparte entre
   vida y ataque segun la proporcion HP:ATK del personaje, normalizada por la
   mediana del plantel: quien esta en la mediana sale equilibrado.
3. `EXAGERACION` separa a los extremos. A 1.0 el plantel sale muy parecido;
   subirla diferencia mas, a costa de acercarse a los limites.
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Solo los Servants jugables. El export incluye fichas de enemigos y de
# jefes de historia, que vienen marcadas con otro `type`: Solomon, por
# ejemplo, es `enemyCollectionDetail` y no tiene ninguna habilidad.
TIPOS_JUGABLES = {"normal"}

# **Un Servant que no se puede invocar no ocupa cupo en la coleccion, y por eso
# su `collectionNo` es 0.** El caso que lo descubrio es Hyde: viene como
# `type` "normal" (en el juego es de verdad), pero es la forma Berserker en la
# que se transforma Jekyll, que ya esta en el plantel por su cuenta con el
# numero 81. No se invoca, no tiene arte propio (sus cuatro URLs dan 404) y
# tenerlo era tener a Jekyll dos veces.
#
# La regla se escribe asi, por el cupo, y no como "quitar a Hyde": si el
# export trae otra forma parecida, se descarta sola.
SIN_CUPO_EN_LA_COLECCION = 0

# Las 8 clases del juego, del nombre de Atlas Academy al nuestro.
CLASES = {
    "saber": "Saber",
    "archer": "Archer",
    "lancer": "Lancer",
    "rider": "Rider",
    "caster": "Caster",
    "assassin": "Assassin",
    "berserker": "Berserker",
    "ruler": "Ruler",
}

# La velocidad sale solo de la clase, porque los datos de FGO no la traen.
VELOCIDAD_POR_CLASE = {
    "Assassin": 1.15,
    "Rider": 1.10,
    "Lancer": 1.05,
    "Saber": 1.00,
    "Archer": 1.00,
    "Ruler": 0.95,
    "Caster": 0.90,
    "Berserker": 0.85,
}

PRESUPUESTO = 3.00
MULTIPLICADOR_MINIMO = 0.55
MULTIPLICADOR_MAXIMO = 1.35

# Cuanto se separan los extremos del plantel. 1.0 es fiel a los datos.
EXAGERACION = 1.5


# --- habilidades -------------------------------------------------------
#
# FGO tiene 73 tipos de buff y 20 de funcion; nosotros tenemos cinco efectos
# (ver src/game/personajes.py), porque nuestro combate solo tiene esas
# perillas. Esta tabla es la traduccion: la clave es el buff cuando la funcion
# pone un estado, y el funcType cuando hace algo de una vez.
#
# Lo que no esta en estas dos tablas entra como NINGUNO y la habilidad solo
# gasta el turno. El 2026-11-09 se midio cuantas eran y por que: de 1044
# habilidades, 159 estaban vacias (15.2%), en 131 personajes. La mitad se
# caia por el objetivo (244 funciones a `enemy` y `enemyAll`), y eso es por
# diseno: los efectos negativos son otro proyecto. De lo que se caia por el
# buff o el funcType se tradujo lo que ya era uno de nuestros cinco efectos
# con otro nombre (las seis entradas comentadas mas abajo), y se dejo fuera lo
# que pide una regla nueva: `guts` (no morirte, 48), `invincible`/`avoidance`
# (esquivar, 38) y `upHate` (provocar, 18). Eso esta en puntos-abiertos.md.
#
# Solo se traduce *que* hace cada habilidad, no cuanto: lo que da cada efecto
# y cuanto dura esta en `VALOR_POR_EFECTO` y `TURNOS_POR_EFECTO`, en
# personajes.py. Las magnitudes de FGO se descartan porque estan calibradas
# para un juego donde usar una habilidad no cuesta el turno.
EFECTOS_POR_BUFF = {
    "upAtk": "ataque",
    "upCommandall": "ataque",
    "upNpdamage": "ataque",
    "upDamage": "ataque",
    "addDamage": "ataque",
    "upDefence": "defensa",
    "subSelfdamage": "defensa",
    # FGO separa probabilidad, dano y estrellas de critico; nosotros tenemos
    # una sola perilla, la probabilidad, asi que las tres caen en ella.
    "upCriticalrate": "critico",
    "upCriticaldamage": "critico",
    "upCriticalpoint": "critico",
    "regainStar": "critico",
    "regainNp": "mana",
    "regainHp": "curar",
}

# Lo mismo, pero de **segunda vuelta**: solo se mira cuando ninguna funcion de
# la habilidad se pudo traducir con las tablas de arriba.
#
# El orden importa y por eso estan aparte. `habilidad_de` se queda con la
# primera funcion que sabe traducir, asi que meter estas en la tabla principal
# no solo rellenaba huecos: le cambiaba el efecto a habilidades que ya tenian
# uno, porque una funcion nueva podia aparecer antes en la lista de FGO. Medido
# al hacerlo: 5 habilidades de critico y 1 de ataque se convertian en mana sin
# que nadie lo pidiera. Con la segunda vuelta, las fichas que ya tenian efecto
# salen identicas y lo unico que cambia son las vacias.
EFECTOS_POR_BUFF_SECUNDARIOS = {
    # Cargar mas rapido es, en un juego sin barras que se llenan por su
    # cuenta, lo mismo que tener mas mana: nuestro mana es un numero que sube
    # y el Noble Fantasma cuesta 100, asi que "subes el mana que te da pegar"
    # y "te doy mana" acaban en la misma perilla. Eran 47 habilidades.
    "upDropnp": "mana",
    "upDamagedropnp": "mana",
    # Mas vida maxima es mas vida, y la unica perilla de vida que tenemos es
    # curar, que da una parte de la maxima. No es lo mismo (una se queda y la
    # otra no), pero el efecto en el combate va en la misma direccion.
    "addMaxhp": "curar",
    "upGainHp": "curar",
    # Esquivar un golpe. En FGO son tres cosas distintas (invulnerable,
    # esquiva, esquiva de un tipo de ataque) y aqui las tres son la misma: el
    # golpe no te toca.
    "invincible": "evasion",
    "avoidance": "evasion",
    "avoidState": "evasion",
    # No morirte. `guts` es el estado y `gutsFunction` la version que se
    # dispara sola; las dos acaban igual.
    "guts": "aguantar",
    "gutsFunction": "aguantar",
    # Los dos unicos efectos negativos. FGO tiene media docena de formas de
    # bajar el ataque o la defensa segun el tipo de carta; aqui no hay cartas,
    # asi que todas caen en la misma.
    #
    # Van en segunda vuelta como todo lo de aqui, y eso decide algo: una
    # habilidad que ya subia tu ataque y **tambien** bajaba el del rival sigue
    # siendo de ataque. Solo se vuelve un debuff si no hacia nada.
    "downAtk": "bajar_ataque",
    "downCommandall": "bajar_ataque",
    "downNpdamage": "bajar_ataque",
    "downDamage": "bajar_ataque",
    "downDefence": "bajar_defensa",
    "downDefencecommandall": "bajar_defensa",
}

# Los efectos que van al rival. Un efecto negativo solo se acepta si en FGO
# apuntaba al enemigo, y un objetivo enemigo solo se acepta si el efecto es
# negativo: asi no entra nunca un `Objetivo.OTRO` con un beneficio sacado de
# un debuff, ni un debuff que te lo pondrias a ti mismo.
EFECTOS_NEGATIVOS = ("bajar_ataque", "bajar_defensa", "bajar_mana")
OBJETIVOS_ENEMIGOS = ("enemy", "enemyAll", "enemyOther")

EFECTOS_POR_FUNCION = {
    "gainNp": "mana",
    "gainMultiplyNp": "mana",
    "gainNpFromTargets": "mana",
    "gainStar": "critico",
    "gainHp": "curar",
    "gainHpFromTargets": "curar",
}

EFECTOS_POR_FUNCION_SECUNDARIOS = {
    # Adelantar el Noble Fantasma un turno es mana por otro camino: en FGO
    # mueve el reloj de la carga, y aqui el reloj **es** el mana. Eran 53
    # habilidades, el grupo mas grande de los que se podian traducir.
    "hastenNpturn": "mana",
    "gainNpBuffIndividualSum": "mana",
    # Quitarle carga al Noble Fantasma del rival. Aqui el reloj **es** el
    # mana, asi que es el espejo exacto de "gainNp": restar en vez de sumar.
    "lossNp": "bajar_mana",
}

# A quien apunta. En Graal no hay equipos: lo que en FGO iba a un aliado o a
# todo el bando pasa a ir a un solo objetivo que elige el Master.
#
# Lo que apunta al enemigo entra desde el 2026-11-09, y entra como "otro", que
# es el objetivo que ya existia para "cualquiera menos tu". No hace falta un
# objetivo nuevo porque en una guerra de todos contra todos un enemigo **es**
# cualquier otro, y lo que no se puede es ponerse un efecto negativo a uno
# mismo: `Objetivo.OTRO` ya lo impide. Lo de FGO que apuntaba a todo el bando
# enemigo apunta aqui a uno solo, igual que los beneficios.
OBJETIVOS = {
    "self": "uno_mismo",
    "ptOne": "aliado",
    "ptAll": "aliado",
    "ptFull": "aliado",
    "ptRandom": "aliado",
    "ptOther": "otro",
    "ptOneOther": "otro",
    "enemy": "otro",
    "enemyAll": "otro",
    "enemyOther": "otro",
}





def _recortar(x: float) -> float:
    return max(MULTIPLICADOR_MINIMO, min(MULTIPLICADOR_MAXIMO, x))


def repartir(razon_relativa: float, velocidad: float) -> tuple[float, float]:
    """Reparte el presupuesto restante entre vida y ataque.

    `razon_relativa` es la razon HP:ATK del personaje dividida por la mediana
    del plantel: 1.0 es un personaje equilibrado.
    """
    forma = razon_relativa**EXAGERACION
    bolsa = PRESUPUESTO - velocidad
    vida = _recortar(bolsa * forma / (1 + forma))
    ataque = _recortar(bolsa - vida)
    vida = _recortar(bolsa - ataque)

    vida = round(vida, 3)
    # El ataque absorbe el redondeo, para que la suma de 3.00 exacto.
    ataque = round(PRESUPUESTO - velocidad - vida, 3)
    return vida, ataque


def nombres_unicos(servants: list[dict]) -> dict[int, str]:
    """Nombre de presentacion por `collectionNo`, sin repetidos.

    Hay 11 nombres repetidos en el plantel (dos Cu Chulainn, tres Medusa...).
    Se desambiguan con la clase, que basta para todos.
    """
    cuantos = collections.Counter(s["name"] for s in servants)
    nombres: dict[int, str] = {}
    for s in servants:
        nombre = s["name"]
        if cuantos[nombre] > 1:
            nombre = f"{nombre} ({CLASES[s['className']]})"
        nombres[s["collectionNo"]] = nombre
    return nombres


def efecto_de(f: dict, secundarios: bool = False) -> dict | None:
    """Traduce una funcion de FGO a uno de nuestros efectos, o nada.

    Con `secundarios` mira las tablas de segunda vuelta en vez de las
    principales, que es como se rellenan los huecos sin tocar lo que ya tenia
    efecto.

    Se ignora la probabilidad de aplicarse (`Rate`): en FGO algunas habilidades
    fallan y aqui todas aciertan, porque el azar del combate ya lo ponen el
    dano, el critico y la esquiva. Y se ignora la magnitud (`Value`, `Turn`),
    que la pone el juego por efecto.
    """
    tipo_objetivo = f.get("funcTargetType")
    objetivo = OBJETIVOS.get(tipo_objetivo)
    if objetivo is None:
        return None
    por_buff = EFECTOS_POR_BUFF_SECUNDARIOS if secundarios else EFECTOS_POR_BUFF
    por_funcion = (
        EFECTOS_POR_FUNCION_SECUNDARIOS if secundarios else EFECTOS_POR_FUNCION
    )
    buff = (f.get("buffs") or [{}])[0].get("type")
    efecto = por_buff.get(buff) if buff else None
    if efecto is None:
        efecto = por_funcion.get(f.get("funcType"))
    if efecto is None:
        return None
    # Negativo y enemigo van juntos o no van: ver OBJETIVOS_ENEMIGOS.
    al_enemigo = tipo_objetivo in OBJETIVOS_ENEMIGOS
    if al_enemigo != (efecto in EFECTOS_NEGATIVOS):
        return None
    return {"efecto": efecto, "objetivo": objetivo}


def habilidad_de(sk: dict) -> dict:
    """Una habilidad nuestra a partir de una de FGO.

    Una habilidad de FGO hace dos o tres cosas a la vez; la nuestra hace una
    sola, asi que se queda con el primer efecto que sepamos traducir. Lo demas
    se pierde a proposito: es lo que mantiene el combate legible.

    Son dos vueltas y el orden es lo que importa: primero las traducciones
    buenas, y solo si ninguna funcion dio efecto, las de segunda vuelta. Asi
    una traduccion nueva rellena un hueco pero nunca le quita el efecto a una
    habilidad que ya lo tenia.
    """
    habilidad = {"nombre": sk.get("name", ""), "efecto": "ninguno"}
    funciones = sk.get("functions", [])
    for secundarios in (False, True):
        for f in funciones:
            efecto = efecto_de(f, secundarios)
            if efecto:
                habilidad.update(efecto)
                return habilidad
    return habilidad


def habilidades_de(s: dict) -> list[dict]:
    """Las habilidades 1, 2 y 3, con nombre y efecto.

    Un personaje puede traer varias entradas con el mismo `num`, porque el
    juego mejora habilidades con el tiempo. Nos quedamos con la primera de
    cada numero, que es la version base.
    """
    por_num: dict[int, dict] = {}
    for sk in s.get("skills", []):
        num = sk.get("num")
        if num in (1, 2, 3) and num not in por_num:
            por_num[num] = habilidad_de(sk)
    return [
        por_num.get(n, {"nombre": "", "efecto": "ninguno"}) for n in (1, 2, 3)
    ]


def noble_fantasma_de(s: dict) -> dict:
    """El Noble Fantasma base: nombre, rango y tipo.

    Igual que con las habilidades, puede haber varias versiones; la primera
    es la original.

    El `detail` de los datos no se trae a proposito: describe lo que hace en
    FGO ("restore your NP Gauge", "inflict Burn 5 turns"), que aqui no pasa.
    Mentirle al jugador sobre lo que hace su Noble Fantasma es peor que no
    contarle nada; lo que hace lo dice el bot con nuestras reglas.
    """
    nps = s.get("noblePhantasms") or []
    if not nps:
        return {"nombre": "", "rango": "", "tipo": ""}
    np = nps[0]
    return {
        "nombre": np.get("name", ""),
        "rango": np.get("rank", ""),
        "tipo": np.get("type", ""),
    }


def imagenes_de(s: dict) -> dict[str, str]:
    """Las URLs del arte de carta, una por ascension.

    `charaGraph` es el arte de carta del propio juego, que es el formato que
    queremos para la carta de invocacion. Las 4 ascensiones son el personaje
    cambiando de aspecto al progresar, y las usamos segun el nivel.

    Aqui solo se guardan las URLs. Las imagenes se descargan aparte con
    tools/descargar_imagenes.py y no van al repositorio.
    """
    asc = ((s.get("extraAssets") or {}).get("charaGraph") or {}).get("ascension") or {}
    return {k: asc[k] for k in ("1", "2", "3", "4") if k in asc}


def convertir(servants: list[dict]) -> list[dict]:
    mediana = statistics.median(s["hpMax"] / s["atkMax"] for s in servants)
    nombres = nombres_unicos(servants)
    fichas = []
    for s in sorted(servants, key=lambda x: x["collectionNo"]):
        clase = CLASES[s["className"]]
        velocidad = VELOCIDAD_POR_CLASE[clase]
        razon = (s["hpMax"] / s["atkMax"]) / mediana
        vida, ataque = repartir(razon, velocidad)
        fichas.append(
            {
                "collectionNo": s["collectionNo"],
                "nombre": nombres[s["collectionNo"]],
                "clase": clase,
                "rareza": s["rarity"],
                "vida": vida,
                "ataque": ataque,
                "velocidad": velocidad,
                # Los nombres y los efectos solo estan en nice_servant.json.
                # Con el export ligero quedan vacios y se rellenan al
                # reimportar con el grande.
                "habilidades": habilidades_de(s),
                "noble_fantasma": noble_fantasma_de(s),
                # Solo las URLs. Las imagenes las baja aparte
                # tools/descargar_imagenes.py, que sin esto no tiene de donde.
                "imagenes": imagenes_de(s),
            }
        )
    return fichas


def entrada_por_defecto() -> Path:
    """Prefiere el export grande, que trae los nombres de habilidades y NP."""
    grande = RAIZ / "data" / "nice_servant.json"
    return grande if grande.exists() else RAIZ / "data" / "basic_servant.json"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--entrada", default=None)
    p.add_argument("--salida", default=str(RAIZ / "data" / "personajes_generados.json"))
    a = p.parse_args()

    entrada = Path(a.entrada) if a.entrada else entrada_por_defecto()
    print(f"leyendo {entrada.name}")
    try:
        bruto = json.loads(entrada.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"{entrada.name} no es JSON valido ({e}). Lo mas probable es que la "
            f"descarga se cortara: un export completo termina en ']'. Vuelve a "
            f"bajarlo con  curl.exe -L -C - -o {entrada.name} "
            f"https://api.atlasacademy.io/export/NA/{entrada.name}"
        ) from e
    de_clase = [s for s in bruto if s.get("className") in CLASES]
    jugables = [s for s in de_clase if s.get("type", "normal") in TIPOS_JUGABLES]
    no_jugables = [s["name"] for s in de_clase if s not in jugables]
    if no_jugables:
        print(f"descartados por no ser jugables: {', '.join(no_jugables)}")
    servants = [
        s
        for s in jugables
        if s.get("collectionNo", 0) != SIN_CUPO_EN_LA_COLECCION
    ]
    sin_cupo = [s["name"] for s in jugables if s not in servants]
    if sin_cupo:
        print(f"descartados por no ser invocables: {', '.join(sin_cupo)}")
    fichas = convertir(servants)

    salida = {
        "_generado_por": "tools/importar_servants.py",
        "_fuente": f"Atlas Academy, export/NA/{entrada.name}",
        "_nota": (
            "Archivo generado: no editar a mano, se sobrescribe al reimportar. "
            "Los rasgos, habilidades y Nobles Fantasmas escritos a mano van en "
            "personajes.json, que se aplica encima de este por collectionNo."
        ),
        "personajes": fichas,
    }
    Path(a.salida).write_text(
        json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    por_clase = collections.Counter(f["clase"] for f in fichas)
    print(f"{len(fichas)} personajes escritos en {a.salida}")
    print("  por clase: " + ", ".join(f"{c} {n}" for c, n in sorted(por_clase.items())))
    vidas = [f["vida"] for f in fichas]
    ataques = [f["ataque"] for f in fichas]
    print(f"  vida:   {min(vidas):.2f} a {max(vidas):.2f}")
    print(f"  ataque: {min(ataques):.2f} a {max(ataques):.2f}")
    malos = [f for f in fichas if abs(f["vida"] + f["ataque"] + f["velocidad"] - 3) > 0.001]
    print(f"  fichas que no suman 3.00: {len(malos)}")
    con_np = sum(1 for f in fichas if f["noble_fantasma"]["nombre"])
    con_hab = sum(1 for f in fichas if all(h["nombre"] for h in f["habilidades"]))
    print(f"  con Noble Fantasma: {con_np}/{len(fichas)}")
    print(f"  con las 3 habilidades: {con_hab}/{len(fichas)}")
    # Si esto sale 0, `descargar_imagenes.py` no puede hacer nada: se perdio
    # una vez y la herramienta solo podia fallar, asi que ahora se cuenta.
    con_img = sum(1 for f in fichas if f.get("imagenes"))
    urls = sum(len(f.get("imagenes") or {}) for f in fichas)
    print(f"  con arte de carta: {con_img}/{len(fichas)} ({urls} URLs)")
    if not con_np:
        print("  (el export ligero no trae nombres: reimporta con nice_servant.json)")

    todas = [h for f in fichas for h in f["habilidades"] if h["nombre"]]
    por_efecto = collections.Counter(h["efecto"] for h in todas)
    por_objetivo = collections.Counter(
        h.get("objetivo", "uno_mismo") for h in todas if h["efecto"] != "ninguno"
    )
    print(f"  habilidades con nombre: {len(todas)}")
    print(
        "  por efecto: "
        + ", ".join(f"{e} {n}" for e, n in sorted(por_efecto.items()))
    )
    print(
        "  por objetivo: "
        + ", ".join(f"{o} {n}" for o, n in sorted(por_objetivo.items()))
    )


if __name__ == "__main__":
    main()

