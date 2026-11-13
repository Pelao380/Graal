"""Simulador para balancear los numeros sin encender el bot.

Ejemplos (desde la carpeta bot/):

    python -m src.simulator --semilla 7 niveles
    python -m src.simulator --semilla 7 triangulo
    python -m src.simulator --semilla 7 duelo --a Emiya --b "Artoria Pendragon"
    python -m src.simulator --semilla 7 plantel
    python -m src.simulator --semilla 7 npc --dia 1
    python -m src.simulator --semilla 7 grupal
    python -m src.simulator --semilla 7 habilidades
    python -m src.simulator --semilla 7 guerras
"""

from __future__ import annotations

import argparse
import random
import statistics
from dataclasses import replace

from .game import ai, battle, invocacion, npc, personajes
from .game.battle import Batalla, Combatiente, Estado
from .game.clases import multiplicador_triangulo
from .game.npc import vida_inicial
from .game.objetos import OBJETOS_POR_BATALLA
from .game.personajes import SIN_HABILIDADES, Efecto, Personaje
from .game.servant import NIVELES_HABILIDAD, Servant, xp_acumulada
from .game.tienda import ORO_POR_BATALLA_GANADA, PRECIO_EN_ORO
from .game.war import Guerra

CATALOGO = personajes.cargar()
POR_NOMBRE = {p.nombre: p for p in CATALOGO}


def _buscar(nombre: str) -> Personaje:
    for p in CATALOGO:
        if p.nombre.lower().startswith(nombre.lower()):
            return p
    parecidos = [p.nombre for p in CATALOGO if nombre.lower() in p.nombre.lower()][:8]
    raise SystemExit(
        f"No encuentro '{nombre}' entre {len(CATALOGO)} personajes."
        + (f" Se parecen: {', '.join(parecidos)}" if parecidos else "")
    )


def _jugar(batalla: Batalla, rng: random.Random, max_turnos: int = 80) -> None:
    """Juega una batalla completa con la IA en todos los lados."""
    while not batalla.terminada and batalla.turno < max_turnos:
        if batalla.estado is Estado.VOTACION:
            votos = {c.id: ai.votar_continuar(batalla, c) for c in batalla.vivos}
            batalla.registrar_votos(votos)
            continue
        decisiones = {c.id: ai.decidir(batalla, c, rng) for c in batalla.vivos}
        batalla.resolver_turno(decisiones)


def _enfrentar(
    a: Personaje,
    b: Personaje,
    nivel_a: int,
    nivel_b: int,
    n: int,
    rng: random.Random,
) -> tuple[float, float]:
    """Devuelve (tasa de victoria de A, turnos medios)."""
    victorias = 0
    turnos: list[int] = []
    for _ in range(n):
        batalla = Batalla(
            [
                Combatiente(
                    id="a", nombre=a.nombre, servant=Servant(a, nivel_a)
                ),
                Combatiente(
                    id="b", nombre=b.nombre, servant=Servant(b, nivel_b)
                ),
            ],
            rng=rng,
        )
        _jugar(batalla, rng)
        g = batalla.ganador()
        if g and g.id == "a":
            victorias += 1
        turnos.append(batalla.turno)
    return victorias / n, statistics.mean(turnos)


def duelo(nombre_a: str, nombre_b: str, nivel_a: int, nivel_b: int, n: int, s) -> None:
    rng = random.Random(s)
    a, b = _buscar(nombre_a), _buscar(nombre_b)
    tasa, turnos = _enfrentar(a, b, nivel_a, nivel_b, n, rng)
    tri = multiplicador_triangulo(a.clase, b.clase)
    print(f"{a.nombre} ({a.clase.value}) nivel {nivel_a}")
    print(f"  contra {b.nombre} ({b.clase.value}) nivel {nivel_b}")
    print(f"  Triangulo: x{tri:.2f} a favor del primero")
    print(f"  Victorias del primero: {tasa:.1%} en {n} combates")
    print(f"  Turnos medios: {turnos:.1f}")


def niveles(n: int, s, nombre: str = "Altria Pendragon") -> None:
    """Cuanto decide el nivel. Es la medida del determinismo."""
    rng = random.Random(s)
    base = _buscar(nombre)
    print(f"Mismo personaje, distinto nivel ({base.nombre} contra si mismo)")
    print("  diferencia | victorias del nivel mas alto | turnos")
    for diferencia in (0, 1, 2, 3, 5, 10, 14):
        tasa, turnos = _enfrentar(base, base, 1 + diferencia, 1, n, rng)
        print(f"  {diferencia:>10} | {tasa:>27.1%} | {turnos:>6.1f}")


def _retocados() -> list[Personaje]:
    """Los personajes con ficha escrita a mano, que son los que tienen rasgo."""
    conservados = [p for p in CATALOGO if p.rasgo.descripcion]
    return conservados or CATALOGO[:8]


def triangulo(n: int, s) -> None:
    """Cuanto decide el emparejamiento de clases, a igual nivel."""
    rng = random.Random(s)
    elegidos = _retocados()
    ancho = max(len(p.nombre) for p in elegidos) + 1
    print(f"Victorias de la fila contra la columna, mismo nivel, {n} combates")
    print(" " * ancho + "".join(f"{p.clase.value[:4]:>7}" for p in elegidos))
    for a in elegidos:
        fila = []
        for b in elegidos:
            if a is b:
                fila.append("    -  ")
                continue
            tasa, _ = _enfrentar(a, b, 1, 1, n, rng)
            fila.append(f"{tasa:>6.0%} ")
        print(f"{a.nombre[:ancho - 1]:<{ancho}}" + "".join(fila))


def habilidades(
    n: int,
    s,
    nivel: int,
    muestra: int,
    escala: float = 1.0,
    efecto: str | None = None,
) -> None:
    """Cuanto pesan las habilidades: el mismo personaje con y sin ellas.

    Usar una habilidad gasta el turno entero, asi que no es gratis: si la
    tasa ronda el 50%, lo que dan los efectos empata con el ataque que
    cuestan, y si baja de ahi es que no pagan y hay que subir la escala.

    `--escala` multiplica todos los efectos, para buscar donde empatan.
    `--efecto` se queda con los personajes que llevan sobre todo ese efecto
    (2 de sus 3 habilidades), que es como se calibra uno por uno.
    """
    rng = random.Random(s)
    if escala != 1.0:
        for e in list(battle.ESCALA_EFECTO):
            battle.ESCALA_EFECTO[e] = escala
    cuantas = min(3, sum(1 for umbral in NIVELES_HABILIDAD if nivel >= umbral))

    candidatos = CATALOGO
    if efecto:
        buscado = Efecto(efecto)
        candidatos = [
            p
            for p in CATALOGO
            if sum(1 for h in p.habilidades[:cuantas] if h.efecto is buscado) >= 2
        ]
        if not candidatos:
            raise SystemExit(f"ningun personaje lleva sobre todo {efecto}")
    elegidos = (
        candidatos if muestra >= len(candidatos) else rng.sample(candidatos, muestra)
    )
    resultados: list[tuple[float, Personaje]] = []
    por_efecto: dict[str, list[float]] = {}
    turnos_medios: list[float] = []

    for p in elegidos:
        desnudo = replace(p, habilidades=SIN_HABILIDADES)
        tasa, turnos = _enfrentar(p, desnudo, nivel, nivel, n, rng)
        resultados.append((tasa, p))
        turnos_medios.append(turnos)
        efectos = {
            h.efecto for h in p.habilidades[:cuantas] if h.hace_algo
        } or {Efecto.NINGUNO}
        for e in efectos:
            por_efecto.setdefault(e.value, []).append(tasa)

    resultados.sort(key=lambda x: x[0])
    tasas = [t for t, _ in resultados]
    print(
        f"El mismo personaje con habilidades contra si mismo sin ellas, "
        f"nivel {nivel} ({cuantas} habilidades), {len(elegidos)} personajes "
        f"x {n} combates, escala x{escala:g}"
        + (f", solo los de {efecto}" if efecto else "")
    )
    print(f"  victorias del que las tiene: media {statistics.mean(tasas):.1%}, "
          f"mediana {statistics.median(tasas):.1%}, "
          f"minimo {min(tasas):.1%}, maximo {max(tasas):.1%}")
    print(f"  turnos medios: {statistics.mean(turnos_medios):.1f}")
    print("\n  Por efecto (un personaje cuenta en cada efecto que tiene):")
    for efecto, valores in sorted(por_efecto.items(), key=lambda x: -statistics.mean(x[1])):
        print(f"    {efecto:<9} {len(valores):>4} personajes  "
              f"{statistics.mean(valores):>6.1%}")
    print("\n  Los 5 que mas sacan de sus habilidades:")
    for t, p in resultados[-5:]:
        print(f"    {t:>6.1%}  {p.nombre:<34} "
              + ", ".join(
                  f"{h.nombre} ({h.efecto.value})" for h in p.habilidades[:cuantas]
              )[:70])
    print("\n  Los 5 que menos:")
    for t, p in resultados[:5]:
        print(f"    {t:>6.1%}  {p.nombre:<34} "
              + ", ".join(
                  f"{h.nombre} ({h.efecto.value})" for h in p.habilidades[:cuantas]
              )[:70])


def plantel(rivales: int, n: int, s, nivel: int = 1) -> None:
    """Busca personajes rotos en el plantel completo.

    Cada personaje pelea contra rivales al azar, al mismo nivel. Si el plantel
    esta sano, todos deberian rondar el 50%. Con `--nivel 15` entran tambien
    las habilidades, que es donde el plantel se puede desequilibrar.
    """
    rng = random.Random(s)
    resultados: list[tuple[float, Personaje]] = []
    for p in CATALOGO:
        ganados = 0
        for _ in range(rivales):
            rival = rng.choice([o for o in CATALOGO if o is not p])
            tasa, _ = _enfrentar(p, rival, nivel, nivel, n, rng)
            ganados += tasa
        resultados.append((ganados / rivales, p))

    resultados.sort(key=lambda x: x[0])
    tasas = [t for t, _ in resultados]
    print(f"Plantel de {len(CATALOGO)} personajes de nivel {nivel}, {rivales} "
          f"rivales al azar x {n} combates cada uno")
    print(f"  victorias: minimo {min(tasas):.1%}, mediana "
          f"{statistics.median(tasas):.1%}, maximo {max(tasas):.1%}")
    print(f"  desviacion: {statistics.pstdev(tasas):.1%}")
    fuera = [(t, p) for t, p in resultados if t < 0.35 or t > 0.65]
    print(f"  fuera de la banda 35-65%: {len(fuera)}")
    print("\n  Los 8 mas debiles:")
    for t, p in resultados[:8]:
        print(f"    {t:>6.1%}  {p.nombre:<34} {p.clase.value:<10} "
              f"{p.mult_vida:.2f}/{p.mult_ataque:.2f}/{p.mult_velocidad:.2f}")
    print("\n  Los 8 mas fuertes:")
    for t, p in resultados[-8:]:
        print(f"    {t:>6.1%}  {p.nombre:<34} {p.clase.value:<10} "
              f"{p.mult_vida:.2f}/{p.mult_ataque:.2f}/{p.mult_velocidad:.2f}")


def combates_npc(dia: int | None, n: int, s, muestra: int = 30) -> None:
    """La escalera de entrenamiento: victorias y XP por dia y por nivel.

    Dos cosas que este modo no medía y por las que no se vio un acantilado
    que estuvo meses ahi (el 4.o NPC pasaba del 84% el dia 3 al 5% el dia 7):

    - **Media un solo personaje** (Altria). El factor de dificultad es
      relativo al Servant del jugador, asi que un personaje no dice nada del
      plantel; ahora usa una muestra.
    - **Media un solo dia.** El endurecimiento por dia es justo donde se
      rompia, asi que sin `--dia` recorre los dias 1, 3, 5 y 7.

    Lo que hay que mirar: que ninguna columna se desplome de un dia para otro,
    que las cuatro se puedan ganar, y que la XP por dia baje con los dias sin
    hundirse.
    """
    rng = random.Random(s)
    elegidos = (
        CATALOGO if muestra >= len(CATALOGO) else random.Random(s).sample(CATALOGO, muestra)
    )
    dias = [dia] if dia is not None else [1, 3, 5, 7]
    print(
        f"Combates NPC, {len(elegidos)} personajes x {n} intentos por nivel y "
        f"rival\nFactores {npc.FACTOR_DIFICULTAD}, endurecimiento "
        f"{npc.ENDURECIMIENTO_POR_DIA:.0%}/dia, tope {npc.FACTOR_MAXIMO}"
    )
    print("  dia | nivel | NPC 1 | NPC 2 | NPC 3 | NPC 4 | XP media del dia")
    for d in dias:
        for nivel in (1, 5, 10, 15):
            tasas = []
            for indice in range(4):
                ganados = sum(
                    1
                    for base in elegidos
                    for _ in range(n)
                    if npc.pelear(Servant(base, nivel), indice, d, rng).gano
                )
                tasas.append(ganados / (len(elegidos) * n))
            xp = sum(t * x for t, x in zip(tasas, npc.XP_POR_VICTORIA))
            print(
                f"  {d:>3} | {nivel:>5} | "
                + " | ".join(f"{t:>5.0%}" for t in tasas)
                + f" | {xp:>5.1f}"
            )
    print(f"\n  XP para el nivel 15: {xp_acumulada(15)}")


def grupal(jugadores: int, n: int, s) -> None:
    rng = random.Random(s)
    turnos: list[int] = []
    victorias: dict[str, int] = {}
    for _ in range(n):
        elegidos = rng.sample(CATALOGO, jugadores)
        combatientes = [
            Combatiente(id=str(i), nombre=p.nombre, servant=Servant(p, 1))
            for i, p in enumerate(elegidos)
        ]
        batalla = Batalla(combatientes, rng=rng)
        _jugar(batalla, rng)
        turnos.append(batalla.turno)
        g = batalla.ganador()
        if g:
            victorias[g.nombre] = victorias.get(g.nombre, 0) + 1

    total = sum(victorias.values())
    print(f"Batallas de {jugadores} al azar, mismo nivel, {n} combates")
    for nombre, v in sorted(victorias.items(), key=lambda x: -x[1]):
        print(f"  {nombre:<20} {v / total:>6.1%}")
    print(f"  Turnos: media {statistics.mean(turnos):.1f}, maximo {max(turnos)}")


def _jugar_batalla_de_guerra(
    guerra: Guerra, grupo: list[str], rng: random.Random, max_turnos: int = 60
) -> list[str]:
    """Pelea una batalla del dia y devuelve **todos** los que cayeron.

    Eran solo el primero, y era el mismo error que tenia `dia.anotar_batalla`:
    si la batalla sigue despues de la votacion puede caer otro, y esa derrota
    se perdia. Afecta a lo que mide el modo `guerras`.
    """
    combatientes = [
        Combatiente(
            id=id_,
            nombre=guerra.masters[id_].nombre,
            servant=guerra.masters[id_].servant,
            vida=vida_inicial(
                guerra.masters[id_].servant, guerra.masters[id_].derrotas_npc
            ),
        )
        for id_ in grupo
    ]
    batalla = Batalla(combatientes, rng=rng)
    _jugar(batalla, rng, max_turnos)
    return list(batalla.caidos)


def _jugar_guerra(
    humanos: int, rng: random.Random, max_dias: int = 30
) -> tuple[bool, bool, int]:
    """Juega una guerra entera con `humanos` personas y el resto bots.

    Devuelve (gano una persona, se entrego el Grial, dias que duro). A los
    humanos los juega la misma IA que a los bots: lo que se mide asi es si la
    mesa es justa, no quien juega mejor.

    El oro se va sumando en los Masters mientras se juega, igual que en el
    bot, asi que el modo `economia` puede leerlo de la guerra al acabar. Lo que
    nadie gasta es ese oro: la IA no compra. Ver `puntos-abiertos.md`.
    """
    guerra = Guerra(id="sim", canal_id="sim", rng=rng)
    for i in range(humanos):
        guerra.inscribir(f"h{i}", f"Humano {i + 1}")
    guerra.rellenar_con_bots()
    guerra.empezar(invocacion.invocar(CATALOGO, rng))

    while not guerra.terminada and guerra.dia <= max_dias:
        # Los bots ya invocaron, entrenaron y declararon en `abrir_dia`, que
        # corre dentro de `empezar` y `siguiente_dia`. Aqui solo quedan las
        # personas, que invocan enseguida y entrenan lo mismo: medir al que
        # espera a proposito es otra pregunta, y esperar solo le quita
        # entrenamiento, porque `formar_batallas` le invoca igual.
        for m in guerra.sin_invocar:
            guerra.invocar_para(m.id, rng)
        for m in guerra.humanos:
            if m.eliminado:
                continue
            while m.intentos_npc < npc.COMBATES_POR_DIA:
                resultado = npc.pelear(m.servant, m.intentos_npc, guerra.dia, rng)
                m.intentos_npc += 1
                if resultado.gano:
                    m.servant.ganar_xp(resultado.xp)
                    # El oro, como en `commands.pelear_npc`: lo cobra quien
                    # juega, no `npc.pelear`.
                    m.oro += resultado.oro
                else:
                    m.derrotas_npc += 1

        # Las declaraciones de las personas, en orden al azar, como llegarian
        # de Discord. Desde que `formar_batallas` sortea quien se queda fuera
        # el orden ya no cambia nada; cuando decidia, moverlo le valia al mismo
        # jugador del 10% al 27% de victorias.
        declarantes = [m.id for m in guerra.activos if not m.es_bot]
        rng.shuffle(declarantes)
        for id_ in declarantes:
            rivales = [o for o in guerra.activos if o.id != id_]
            if rivales:
                guerra.declarar_ataque(id_, rng.choice(rivales).id)

        batallas, _ = guerra.formar_batallas(rng)
        for grupo in batallas:
            caidos = _jugar_batalla_de_guerra(guerra, grupo, rng)
            for caido in caidos:
                guerra.registrar_derrota(caido)
            # El oro de ganar la batalla, igual que en `dia.anotar_batalla`:
            # cobra quien sale en pie de una batalla que tumbo a alguien. Este
            # camino no pasa por `anotar_batalla` (ver su comentario), asi que
            # hay que pagarlo aqui tambien, y es la misma trampa de siempre:
            # dos caminos que tienen que dejar la misma mesa.
            if caidos:
                for id_ in grupo:
                    if id_ not in caidos:
                        guerra.masters[id_].oro += ORO_POR_BATALLA_GANADA
        guerra.siguiente_dia()

    ganador = guerra.ganador()
    gano_persona = ganador is not None and not ganador.es_bot
    _ultima_guerra.append(guerra)
    return gano_persona, guerra.gana_el_grial() is not None, guerra.dia


# La guerra que se acaba de jugar, para que `economia` pueda mirarle el oro sin
# cambiarle la forma del resultado a `guerras`, que es lo que mide la justicia
# y conviene no tocar. Solo se guarda la ultima.
_ultima_guerra: list[Guerra] = []


def economia(n: int, s, humanos: int = 4) -> None:
    """Cuanto oro da una guerra, y que se compra con eso.

    Esta es la medida que justifica los precios de `tienda.PRECIO_EN_ORO`: si
    una guerra diera 1000 de oro, los precios sobrarian y se compraria todo; si
    diera 50, la tienda seria un adorno. Lo que se busca es que dé para armarse
    en las batallas que vas a pelear y poco mas.

    Lo que esto **no** mide es si los objetos estan bien de valor: la IA no los
    usa. Ver `puntos-abiertos.md`.
    """
    rng = random.Random(s)
    oros: list[int] = []
    dias: list[int] = []
    for _ in range(n):
        _ultima_guerra.clear()
        _, _, d = _jugar_guerra(humanos, rng)
        dias.append(d)
        guerra = _ultima_guerra[-1]
        oros.extend(m.oro for m in guerra.humanos)

    oros.sort()
    medio = statistics.mean(oros)
    print(f"Economia de {n} guerras de {humanos} personas, {len(oros)} Masters")
    print(f"  dias por guerra:  {statistics.mean(dias):.1f}")
    print(f"  oro por Master:   {medio:.0f} de media")
    print(
        f"                    {oros[len(oros) // 10]:.0f} el decil bajo, "
        f"{statistics.median(oros):.0f} la mediana, "
        f"{oros[-len(oros) // 10]:.0f} el decil alto"
    )
    barato = min(PRECIO_EN_ORO.values())
    caro = max(PRECIO_EN_ORO.values())
    todo = sum(PRECIO_EN_ORO.values())
    print(f"  objetos baratos:  {medio / barato:.1f} con el oro medio ({barato} c/u)")
    print(f"  objetos caros:    {medio / caro:.1f} con el oro medio ({caro} c/u)")
    print(f"  comprarlo todo:   {todo} ({todo / medio:.1f} guerras)")
    print(
        "  objetos usables en combate en toda la guerra: "
        f"{OBJETOS_POR_BATALLA} por batalla"
    )


def guerras(n: int, s) -> None:
    """Guerras completas con distinta cantidad de gente.

    Con los humanos jugados por la IA, una mesa justa reparte las victorias a
    partes iguales: 1 de 7 para una persona sola contra 6 bots.
    """
    rng = random.Random(s)
    print(f"Guerras completas, {n} por cada cantidad de personas")
    print("  personas | victorias de una persona | esperado | Grial | dias")
    for humanos in (1, 2, 4, 7):
        gana_persona = griales = 0
        dias: list[int] = []
        for _ in range(n):
            persona, grial, d = _jugar_guerra(humanos, rng)
            gana_persona += persona
            griales += grial
            dias.append(d)
        esperado = humanos / 7
        print(
            f"  {humanos:>8} | {gana_persona / n:>24.1%} | {esperado:>8.1%} | "
            f"{griales / n:>5.0%} | {statistics.mean(dias):>4.1f}"
        )


def invocaciones(n: int, s) -> None:
    rng = random.Random(s)
    rulers = 0
    for _ in range(n):
        if any(s_.clase.value == "Ruler" for s_ in invocacion.invocar(CATALOGO, rng)):
            rulers += 1
    print(f"Guerras simuladas: {n}")
    print(f"  Con Ruler: {rulers / n:.1%} (esperado 5%)")


def main() -> None:
    p = argparse.ArgumentParser(description="Simulador de combates de Graal")
    p.add_argument("--semilla", type=int, default=None)
    sub = p.add_subparsers(dest="modo", required=True)

    d = sub.add_parser("duelo", help="dos personajes concretos")
    d.add_argument("--a", default="Artoria")
    d.add_argument("--b", default="Emiya")
    d.add_argument("--nivel-a", type=int, default=1)
    d.add_argument("--nivel-b", type=int, default=1)
    d.add_argument("-n", type=int, default=1000)

    nv = sub.add_parser("niveles", help="cuanto decide el nivel")
    nv.add_argument("-n", type=int, default=500)
    nv.add_argument("--nombre", default="Altria Pendragon")

    tr = sub.add_parser("triangulo", help="matriz de emparejamientos")
    tr.add_argument("-n", type=int, default=200)

    c = sub.add_parser("npc", help="tasa de victoria contra los 4 NPC")
    c.add_argument("--dia", type=int, default=None, help="por defecto 1, 3, 5 y 7")
    c.add_argument("-n", type=int, default=10)
    c.add_argument("--muestra", type=int, default=30)

    g = sub.add_parser("grupal", help="batalla de 3 o 4")
    g.add_argument("--jugadores", type=int, default=4, choices=(2, 3, 4))
    g.add_argument("-n", type=int, default=500)

    pl = sub.add_parser("plantel", help="busca personajes rotos entre los 348")
    pl.add_argument("--rivales", type=int, default=12)
    pl.add_argument("-n", type=int, default=30)
    pl.add_argument("--nivel", type=int, default=1)

    hb = sub.add_parser("habilidades", help="cuanto pesan las habilidades")
    hb.add_argument("-n", type=int, default=40)
    hb.add_argument("--nivel", type=int, default=15)
    hb.add_argument("--muestra", type=int, default=60)
    hb.add_argument("--escala", type=float, default=1.0)
    hb.add_argument(
        "--efecto",
        default=None,
        choices=[e.value for e in Efecto if e is not Efecto.NINGUNO],
    )

    # El %% es para argparse, que interpreta el % en los textos de ayuda.
    gu = sub.add_parser("guerras", help="guerras completas, con bots o sin ellos")
    gu.add_argument("-n", type=int, default=60)

    ec = sub.add_parser("economia", help="cuanto oro da una guerra y que compra")
    ec.add_argument("-n", type=int, default=120)
    ec.add_argument("--humanos", type=int, default=4, choices=(1, 2, 4, 7))

    # El %% es para argparse, que interpreta el % en los textos de ayuda.
    iv = sub.add_parser("invocacion", help="comprueba el 5%% del Ruler")
    iv.add_argument("-n", type=int, default=4000)

    a = p.parse_args()
    if a.modo == "duelo":
        duelo(a.a, a.b, a.nivel_a, a.nivel_b, a.n, a.semilla)
    elif a.modo == "niveles":
        niveles(a.n, a.semilla, a.nombre)
    elif a.modo == "triangulo":
        triangulo(a.n, a.semilla)
    elif a.modo == "npc":
        combates_npc(a.dia, a.n, a.semilla, a.muestra)
    elif a.modo == "grupal":
        grupal(a.jugadores, a.n, a.semilla)
    elif a.modo == "plantel":
        plantel(a.rivales, a.n, a.semilla, a.nivel)
    elif a.modo == "habilidades":
        habilidades(a.n, a.semilla, a.nivel, a.muestra, a.escala, a.efecto)
    elif a.modo == "guerras":
        guerras(a.n, a.semilla)
    elif a.modo == "economia":
        economia(a.n, a.semilla, a.humanos)
    else:
        invocaciones(a.n, a.semilla)


if __name__ == "__main__":
    main()
