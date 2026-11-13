"""Pruebas del catalogo, el presupuesto, el triangulo y la invocacion."""

from __future__ import annotations

import random
import unittest

from src.game import personajes
from src.game.clases import (
    BONO_VENTAJA,
    CLASES_BASE,
    PENALIZACION_DESVENTAJA,
    PROB_RULER,
    Clase,
    multiplicador_triangulo,
)
from src.game.invocacion import CUPOS, invocar
from src.game.personajes import PRESUPUESTO, Personaje, desde_dict


class PruebaCatalogo(unittest.TestCase):
    def setUp(self) -> None:
        self.catalogo = personajes.cargar()

    def test_hay_al_menos_una_de_cada_clase_base(self) -> None:
        clases = {p.clase for p in self.catalogo}
        for c in CLASES_BASE:
            self.assertIn(c, clases, f"falta un personaje de clase {c.value}")

    def test_todos_respetan_el_presupuesto(self) -> None:
        for p in self.catalogo:
            self.assertAlmostEqual(p.presupuesto, PRESUPUESTO, places=3, msg=p.nombre)

    def test_todos_tienen_tres_huecos_de_habilidad(self) -> None:
        for p in self.catalogo:
            self.assertEqual(len(p.habilidades), 3, p.nombre)

    def test_casi_todos_traen_nombres_desde_los_datos(self) -> None:
        """El import grande rellena Noble Fantasma y habilidades."""
        con_np = [p for p in self.catalogo if p.noble_fantasma]
        con_hab = [p for p in self.catalogo if all(h.nombre for h in p.habilidades)]
        total = len(self.catalogo)
        # Si alguien reimporta con el export ligero, estos quedan vacios y la
        # prueba avisa en vez de dejarlo pasar en silencio.
        self.assertGreater(len(con_np) / total, 0.95, "faltan Nobles Fantasmas")
        self.assertGreater(len(con_hab) / total, 0.95, "faltan habilidades")

    def test_el_retoque_a_mano_gana_sobre_los_datos(self) -> None:
        """Las habilidades escritas a mano no se pierden al reimportar."""
        artoria = next(p for p in self.catalogo if p.collection_no == 2)
        # En los datos se llama "Charisma B".
        self.assertEqual(artoria.habilidades[0].nombre, "Carisma")

    def test_el_retoque_del_nombre_conserva_el_efecto(self) -> None:
        """Renombrar una habilidad a mano no le quita lo que hace."""
        artoria = next(p for p in self.catalogo if p.collection_no == 2)
        self.assertTrue(
            artoria.habilidades[0].hace_algo,
            "el retoque a mano borro el efecto que trajo el importador",
        )

    def test_el_noble_fantasma_trae_rango_y_tipo(self) -> None:
        artoria = next(p for p in self.catalogo if p.collection_no == 2)
        self.assertEqual(artoria.noble_fantasma.nombre, "Excalibur")
        self.assertEqual(artoria.noble_fantasma.rango, "A")
        self.assertEqual(artoria.noble_fantasma.tipo, "Anti-Fortress")

    def test_el_retoque_del_nombre_conserva_rango_y_tipo(self) -> None:
        """El nombre a mano no borra lo que trajo el importador."""
        con_rango = [p for p in self.catalogo if p.noble_fantasma.rango]
        self.assertGreater(len(con_rango) / len(self.catalogo), 0.95)

    def test_los_nombres_no_se_repiten(self) -> None:
        nombres = [p.nombre for p in self.catalogo]
        self.assertEqual(len(nombres), len(set(nombres)))

    def test_los_retocados_a_mano_estan_completos(self) -> None:
        """Un retoque a mano no deja nada a medias.

        Lo que se exige depende de lo que el retoque toque: el Noble Fantasma
        y los nombres de las habilidades valen para todos, porque se heredan
        del importador, pero el rasgo solo se le pide a quien trae un rasgo.
        Desde que los 39 huecos se llenaron a mano (2026-11-09) hay fichas que
        solo cambian el efecto de una habilidad y no tienen rasgo propio.
        """
        import json

        from src.game.personajes import RUTA_CATALOGO

        retoques = json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))["personajes"]
        self.assertTrue(retoques, "no hay retoques a mano")
        por_id = {p.collection_no: p for p in self.catalogo}
        for r in retoques:
            p = por_id[r["collectionNo"]]
            self.assertTrue(p.noble_fantasma, p.nombre)
            self.assertTrue(all(h.nombre for h in p.habilidades), p.nombre)
            if "rasgo" in r:
                self.assertTrue(p.rasgo.descripcion, p.nombre)

    def test_el_retoque_hereda_las_estadisticas_del_plantel(self) -> None:
        """Un retoque trae solo lo que cambia: el resto lo hereda."""
        heracles = next(p for p in self.catalogo if p.collection_no == 47)
        self.assertTrue(heracles.rasgo.objetivo_al_azar)
        self.assertEqual(heracles.clase, Clase.BERSERKER)
        # Las estadisticas salen del importador, no del retoque.
        self.assertAlmostEqual(heracles.presupuesto, PRESUPUESTO, places=3)
        self.assertEqual(heracles.mult_velocidad, 0.85)


class PruebaNobleFantasmaTapado(unittest.TestCase):
    """Los que traen el nombre con interrogantes en los datos de Atlas.

    Son siete, y en FGO es un secreto de la historia, no un dato que falte.
    La ficha no ensena "??? (rango ？)": ensena el Noble Fantasma sin nombre.
    """

    def setUp(self) -> None:
        self.catalogo = personajes.cargar()

    def test_ninguna_ficha_ensena_interrogantes(self) -> None:
        for p in self.catalogo:
            np = p.noble_fantasma
            with self.subTest(personaje=p.nombre):
                self.assertNotIn("?", np.nombre)
                self.assertNotIn("？", np.nombre)
                self.assertNotIn("?", np.rango)
                self.assertNotIn("？", np.rango)

    def test_el_tapado_sigue_teniendo_noble_fantasma(self) -> None:
        """Lo tiene y lo lanza: lo que no se sabe es como se llama."""
        tapados = [p for p in self.catalogo if p.noble_fantasma.oculto]
        self.assertTrue(tapados, "ninguno quedo marcado como oculto")
        for p in tapados:
            with self.subTest(personaje=p.nombre):
                self.assertTrue(p.noble_fantasma, "cuenta como que lo tiene")
                self.assertFalse(p.noble_fantasma.nombre)

    def test_el_que_de_verdad_no_tiene_sigue_sin_tener(self) -> None:
        from src.game.personajes import SIN_NOBLE_FANTASMA

        self.assertFalse(SIN_NOBLE_FANTASMA)

    def test_un_nombre_normal_no_se_toca(self) -> None:
        np = personajes.noble_fantasma_desde(
            {"nombre": "Excalibur", "rango": "A++", "tipo": "???"}
        )
        self.assertEqual(np.nombre, "Excalibur")
        self.assertEqual(np.rango, "A++")
        self.assertFalse(np.oculto)


class PruebaPresupuesto(unittest.TestCase):
    def test_un_personaje_que_se_pasa_no_se_carga(self) -> None:
        with self.assertRaises(ValueError):
            desde_dict(
                {
                    "nombre": "Roto",
                    "clase": "Saber",
                    "vida": 1.30,
                    "ataque": 1.30,
                    "velocidad": 1.30,
                    "habilidades": ["a", "b", "c"],
                }
            )

    def test_un_multiplicador_fuera_de_rango_no_se_carga(self) -> None:
        with self.assertRaises(ValueError):
            desde_dict(
                {
                    "nombre": "Extremo",
                    "clase": "Saber",
                    "vida": 1.50,
                    "ataque": 1.00,
                    "velocidad": 0.50,
                    "habilidades": ["a", "b", "c"],
                }
            )

    def test_el_presupuesto_justo_si_se_carga(self) -> None:
        p = desde_dict(
            {
                "nombre": "Correcto",
                "clase": "Saber",
                "vida": 1.10,
                "ataque": 1.00,
                "velocidad": 0.90,
                "habilidades": ["a", "b", "c"],
            }
        )
        self.assertAlmostEqual(p.presupuesto, PRESUPUESTO, places=3)


class PruebaEsquivaPorVelocidad(unittest.TestCase):
    def test_el_mas_lento_no_esquiva(self) -> None:
        from src.game.battle import prob_esquiva_por_velocidad

        self.assertEqual(prob_esquiva_por_velocidad(50, 60), 0.0)
        self.assertEqual(prob_esquiva_por_velocidad(50, 50), 0.0)

    def test_la_esquiva_crece_con_la_ventaja(self) -> None:
        from src.game.battle import prob_esquiva_por_velocidad

        from src.game.battle import FACTOR_ESQUIVA_VELOCIDAD

        poca = prob_esquiva_por_velocidad(55, 50)
        mucha = prob_esquiva_por_velocidad(70, 50)
        self.assertGreater(mucha, poca)
        # 10% mas rapido da el factor por ese 10%, sea cual sea el factor.
        self.assertAlmostEqual(poca, 0.10 * FACTOR_ESQUIVA_VELOCIDAD, places=3)

    def test_la_esquiva_tiene_tope(self) -> None:
        from src.game.battle import TOPE_ESQUIVA_VELOCIDAD, prob_esquiva_por_velocidad

        self.assertEqual(prob_esquiva_por_velocidad(500, 50), TOPE_ESQUIVA_VELOCIDAD)


class PruebaDemencia(unittest.TestCase):
    def test_heracles_no_elige_objetivo(self) -> None:
        catalogo = personajes.cargar()
        her = next(p for p in catalogo if p.nombre == "Heracles")
        self.assertTrue(her.rasgo.objetivo_al_azar)

    def test_el_objetivo_elegido_se_ignora(self) -> None:
        import random

        from src.game.battle import Accion, Batalla, Combatiente, Decision
        from src.game.servant import Servant

        catalogo = personajes.cargar()
        her = next(p for p in catalogo if p.nombre == "Heracles")
        otro = next(p for p in catalogo if p.clase is Clase.RIDER)

        # Heracles apunta siempre a "b", pero deberia repartir entre b y c.
        golpeados = set()
        for semilla in range(60):
            cs = [
                Combatiente(id="a", nombre="H", servant=Servant(her, 1)),
                Combatiente(id="b", nombre="B", servant=Servant(otro, 1)),
                Combatiente(id="c", nombre="C", servant=Servant(otro, 1)),
            ]
            b = Batalla(cs, rng=random.Random(semilla))
            b.resolver_turno({"a": Decision(Accion.ATACAR, "b")})
            for c in cs[1:]:
                if c.vida < c.servant.vida_maxima:
                    golpeados.add(c.id)
        self.assertEqual(golpeados, {"b", "c"})


class PruebaTriangulo(unittest.TestCase):
    def test_el_triangulo_clasico(self) -> None:
        self.assertEqual(
            multiplicador_triangulo(Clase.SABER, Clase.LANCER), BONO_VENTAJA
        )
        self.assertEqual(
            multiplicador_triangulo(Clase.LANCER, Clase.ARCHER), BONO_VENTAJA
        )
        self.assertEqual(
            multiplicador_triangulo(Clase.ARCHER, Clase.SABER), BONO_VENTAJA
        )

    def test_la_desventaja_es_el_reverso(self) -> None:
        self.assertEqual(
            multiplicador_triangulo(Clase.LANCER, Clase.SABER),
            PENALIZACION_DESVENTAJA,
        )

    def test_las_demas_clases_son_neutrales(self) -> None:
        for c in (Clase.RIDER, Clase.CASTER, Clase.ASSASSIN, Clase.BERSERKER):
            self.assertEqual(multiplicador_triangulo(c, Clase.SABER), 1.0)
            self.assertEqual(multiplicador_triangulo(Clase.SABER, c), 1.0)

    def test_misma_clase_es_neutral(self) -> None:
        self.assertEqual(multiplicador_triangulo(Clase.SABER, Clase.SABER), 1.0)


class PruebaInvocacion(unittest.TestCase):
    def setUp(self) -> None:
        self.catalogo = personajes.cargar()

    def test_siempre_siete_servants(self) -> None:
        rng = random.Random(1)
        for _ in range(50):
            self.assertEqual(len(invocar(self.catalogo, rng)), CUPOS)

    def test_sin_clases_repetidas(self) -> None:
        rng = random.Random(2)
        for _ in range(50):
            clases = [s.clase for s in invocar(self.catalogo, rng)]
            self.assertEqual(len(clases), len(set(clases)))

    def test_el_ruler_aparece_cerca_del_cinco_por_ciento(self) -> None:
        rng = random.Random(3)
        intentos = 4000
        con_ruler = sum(
            1
            for _ in range(intentos)
            if any(s.clase is Clase.RULER for s in invocar(self.catalogo, rng))
        )
        self.assertAlmostEqual(con_ruler / intentos, PROB_RULER, delta=0.015)

    def test_cuando_sale_ruler_falta_una_clase_base(self) -> None:
        rng = random.Random(4)
        for _ in range(2000):
            invocados = invocar(self.catalogo, rng)
            clases = {s.clase for s in invocados}
            if Clase.RULER in clases:
                faltan = [c for c in CLASES_BASE if c not in clases]
                self.assertEqual(len(faltan), 1)
                return
        self.skipTest("no salio ningun Ruler en 2000 guerras")

    def test_los_sellos_salen_del_rasgo(self) -> None:
        jeanne = next(p for p in self.catalogo if p.clase is Clase.RULER)
        self.assertEqual(jeanne.rasgo.sellos, 5)
        otro = next(p for p in self.catalogo if p.clase is Clase.SABER)
        self.assertEqual(otro.rasgo.sellos, 3)


if __name__ == "__main__":
    unittest.main()

