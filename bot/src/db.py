"""Persistencia en SQLite.

Un solo archivo (`graal.db`) en la carpeta del proyecto: no hace falta
instalar ni levantar ningun servidor.

Regla de diseno: todos los plazos viven en la tabla `plazos`, no en memoria.
Si el bot se reinicia a mitad de una guerra, al arrancar lee los plazos
vencidos y sigue donde iba.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

RUTA_POR_DEFECTO = Path(__file__).resolve().parent.parent / "graal.db"

ESQUEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS guerras (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id            TEXT NOT NULL,
    canal_id            TEXT NOT NULL,
    creador_id          TEXT NOT NULL,
    preparacion         TEXT NOT NULL DEFAULT '1h',
    idioma              TEXT NOT NULL DEFAULT 'es',
    maximo_dia_segundos INTEGER NOT NULL DEFAULT 86400,
    dia                 INTEGER NOT NULL DEFAULT 0,
    fase                TEXT NOT NULL DEFAULT 'lobby',
    creada_en           TEXT NOT NULL DEFAULT (datetime('now')),
    terminada_en        TEXT
);

CREATE TABLE IF NOT EXISTS masters (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    guerra_id     INTEGER NOT NULL REFERENCES guerras(id) ON DELETE CASCADE,
    usuario_id    TEXT NOT NULL,
    nombre        TEXT NOT NULL,
    es_bot        INTEGER NOT NULL DEFAULT 0,
    derrotas      INTEGER NOT NULL DEFAULT 0,
    sellos        INTEGER NOT NULL DEFAULT 3,
    intentos_npc  INTEGER NOT NULL DEFAULT 0,
    derrotas_npc  INTEGER NOT NULL DEFAULT 0,
    objetivo_id   TEXT,
    eliminado_dia INTEGER,
    UNIQUE (guerra_id, usuario_id)
);

-- Catalogo de personajes. Vive en datos, no en el codigo, para poder
-- cambiarlo sin tocar el juego.
CREATE TABLE IF NOT EXISTS catalogo_servants (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT NOT NULL UNIQUE,
    clase      TEXT NOT NULL,
    activo     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS servants (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id   INTEGER NOT NULL REFERENCES masters(id) ON DELETE CASCADE,
    nombre      TEXT NOT NULL,
    clase       TEXT NOT NULL,
    nivel       INTEGER NOT NULL DEFAULT 1,
    xp          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS combates_npc (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id  INTEGER NOT NULL REFERENCES masters(id) ON DELETE CASCADE,
    dia        INTEGER NOT NULL,
    indice     INTEGER NOT NULL,
    gano       INTEGER NOT NULL,
    xp         INTEGER NOT NULL DEFAULT 0,
    objeto     TEXT,
    jugado_en  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS batallas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guerra_id  INTEGER NOT NULL REFERENCES guerras(id) ON DELETE CASCADE,
    dia        INTEGER NOT NULL,
    estado     TEXT NOT NULL DEFAULT 'pendiente',
    turno      INTEGER NOT NULL DEFAULT 0,
    mensaje_id TEXT,
    simulada   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS participantes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    batalla_id INTEGER NOT NULL REFERENCES batallas(id) ON DELETE CASCADE,
    master_id  INTEGER NOT NULL REFERENCES masters(id) ON DELETE CASCADE,
    vida       INTEGER NOT NULL,
    mana       INTEGER NOT NULL DEFAULT 20,
    np_usado   INTEGER NOT NULL DEFAULT 0,
    defendio   INTEGER NOT NULL DEFAULT 0,
    listo      INTEGER NOT NULL DEFAULT 0,
    por_ia     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (batalla_id, master_id)
);

-- Decisiones ocultas: se guardan al elegir y se revelan al resolver el turno.
CREATE TABLE IF NOT EXISTS decisiones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    batalla_id INTEGER NOT NULL REFERENCES batallas(id) ON DELETE CASCADE,
    turno      INTEGER NOT NULL,
    master_id  INTEGER NOT NULL REFERENCES masters(id) ON DELETE CASCADE,
    accion     TEXT NOT NULL,
    objetivo   INTEGER,
    habilidad  INTEGER,
    UNIQUE (batalla_id, turno, master_id)
);

-- Todos los plazos del juego, para sobrevivir a un reinicio.
CREATE TABLE IF NOT EXISTS plazos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    guerra_id  INTEGER NOT NULL REFERENCES guerras(id) ON DELETE CASCADE,
    batalla_id INTEGER REFERENCES batallas(id) ON DELETE CASCADE,
    tipo       TEXT NOT NULL,  -- preparacion | maximo_dia | listo | turno
    vence_en   TEXT NOT NULL,  -- ISO 8601 en UTC
    atendido   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_plazos_pendientes
    ON plazos (atendido, vence_en);

-- La cuenta de una persona, **fuera de cualquier guerra**. Es la unica tabla
-- que no cuelga de `guerras`, y por eso existe: los griales son lo unico del
-- juego que sobrevive a la guerra en la que se ganaron. El oro no esta aqui a
-- proposito: ese muere con la guerra y vive en `masters`.
CREATE TABLE IF NOT EXISTS cuentas (
    usuario_id      TEXT PRIMARY KEY,
    griales         INTEGER NOT NULL DEFAULT 0,
    guerras_ganadas INTEGER NOT NULL DEFAULT 0
);
"""


def conectar(ruta: str | Path | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(str(ruta or RUTA_POR_DEFECTO))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def crear_esquema(con: sqlite3.Connection) -> None:
    con.executescript(ESQUEMA)
    con.commit()


def plazos_vencidos(con: sqlite3.Connection) -> list[sqlite3.Row]:
    """Plazos que ya vencieron y nadie atendio, por ejemplo tras un reinicio."""
    return con.execute(
        "SELECT * FROM plazos "
        "WHERE atendido = 0 AND vence_en <= datetime('now') "
        "ORDER BY vence_en"
    ).fetchall()


if __name__ == "__main__":
    con = conectar()
    crear_esquema(con)
    print(f"Base de datos lista en {RUTA_POR_DEFECTO}")
