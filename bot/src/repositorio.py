"""Guardar y cargar guerras en SQLite, para que un reinicio no pierda nada.

Esta es la capa que faltaba para cumplir la regla de la casa: **los plazos van
en la base de datos**. No tenia sentido guardar el plazo de una guerra que no
se guardaba, asi que primero van las guerras y el plazo va con ellas, en la
tabla `plazos`.

Dos decisiones que explican casi todo el modulo:

**Una guerra se guarda entera, de una vez.** `guardar()` reescribe sus 7
Masters y sus Servants en lugar de ir apuntando cambios campo a campo. Son 7
filas: cuesta nada y quita de encima la clase de error mas probable de todas,
que es olvidarse de guardar un campo que cambio. Lo unico que se conserva al
reescribir es la fila de la guerra, por su `id`.

**Un Servant se guarda por `collection_no`, no por nombre.** Los nombres no son
unicos (hay dos Cu Chulainn, tres Medusa) y el plantel se regenera. Al cargar
se busca el personaje en el catalogo y se le pegan encima el nivel y la XP. Si
el personaje ya no esta en el catalogo, la guerra no se carga: es mejor
perderla que resucitarla con otro personaje dentro.

Lo que no se guarda a proposito: nada de las batallas. Hoy se pelean enteras
dentro de `dia.cerrar_dia()` y no sobreviven a nada, porque duran un instante.
Cuando existan las batallas por turnos, que duran dias, tendran que guardarse
con las tablas `batallas`, `participantes` y `decisiones`, que ya estan en el
esquema esperando.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from datetime import datetime, timezone

from .game.objetos import Inventario
from .game.personajes import Personaje
from .game.tienda import Cuenta
from .game.servant import Servant
from .game.war import Fase, Guerra, Master

registro = logging.getLogger(__name__)

# Columnas que el esquema original no tenia. Se anaden al arrancar si faltan,
# para no obligar a borrar un graal.db que ya exista.
COLUMNAS_NUEVAS = {
    "guerras": {
        "sin_repartir": "TEXT NOT NULL DEFAULT '[]'",
        "orden_declaraciones": "TEXT NOT NULL DEFAULT '[]'",
    },
    "masters": {
        "listo": "INTEGER NOT NULL DEFAULT 0",
        # A quien le ha visto el Servant. Una lista JSON de ids: es del
        # Master, no se consulta por separado y no tiene identidad propia.
        "conocidos": "TEXT NOT NULL DEFAULT '[]'",
        # Lo que lleva encima: un JSON de clave a cuantos. Va en una columna
        # y no en una tabla por lo mismo que `conocidos`: es del Master, no se
        # consulta por separado y se guarda y se lee de una vez. Lo que **no**
        # se guarda es cuantos objetos uso en la batalla de hoy, porque una
        # batalla no sobrevive a un reinicio (ver `self.combates` del Cog).
        "inventario": "TEXT NOT NULL DEFAULT '{}'",
        # El oro de la tienda. Va en la fila del Master y no en `cuentas`
        # porque **muere con la guerra**: ver la cabecera de `game/tienda.py`.
        "oro": "INTEGER NOT NULL DEFAULT 0",
        # Se rindio. Esto si tiene que sobrevivir a un reinicio: si no, el
        # que se fue volveria a la guerra en la siguiente carga.
        "retirado": "INTEGER NOT NULL DEFAULT 0",
    },
    "servants": {"collection_no": "INTEGER"},
}

TIPO_PLAZO_PREPARACION = "preparacion"


# --- esquema ---


def migrar(con: sqlite3.Connection) -> None:
    """Crea lo que falte y anade las columnas nuevas. Se puede repetir."""
    from . import db

    db.crear_esquema(con)
    for tabla, columnas in COLUMNAS_NUEVAS.items():
        existentes = {
            f["name"] for f in con.execute(f"PRAGMA table_info({tabla})")
        }
        for nombre, tipo in columnas.items():
            if nombre not in existentes:
                con.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {tipo}")
                registro.info("columna nueva: %s.%s", tabla, nombre)
    con.commit()


# --- fechas ---


def _a_iso(epoch: float) -> str:
    """Un instante en segundos a ISO 8601 en UTC, como lo guarda `plazos`."""
    return (
        datetime.fromtimestamp(epoch, tz=timezone.utc)
        .replace(tzinfo=None)
        .isoformat(sep=" ", timespec="seconds")
    )


def _de_iso(texto: str) -> float:
    return (
        datetime.fromisoformat(texto)
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


# --- guardar ---


def guardar(con: sqlite3.Connection, guerra: Guerra) -> int:
    """Guarda una guerra entera y devuelve su id en la base de datos."""
    id_ = _guardar_guerra(con, guerra)
    _guardar_masters(con, id_, guerra)
    _guardar_plazo(con, id_, guerra)
    con.commit()
    return id_


def _id_de(con: sqlite3.Connection, guerra: Guerra) -> int | None:
    fila = con.execute(
        "SELECT id FROM guerras WHERE canal_id = ? AND terminada_en IS NULL",
        (guerra.canal_id,),
    ).fetchone()
    return fila["id"] if fila else None


def _guardar_guerra(con: sqlite3.Connection, guerra: Guerra) -> int:
    datos = (
        guerra.canal_id,
        guerra.creador_id,
        guerra.preparacion,
        guerra.idioma,
        guerra.maximo_dia_segundos,
        guerra.dia,
        guerra.fase.value,
        json.dumps(_fichas_sin_repartir(guerra)),
        json.dumps(guerra.orden_declaraciones),
        # Una guerra terminada se marca y deja de cargarse, pero no se borra:
        # sirve para saber quien gano cada una.
        _a_iso(time.time()) if guerra.terminada else None,
    )
    id_ = _id_de(con, guerra)
    if id_ is None:
        cursor = con.execute(
            "INSERT INTO guerras (guild_id, canal_id, creador_id, preparacion,"
            " idioma, maximo_dia_segundos, dia, fase, sin_repartir,"
            " orden_declaraciones, terminada_en)"
            " VALUES ('', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            datos,
        )
        return int(cursor.lastrowid)
    con.execute(
        "UPDATE guerras SET canal_id = ?, creador_id = ?, preparacion = ?,"
        " idioma = ?, maximo_dia_segundos = ?, dia = ?, fase = ?,"
        " sin_repartir = ?, orden_declaraciones = ?, terminada_en = ?"
        " WHERE id = ?",
        (*datos, id_),
    )
    return id_


def _ficha_de(personaje: Personaje) -> int | str:
    """Con que se identifica un personaje: su collectionNo, o su nombre."""
    return (
        personaje.collection_no
        if personaje.collection_no is not None
        else personaje.nombre
    )


def _fichas_sin_repartir(guerra: Guerra) -> list[int | str]:
    return [_ficha_de(s.personaje) for s in guerra.sin_repartir]


def _guardar_masters(con: sqlite3.Connection, id_: int, guerra: Guerra) -> None:
    # Reescribir en vez de actualizar campo a campo: ver la cabecera. El
    # borrado se lleva los servants por el ON DELETE CASCADE.
    con.execute("DELETE FROM masters WHERE guerra_id = ?", (id_,))
    for m in guerra.masters.values():
        cursor = con.execute(
            "INSERT INTO masters (guerra_id, usuario_id, nombre, es_bot,"
            " derrotas, sellos, intentos_npc, derrotas_npc, objetivo_id,"
            " listo, conocidos, inventario, oro, retirado)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                id_,
                m.id,
                m.nombre,
                int(m.es_bot),
                m.derrotas,
                m.sellos,
                m.intentos_npc,
                m.derrotas_npc,
                m.objetivo,
                int(m.listo),
                json.dumps(sorted(m.conocidos)),
                json.dumps(m.inventario.cuantos, sort_keys=True),
                m.oro,
                int(m.retirado),
            ),
        )
        if m.servant is not None:
            s = m.servant
            con.execute(
                "INSERT INTO servants (master_id, nombre, clase, nivel, xp,"
                " collection_no) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    int(cursor.lastrowid),
                    s.personaje.nombre,
                    s.clase.value,
                    s.nivel,
                    s.xp,
                    s.personaje.collection_no,
                ),
            )


def _guardar_plazo(con: sqlite3.Connection, id_: int, guerra: Guerra) -> None:
    """Deja un solo plazo de preparacion por guerra, el del dia en curso.

    Los de dias pasados se marcan atendidos en lugar de borrarse: si alguna
    vez hay que entender por que una guerra fue como fue, la lista de plazos
    es media respuesta.
    """
    con.execute(
        "UPDATE plazos SET atendido = 1 WHERE guerra_id = ? AND tipo = ?",
        (id_, TIPO_PLAZO_PREPARACION),
    )
    if guerra.terminada or guerra.fase is not Fase.PREPARACION:
        return
    con.execute(
        "INSERT INTO plazos (guerra_id, tipo, vence_en, atendido)"
        " VALUES (?, ?, ?, 0)",
        (id_, TIPO_PLAZO_PREPARACION, _a_iso(guerra.vence_preparacion)),
    )


# --- cargar ---


def cargar_todas(
    con: sqlite3.Connection, catalogo: list[Personaje]
) -> dict[int, Guerra]:
    """Las guerras sin terminar, listas para seguir jugandose.

    Devuelve lo que el Cog usa: canal_id (entero, como lo da Discord) a
    `Guerra`. Una guerra que no se puede reconstruir se deja estar y se
    registra, para que un dato raro no impida arrancar el bot.
    """
    por_ficha: dict[int | str, Personaje] = {}
    for p in catalogo:
        por_ficha[_ficha_de(p)] = p

    guerras: dict[int, Guerra] = {}
    for fila in con.execute(
        "SELECT * FROM guerras WHERE terminada_en IS NULL ORDER BY id"
    ):
        try:
            guerra = _cargar_guerra(con, fila, por_ficha)
        except (KeyError, ValueError) as e:
            registro.warning(
                "no pude cargar la guerra %s del canal %s: %s",
                fila["id"],
                fila["canal_id"],
                e,
            )
            continue
        guerras[int(guerra.canal_id)] = guerra
    return guerras


def _servant_de(fila: sqlite3.Row, por_ficha: dict[int | str, Personaje]) -> Servant:
    ficha = (
        fila["collection_no"]
        if fila["collection_no"] is not None
        else fila["nombre"]
    )
    if ficha not in por_ficha:
        raise KeyError(f"el catalogo ya no tiene a {fila['nombre']!r} ({ficha})")
    return Servant(personaje=por_ficha[ficha], nivel=fila["nivel"], xp=fila["xp"])


def _cargar_guerra(
    con: sqlite3.Connection,
    fila: sqlite3.Row,
    por_ficha: dict[int | str, Personaje],
) -> Guerra:
    guerra = Guerra(
        id=str(fila["canal_id"]),
        canal_id=str(fila["canal_id"]),
        preparacion=fila["preparacion"],
        maximo_dia_segundos=fila["maximo_dia_segundos"],
        dia=fila["dia"],
        fase=Fase(fila["fase"]),
        creador_id=fila["creador_id"],
        idioma=fila["idioma"],
    )
    guerra.sin_repartir = [
        Servant(personaje=por_ficha[f])
        for f in _fichas_guardadas(fila["sin_repartir"], por_ficha)
    ]
    guerra.orden_declaraciones = list(json.loads(fila["orden_declaraciones"]))

    for m in con.execute(
        "SELECT * FROM masters WHERE guerra_id = ? ORDER BY id", (fila["id"],)
    ):
        master = Master(
            id=m["usuario_id"],
            nombre=m["nombre"],
            derrotas=m["derrotas"],
            sellos=m["sellos"],
            intentos_npc=m["intentos_npc"],
            derrotas_npc=m["derrotas_npc"],
            objetivo=m["objetivo_id"],
            idioma=guerra.idioma,
            es_bot=bool(m["es_bot"]),
            listo=bool(m["listo"]),
            conocidos=set(json.loads(m["conocidos"])),
            inventario=_inventario_de(m["inventario"]),
            oro=m["oro"],
            retirado=bool(m["retirado"]),
        )
        servant = con.execute(
            "SELECT * FROM servants WHERE master_id = ?", (m["id"],)
        ).fetchone()
        if servant is not None:
            master.servant = _servant_de(servant, por_ficha)
        guerra.masters[master.id] = master

    guerra.vence_preparacion = _plazo_de(con, fila["id"], guerra)
    return guerra


def _inventario_de(texto: str | None) -> Inventario:
    """El inventario desde su JSON. Un dato raro no impide cargar la guerra.

    Es la misma politica que con los Servants que ya no estan en el catalogo,
    pero al contrario: alli se descarta la guerra entera porque resucitarla
    con otro personaje dentro seria peor que perderla, y aqui no, porque el
    inventario es un adorno y la guerra se puede seguir jugando sin el.
    """
    try:
        cuantos = json.loads(texto or "{}")
    except ValueError:
        registro.warning("inventario ilegible, se carga vacio: %r", texto)
        return Inventario()
    if not isinstance(cuantos, dict):
        return Inventario()
    limpio = {
        str(k): int(v)
        for k, v in cuantos.items()
        if isinstance(v, int) and v > 0
    }
    return Inventario(cuantos=limpio)


# --- las cuentas: los griales, que no son de ninguna guerra ---


def cargar_cuenta(con: sqlite3.Connection, usuario_id: str) -> Cuenta:
    """La cuenta de alguien, o una a 0 si todavia no tiene fila.

    No se crea la fila al leer a proposito: la mayoria de la gente nunca va a
    tener griales, y una tabla con una fila por cada persona que entro una vez
    a una guerra no sirve para nada. La fila la escribe `guardar_cuenta`, que
    la llama quien gana o quien compra.
    """
    fila = con.execute(
        "SELECT * FROM cuentas WHERE usuario_id = ?", (str(usuario_id),)
    ).fetchone()
    if fila is None:
        return Cuenta(usuario_id=str(usuario_id))
    return Cuenta(
        usuario_id=fila["usuario_id"],
        griales=fila["griales"],
        guerras_ganadas=fila["guerras_ganadas"],
    )


def guardar_cuenta(con: sqlite3.Connection, cuenta: Cuenta) -> None:
    """Escribe la cuenta entera. Crea la fila si no estaba."""
    con.execute(
        "INSERT INTO cuentas (usuario_id, griales, guerras_ganadas)"
        " VALUES (?, ?, ?)"
        " ON CONFLICT(usuario_id) DO UPDATE SET"
        " griales = excluded.griales,"
        " guerras_ganadas = excluded.guerras_ganadas",
        (cuenta.usuario_id, cuenta.griales, cuenta.guerras_ganadas),
    )
    con.commit()


def _fichas_guardadas(
    texto: str, por_ficha: dict[int | str, Personaje]
) -> list[int | str]:
    fichas = list(json.loads(texto))
    faltan = [f for f in fichas if f not in por_ficha]
    if faltan:
        raise KeyError(f"el catalogo ya no tiene estas fichas: {faltan}")
    return fichas


def _plazo_de(con: sqlite3.Connection, id_: int, guerra: Guerra) -> float:
    """El plazo de preparacion guardado, o uno nuevo si no hay ninguno.

    Si no hay plazo pero la guerra esta en preparacion, se le da la ventana
    entera desde ahora. Pasa con una guerra guardada antes de que existieran
    los plazos, y es lo generoso: nadie pierde el dia por un cambio de
    version.
    """
    fila = con.execute(
        "SELECT vence_en FROM plazos"
        " WHERE guerra_id = ? AND tipo = ? AND atendido = 0"
        " ORDER BY vence_en DESC LIMIT 1",
        (id_, TIPO_PLAZO_PREPARACION),
    ).fetchone()
    if fila is None:
        return guerra.reloj() + guerra.segundos_preparacion
    return _de_iso(fila["vence_en"])
