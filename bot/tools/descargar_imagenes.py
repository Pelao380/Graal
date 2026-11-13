"""Descarga el arte de carta de los personajes, una sola vez.

IMPORTANTE: esto hay que correrlo en Windows (PowerShell), no en un entorno
sin salida a internet.

Uso, desde la carpeta bot/:

    python tools/descargar_imagenes.py --limite 5    # probar con 5
    python tools/descargar_imagenes.py               # las 348 x 4 ascensiones
    python tools/descargar_imagenes.py --ascensiones 1

Las imagenes van a data/imagenes/ con el nombre {collectionNo}_{ascension}.png
y **no se suben al repositorio**: el repositorio lleva este script, para que
cada uno descargue su propia copia en vez de recibirla de otro.

Las cuatro ascensiones se reparten por nivel, y de eso decide
`Servant.ascension`: 1-4 la primera, 5-9 la segunda, 10-14 la tercera y 15 la
cuarta. Son los mismos cortes que `NIVELES_HABILIDAD`, asi que el aspecto
cambia justo cuando se desbloquea una habilidad. Si solo bajas unas pocas
ascensiones, los Servants de los niveles que falten se quedan sin imagen.

El script es reanudable: salta lo que ya esta descargado, asi que si se corta
se vuelve a correr y sigue donde iba.

Solo usa la biblioteca estandar: no hay que instalar nada.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
GENERADOS = RAIZ / "data" / "personajes_generados.json"
DESTINO = RAIZ / "data" / "imagenes"

# Identificarse con un nombre generico es lo correcto al descargar de un
# servidor ajeno. Nada de datos personales aqui.
AGENTE = "Graal/0.1 (bot de Discord, proyecto de fans sin animo de lucro)"

# Una pausa entre descargas para no castigar al servidor de Atlas Academy,
# que es un proyecto de fans pagando de su bolsillo.
PAUSA_SEGUNDOS = 0.3

TIEMPO_LIMITE = 30


def descargar(url: str, destino: Path) -> int:
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(peticion, timeout=TIEMPO_LIMITE) as r:
        datos = r.read()
    # Se escribe primero a un temporal: si se corta, no queda un PNG a medias
    # que el script siguiente daria por bueno.
    temporal = destino.with_suffix(".parcial")
    temporal.write_bytes(datos)
    temporal.replace(destino)
    return len(datos)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limite", type=int, default=None,
                   help="descarga solo los primeros N personajes, para probar")
    p.add_argument("--ascensiones", nargs="+", default=["1", "2", "3", "4"],
                   help="que ascensiones bajar (por defecto las 4)")
    a = p.parse_args()

    if not GENERADOS.exists():
        raise SystemExit(
            f"No encuentro {GENERADOS.name}. Corre antes: "
            f"python tools/importar_servants.py"
        )

    fichas = json.loads(GENERADOS.read_text(encoding="utf-8"))["personajes"]
    if not any(f.get("imagenes") for f in fichas):
        raise SystemExit(
            "El plantel no tiene URLs de imagen. Reimporta con el export "
            "grande: python tools/importar_servants.py"
        )
    if a.limite:
        fichas = fichas[: a.limite]

    DESTINO.mkdir(parents=True, exist_ok=True)

    pendientes: list[tuple[str, Path]] = []
    for f in fichas:
        for ascension, url in (f.get("imagenes") or {}).items():
            if ascension not in a.ascensiones:
                continue
            archivo = DESTINO / f"{f['collectionNo']}_{ascension}.png"
            if not archivo.exists():
                pendientes.append((url, archivo))

    ya = sum(1 for f in fichas
             for asc in (f.get("imagenes") or {})
             if asc in a.ascensiones and (DESTINO / f"{f['collectionNo']}_{asc}.png").exists())
    print(f"{len(fichas)} personajes. Ya descargadas: {ya}. Pendientes: {len(pendientes)}.")
    if not pendientes:
        print("Nada que hacer.")
        return
    print(f"Guardando en {DESTINO}")

    bytes_totales = 0
    fallos: list[tuple[str, str]] = []
    for i, (url, archivo) in enumerate(pendientes, 1):
        try:
            bytes_totales += descargar(url, archivo)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            fallos.append((url, str(e)))
        if i % 25 == 0 or i == len(pendientes):
            print(f"  {i}/{len(pendientes)}  ({bytes_totales / 1_048_576:.1f} MB)")
        time.sleep(PAUSA_SEGUNDOS)

    print(f"\nListo. {len(pendientes) - len(fallos)} imagenes, "
          f"{bytes_totales / 1_048_576:.1f} MB en total.")
    if fallos:
        print(f"Fallaron {len(fallos)}. Vuelve a correr el script y lo reintenta:")
        for url, e in fallos[:5]:
            print(f"   {url}  ->  {e}")


if __name__ == "__main__":
    main()
