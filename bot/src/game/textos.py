"""Los textos que lee el jugador, en espanol y en ingles.

Las frases viven en `data/textos.json`, no en el codigo, por la misma razon
que los personajes: traducir o retocar una frase no deberia ser tocar el
juego. Aqui solo esta como se piden.

    t("batalla.cae", "en", nombre="Emiya")  ->  "Emiya falls."

Se valida al cargar: cada clave tiene que traer todos los idiomas y los huecos
entre llaves tienen que ser los mismos en todos. Asi una traduccion a medias o
un hueco mal escrito revienta al arrancar, y no en medio de una batalla.

El idioma lo decide quien llama. Las batallas lo llevan en la `Batalla`, las
guerras en la `Guerra`, y el bot ademas puede usar el de Discord para lo que
solo ve un jugador.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATOS = Path(__file__).resolve().parent.parent.parent / "data"
RUTA_TEXTOS = DATOS / "textos.json"

# El idioma por defecto es el ingles, porque es el que entiende mas gente: lo
# usan la guerra que se crea sin elegir idioma, los nombres de los comandos
# que Discord ensena a quien tenga un idioma que no tenemos, y cualquier texto
# que se pida sin decir en cual. El espanol es una traduccion mas.
IDIOMA_POR_DEFECTO = "en"

# Los huecos de una frase: {nombre}, {vida}...
_HUECOS = re.compile(r"\{(\w+)\}")


def _cargar(ruta: Path | None = None) -> tuple[dict[str, dict[str, str]], tuple[str, ...]]:
    bruto = json.loads(Path(ruta or RUTA_TEXTOS).read_text(encoding="utf-8"))
    idiomas = tuple(bruto.get("_idiomas") or (IDIOMA_POR_DEFECTO,))
    textos = bruto["textos"]

    for clave, frases in textos.items():
        faltan = [i for i in idiomas if not frases.get(i)]
        if faltan:
            raise ValueError(
                f"el texto '{clave}' no esta en {', '.join(faltan)}. Un idioma a "
                f"medias no entra: se veria la clave cruda en Discord."
            )
        huecos = {i: set(_HUECOS.findall(frases[i])) for i in idiomas}
        referencia = huecos[idiomas[0]]
        for i in idiomas[1:]:
            if huecos[i] != referencia:
                sobran = huecos[i] - referencia
                faltan_huecos = referencia - huecos[i]
                raise ValueError(
                    f"el texto '{clave}' en {i} no cuadra con {idiomas[0]}: "
                    + (f"le sobra {sorted(sobran)} " if sobran else "")
                    + (f"le falta {sorted(faltan_huecos)}" if faltan_huecos else "")
                )
    return textos, idiomas


TEXTOS, IDIOMAS = _cargar()


def idioma_valido(idioma: str | None) -> str:
    """Normaliza lo que llega de fuera a uno de nuestros idiomas.

    Discord manda cosas como "es-ES" o "en-GB", y un idioma que no tenemos
    cae al por defecto en vez de reventar: quedarse sin texto es peor que
    quedarse en espanol.
    """
    if not idioma:
        return IDIOMA_POR_DEFECTO
    corto = str(idioma).replace("_", "-").split("-")[0].lower()
    return corto if corto in IDIOMAS else IDIOMA_POR_DEFECTO


def t(clave: str, idioma: str | None = None, **datos: object) -> str:
    """La frase `clave` en `idioma`, con sus huecos rellenos."""
    frases = TEXTOS.get(clave)
    if frases is None:
        raise KeyError(f"no existe el texto '{clave}'")
    frase = frases[idioma_valido(idioma)]
    try:
        return frase.format(**datos)
    except KeyError as e:
        raise KeyError(
            f"al texto '{clave}' le falta el dato {e}: lo piden sus huecos"
        ) from e


def plural(base: str, cuantos: int, idioma: str | None = None) -> str:
    """Elige entre `base.uno` y `base.varios` segun el numero.

    Para que no haya que escribir "1 persona(s)" en ninguna frase.
    """
    clave = f"{base}.uno" if cuantos == 1 else f"{base}.varios"
    return t(clave, idioma, cuantos=cuantos)


def turnos(cuantos: int, idioma: str | None = None) -> str:
    """"1 turno", "3 turnos", "1 turn", "3 turns"."""
    return plural("turnos", cuantos, idioma)
