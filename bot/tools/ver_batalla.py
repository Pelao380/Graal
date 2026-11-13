r"""Juega una batalla y escribe su registro, para mirarlo con los ojos.

Uso, desde la carpeta bot/:

    .venv\Scripts\python tools/ver_batalla.py
    .venv\Scripts\python tools/ver_batalla.py --a Gilgamesh --b Enkidu --semilla 3

No se conecta a Discord ni hace falta token: juega la batalla con la IA a los
dos lados y enseña lo mismo que leeria un jugador en su menu. El simulador
contesta "cuantas veces gana" con miles de corridas; esto contesta "que paso"
con una sola, que es la pregunta de al lado y no la misma.

Ojo con lo que se ve aqui: el registro **nombra las habilidades**, y el nombre
de una habilidad delata al Servant que la lleva. Por eso en una partida esto
va en privado y al canal no llega nunca.
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.game import ai, personajes  # noqa: E402
from src.game.battle import Batalla, Combatiente, Estado  # noqa: E402
from src.game.servant import NIVEL_MAXIMO, Servant  # noqa: E402

CATALOGO = personajes.cargar()
MAXIMO_TURNOS = 80


def buscar(nombre: str):
    """El primer personaje cuyo nombre empieza asi, como en el simulador."""
    for p in CATALOGO:
        if p.nombre.lower().startswith(nombre.lower()):
            return p
    parecidos = [p.nombre for p in CATALOGO if nombre.lower() in p.nombre.lower()][:8]
    raise SystemExit(
        f"No encuentro '{nombre}' entre {len(CATALOGO)} personajes."
        + (f" Se parecen: {', '.join(parecidos)}" if parecidos else "")
    )


def jugar(a, b, nombres, nivel, semilla, idioma):
    rng = random.Random(semilla)
    batalla = Batalla(
        [
            Combatiente(id="a", nombre=nombres[0], servant=Servant(a, nivel)),
            Combatiente(id="b", nombre=nombres[1], servant=Servant(b, nivel)),
        ],
        rng=rng,
        idioma=idioma,
    )
    while not batalla.terminada and batalla.turno < MAXIMO_TURNOS:
        if batalla.estado is Estado.VOTACION:
            batalla.registrar_votos(
                {c.id: ai.votar_continuar(batalla, c) for c in batalla.vivos}
            )
            continue
        batalla.resolver_turno(
            {c.id: ai.decidir(batalla, c, rng) for c in batalla.vivos}
        )
    return batalla


def main() -> None:
    p = argparse.ArgumentParser(description="Juega una batalla y escribe su registro")
    p.add_argument("--a", default="Emiya")
    p.add_argument("--b", default="Altria Pendragon")
    p.add_argument("--master-a", default="Hikari", help="el Master que lleva a --a")
    p.add_argument("--master-b", default="Rin", help="el Master que lleva a --b")
    p.add_argument("--nivel", type=int, default=NIVEL_MAXIMO)
    p.add_argument("--semilla", type=int, default=7)
    p.add_argument("--idioma", default="es", choices=("es", "en"))
    args = p.parse_args()

    a, b = buscar(args.a), buscar(args.b)
    batalla = jugar(
        a, b, (args.master_a, args.master_b), args.nivel, args.semilla, args.idioma
    )
    print(f"# {args.master_a}: {a.nombre} ({a.clase.value}) nivel {args.nivel}")
    print(f"# {args.master_b}: {b.nombre} ({b.clase.value}) nivel {args.nivel}")
    print(f"# semilla {args.semilla}")
    print()
    for linea in batalla.registro:
        print(linea)


if __name__ == "__main__":
    main()
