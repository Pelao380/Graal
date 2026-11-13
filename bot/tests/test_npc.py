"""Pruebas del entrenamiento contra NPC.

Lo que se fija aqui no son tasas de victoria —eso lo mide el simulador y vive
en `docs/decisiones.md`— sino las reglas que, si se rompen, rompen el
entrenamiento sin que nada avise:

- **una Sombra nunca es un espejo mas fuerte que tu** (el tope del factor),
- la escalera va de menos a mas,
- endurecerse por dia no puede invertir el orden,
- y la Sombra comparte clase y habilidades, para que el entrenamiento mida al
  jugador y no su emparejamiento.
"""

from __future__ import annotations

import random
import unittest

from src.game import npc, objetos, personajes
from src.game.clases import Clase
from src.game.servant import Servant

CATALOGO = personajes.cargar()
POR_NOMBRE = {p.nombre: p for p in CATALOGO}
UNO = next(p for p in CATALOGO if p.habilidades and p.habilidades[0].nombre)

DIAS = (1, 2, 3, 5, 7, 10, 30, 200)


def _factor(indice: int, dia: int) -> float:
    """El factor que de verdad se aplica, leido de la Sombra construida."""
    base = UNO
    sombra = npc.construir_npc(Servant(base, 1), indice, dia).personaje
    return sombra.mult_ataque / base.mult_ataque


class PruebaElTopeDelFactor(unittest.TestCase):
    """El tope es lo que impide el acantilado, y no se ve en ningun sitio."""

    def test_ninguna_sombra_pasa_del_tope_ningun_dia(self) -> None:
        for indice in range(npc.COMBATES_POR_DIA):
            for dia in DIAS:
                self.assertLessEqual(
                    _factor(indice, dia),
                    npc.FACTOR_MAXIMO + 1e-9,
                    f"NPC {indice + 1} del dia {dia}",
                )

    def test_el_tope_deja_la_sombra_por_debajo_del_jugador(self) -> None:
        """Si llegara a 1.00 seria una moneda al aire, y mas, imposible.

        Medido: con factor 1.00 el jugador gana el 49%, y con 1.03 el 14%. El
        4.o NPC cruzaba el 1.00 el dia 5 y la escalera se rompia de un dia
        para otro.
        """
        self.assertLess(npc.FACTOR_MAXIMO, 1.0)

    def test_sin_el_tope_el_dia_5_se_pasaria(self) -> None:
        """Deja constancia de que el tope hace falta, no es decorativo."""
        crudo = npc.FACTOR_DIFICULTAD[-1] * (
            1 + npc.ENDURECIMIENTO_POR_DIA * (30 - 1)
        )
        self.assertGreater(crudo, 1.0, "sin tope la Sombra superaria al jugador")


class PruebaLaEscalera(unittest.TestCase):
    def test_cada_npc_es_mas_duro_que_el_anterior(self) -> None:
        factores = [_factor(i, 1) for i in range(npc.COMBATES_POR_DIA)]
        self.assertEqual(factores, sorted(factores))
        self.assertEqual(len(set(factores)), len(factores), "y distintos")

    def test_todos_quedan_en_la_banda_util(self) -> None:
        """Por debajo de 0.85 un NPC es un regalo: gana el 100%. Medido."""
        for indice in range(npc.COMBATES_POR_DIA):
            self.assertGreaterEqual(_factor(indice, 1), 0.85)

    def test_endurecerse_no_invierte_el_orden(self) -> None:
        for dia in DIAS:
            factores = [_factor(i, dia) for i in range(npc.COMBATES_POR_DIA)]
            self.assertEqual(factores, sorted(factores), f"dia {dia}")

    def test_el_mismo_npc_no_se_ablanda_con_los_dias(self) -> None:
        for indice in range(npc.COMBATES_POR_DIA):
            anterior = 0.0
            for dia in DIAS:
                ahora = _factor(indice, dia)
                self.assertGreaterEqual(ahora, anterior - 1e-9)
                anterior = ahora

    def test_el_cuarto_npc_se_puede_ganar(self) -> None:
        """Endurecer sin pasarse: el ultimo tiene que ser ganable.

        Con semilla fija, asi que no es inestable. El numero exacto vive en
        `docs/decisiones.md`; aqui solo se exige que no sea una pared.
        """
        rng = random.Random(11)
        servant = Servant(UNO, 10)
        ganados = sum(
            npc.pelear(servant, npc.COMBATES_POR_DIA - 1, 7, rng).gano
            for _ in range(60)
        )
        self.assertGreater(ganados, 30, "el 4.o NPC del dia 7 es una pared")


class PruebaLaSombra(unittest.TestCase):
    def test_comparte_clase_para_que_el_triangulo_quede_neutro(self) -> None:
        for base in (UNO, POR_NOMBRE["Emiya"]):
            sombra = npc.construir_npc(Servant(base, 3), 2, 1).personaje
            self.assertIs(sombra.clase, base.clase)

    def test_comparte_habilidades(self) -> None:
        """Si no, entrenar se abarataria solo al llegar al nivel 5."""
        sombra = npc.construir_npc(Servant(UNO, 15), 1, 1).personaje
        self.assertEqual(sombra.habilidades, UNO.habilidades)

    def test_va_al_mismo_nivel_que_el_jugador(self) -> None:
        for nivel in (1, 7, 15):
            self.assertEqual(
                npc.construir_npc(Servant(UNO, nivel), 0, 1).nivel, nivel
            )

    def test_escala_las_tres_estadisticas_por_igual(self) -> None:
        sombra = npc.construir_npc(Servant(UNO, 1), 3, 1).personaje
        f = npc.FACTOR_DIFICULTAD[3]
        for atributo in ("mult_vida", "mult_ataque", "mult_velocidad"):
            self.assertAlmostEqual(
                getattr(sombra, atributo),
                getattr(UNO, atributo) * f,
                places=6,
            )

    def test_la_sombra_no_entra_en_el_catalogo(self) -> None:
        """No cumple el presupuesto de 3.00 y no tiene por que: es una vara."""
        sombra = npc.construir_npc(Servant(UNO, 1), 0, 1).personaje
        suma = sombra.mult_vida + sombra.mult_ataque + sombra.mult_velocidad
        self.assertLess(suma, 3.0)


class PruebaPremiosYCastigos(unittest.TestCase):
    def test_la_xp_sale_del_numero_de_combate(self) -> None:
        rng = random.Random(3)
        servant = Servant(UNO, 10)
        for indice in range(npc.COMBATES_POR_DIA):
            r = npc.pelear(servant, indice, 1, rng)
            esperada = npc.XP_POR_VICTORIA[indice] if r.gano else 0
            self.assertEqual(r.xp, esperada)

    def test_perder_resta_vida_en_la_batalla_de_verdad(self) -> None:
        servant = Servant(UNO, 10)
        entera = npc.vida_inicial(servant, 0)
        self.assertEqual(entera, servant.vida_maxima)
        anterior = entera
        for derrotas in range(1, npc.COMBATES_POR_DIA + 1):
            ahora = npc.vida_inicial(servant, derrotas)
            self.assertLess(ahora, anterior)
            anterior = ahora
        self.assertGreaterEqual(anterior, 1, "nunca se entra con 0 de vida")

    def test_mas_derrotas_de_las_posibles_no_revienta(self) -> None:
        servant = Servant(UNO, 10)
        self.assertGreaterEqual(npc.vida_inicial(servant, 99), 1)


class PruebaLaSuelta(unittest.TestCase):
    """De donde salen los objetos. La probabilidad es de `PROB_OBJETO`."""

    def _peleas(self, indice: int, veces: int = 400, semilla: int = 7):
        rng = random.Random(semilla)
        servant = Servant(UNO, 10)
        return [npc.pelear(servant, indice, 1, rng) for _ in range(veces)]

    def test_solo_suelta_quien_gana(self) -> None:
        for indice in range(npc.COMBATES_POR_DIA):
            for r in self._peleas(indice, veces=120):
                if not r.gano:
                    self.assertIsNone(r.objeto, "perder no puede dar premio")

    def test_lo_que_suelta_esta_en_el_catalogo(self) -> None:
        sueltos = {o.clave for o in objetos.sueltos()}
        for indice in range(npc.COMBATES_POR_DIA):
            for r in self._peleas(indice, veces=120):
                if r.objeto is not None:
                    self.assertIn(r.objeto.clave, sueltos)

    def test_el_ultimo_npc_suelta_mas_que_el_primero(self) -> None:
        """La escalera tambien es de premio, no solo de dificultad."""
        self.assertLess(npc.PROB_OBJETO[0], npc.PROB_OBJETO[npc.COMBATES_POR_DIA - 1])

    def test_la_suelta_cae_cerca_de_su_probabilidad(self) -> None:
        """No es una medida de balance, es que el dado sea el que se cree."""
        for indice in range(npc.COMBATES_POR_DIA):
            peleas = self._peleas(indice, veces=400)
            ganadas = [r for r in peleas if r.gano]
            if len(ganadas) < 50:
                continue  # con pocas victorias la proporcion no dice nada
            con_objeto = sum(1 for r in ganadas if r.objeto is not None)
            proporcion = con_objeto / len(ganadas)
            esperada = npc.PROB_OBJETO[indice]
            self.assertAlmostEqual(
                proporcion,
                esperada,
                delta=0.10,
                msg=f"NPC {indice + 1}: {proporcion:.2f} contra {esperada:.2f}",
            )

    def test_el_objeto_cabe_en_el_inventario(self) -> None:
        """El camino entero: se pelea, se gana, se guarda."""
        inventario = objetos.Inventario()
        for indice in range(npc.COMBATES_POR_DIA):
            for r in self._peleas(indice, veces=60):
                if r.objeto is not None:
                    inventario.anadir(r.objeto.clave)
        self.assertFalse(inventario.vacio, "alguna suelta tenia que caer")
        self.assertLessEqual(inventario.total, objetos.TOPE_INVENTARIO)


if __name__ == "__main__":
    unittest.main()
