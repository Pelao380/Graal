"""Abre graal.db y ensena lo que hay dentro.

Uso, desde la carpeta bot/:

    .\\.venv\\Scripts\\python.exe tools/ver_db.py
    .\\.venv\\Scripts\\python.exe tools/ver_db.py masters

Sin argumentos lista las tablas con sus columnas y cuantas filas tiene cada
una. Con el nombre de una tabla, ensena sus filas (las ultimas 20).

Si la base no existe, la crea: es lo mismo que `python -m src.db`.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src import db  # noqa: E402

FILAS_QUE_SE_ENSENAN = 20


def tablas(con) -> list[str]:
    return [
        f["name"]
        for f in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
    ]


def resumen(con) -> None:
    print(f"Base de datos: {db.RUTA_POR_DEFECTO}")
    nombres = tablas(con)
    print(f"{len(nombres)} tablas\n")
    for nombre in nombres:
        cuantas = con.execute(f"SELECT COUNT(*) FROM {nombre}").fetchone()[0]
        columnas = [
            f["name"] for f in con.execute(f"PRAGMA table_info({nombre})")
        ]
        print(f"  {nombre:<18} {cuantas:>6} filas")
        print(f"  {'':<18} {', '.join(columnas)}")
    print(
        "\nLas guerras se guardan al jugarlas: si estan vacias es que todavia "
        "no se ha jugado ninguna con este archivo. Las columnas nuevas se "
        "anaden al arrancar el bot, asi que una base de datos creada antes "
        "puede ensenar menos de las que tiene el codigo hasta que lo arranques."
    )


def contenido(con, tabla: str) -> None:
    if tabla not in tablas(con):
        raise SystemExit(
            f"no existe la tabla '{tabla}'. Las que hay: "
            + ", ".join(tablas(con))
        )
    filas = con.execute(
        f"SELECT * FROM {tabla} ORDER BY rowid DESC LIMIT {FILAS_QUE_SE_ENSENAN}"
    ).fetchall()
    if not filas:
        print(f"La tabla '{tabla}' esta vacia.")
        return
    columnas = filas[0].keys()
    print(" | ".join(columnas))
    for fila in reversed(filas):
        print(" | ".join("" if fila[c] is None else str(fila[c]) for c in columnas))


def main() -> None:
    con = db.conectar()
    db.crear_esquema(con)
    try:
        if len(sys.argv) > 1:
            contenido(con, sys.argv[1])
        else:
            resumen(con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
