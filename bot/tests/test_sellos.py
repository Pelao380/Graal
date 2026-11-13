"""Pruebas de los Sellos de Comando.

Lo que se fija aqui es lo que, si se rompe, no avisa: que un Sello no gaste el
turno, que los dos topes se descuenten juntos (tres por guerra, uno por
batalla), que el de la batalla vuelva con el dia y el de la guerra no, y que
los tres usos sigan siendo tres.
"""

from __future__ import annotations

import random
import unittest

from src.game import dia, invocacion, personajes, sellos
from src.game.battle import Accion, Cuenta, Decision
from src.game.combate import Combate
from src.game.personajes import Efecto
from src.game.war import SELLOS_POR_BATALLA, SELLOS_POR_MASTER, Guerra

CATALOGO = personajes.cargar()


def _guerra(semilla: int = 7) -> Guerra:
    rng = random.Random(semilla)
    g = Guerra(id="1", canal_id="100", rng=rng)
    for i in range(2):
        g.inscribir(f"h{i}", f"Humano {i}")
    g.rellenar_con_bots()
    g.empezar(invocacion.invocar(CATALOGO, rng))
    for m in g.sin_invocar:
        g.invocar_para(m.id, rng)
    return g


def _combate(guerra: Guerra) -> Combate:
    return Combate(
        dia.armar_batalla(guerra, ["h0", "h1"], guerra.rng),
        humanos={"h0", "h1"},
        rng=guerra.rng,
    )


class PruebaLosTres(unittest.TestCase):
    def test_son_tres_usos_y_no_mas(self) -> None:
        """La lista es cerrada a proposito: un Sello no inventa reglas."""
        self.assertEqual(len(sellos.lista()), 3)
        self.assertEqual(len(sellos.Uso), 3)

    def test_cada_uso_tiene_sus_frases(self) -> None:
        for s in sellos.lista():
            for idioma in ("es", "en"):
                self.assertTrue(s.nombre_para(idioma))
                self.assertTrue(s.descripcion(idioma))

    def test_una_clave_que_no_existe_no_es_un_sello(self) -> None:
        self.assertIsNone(sellos.sello("ataque"))
        self.assertIsNone(sellos.sello(""))
        self.assertIs(sellos.sello("curar").uso, sellos.Uso.CURAR)

    def test_solo_curar_pasa_por_un_efecto_del_combate(self) -> None:
        """Los otros dos no son ninguno de los diez, y por eso no lo finjen."""
        con_efecto = [s for s in sellos.lista() if s.efecto is not Efecto.NINGUNO]
        self.assertEqual([s.uso for s in con_efecto], [sellos.Uso.CURAR])
        self.assertIs(con_efecto[0].efecto, Efecto.CURAR)


class PruebaEnLaBatalla(unittest.TestCase):
    def setUp(self) -> None:
        self.g = _guerra()
        self.c = _combate(self.g)
        self.yo = self.c.batalla.combatientes["h0"]

    def test_llenar_el_mana_deja_lanzar_el_noble_fantasma(self) -> None:
        self.yo.mana = 0
        self.assertFalse(self.yo.puede_noble_fantasma)
        self.c.usar_sello("h0", sellos.sello("mana"))
        self.assertTrue(self.yo.puede_noble_fantasma)
        self.assertEqual(self.yo.mana, self.yo.costo_np)

    def test_llenar_el_mana_no_regala_el_siguiente(self) -> None:
        """Se llena **hasta** el costo, no se suma."""
        self.yo.mana = self.yo.costo_np * 2
        antes = self.yo.mana
        self.c.usar_sello("h0", sellos.sello("mana"))
        self.assertEqual(self.yo.mana, antes)

    def test_curar_devuelve_vida_y_no_pasa_de_la_maxima(self) -> None:
        maxima = self.yo.servant.vida_maxima
        self.yo.vida = 1
        self.c.usar_sello("h0", sellos.sello("curar"))
        self.assertGreater(self.yo.vida, 1)
        self.assertLessEqual(self.yo.vida, maxima)
        self.yo.vida = maxima
        self.c.usar_sello("h0", sellos.sello("curar"))
        self.assertEqual(self.yo.vida, maxima)

    def test_los_enfriamientos_se_apagan(self) -> None:
        numero = self.yo.servant.habilidades_desbloqueadas or 1
        self.yo.enfriamientos[numero] = Cuenta(turnos=3, turno_creado=0)
        self.assertTrue(self.yo.enfriamiento_restante(numero))
        self.c.usar_sello("h0", sellos.sello("enfriamientos"))
        self.assertFalse(self.yo.enfriamiento_restante(numero))

    def test_gastar_un_sello_no_es_la_decision_del_turno(self) -> None:
        """Es la regla que lo hace distinto de una habilidad."""
        self.c.usar_sello("h0", sellos.sello("mana"))
        self.assertEqual(self.c.batalla.turno, 0, "no se resolvio nada")
        self.assertIn("h0", self.c.pendientes, "le sigue tocando elegir")

    def test_queda_en_el_registro_de_la_batalla(self) -> None:
        self.c.usar_sello("h0", sellos.sello("mana"))
        self.assertTrue(any("h0" in x or "Humano 0" in x for x in self.c.batalla.registro))

    def test_un_combate_acabado_no_acepta_sellos(self) -> None:
        rival = self.c.batalla.combatientes["h1"]
        rival.vida = 1
        while not self.c.terminado:
            for quien in list(self.c.pendientes):
                otro = self.c.batalla.rivales_de(quien)[0]
                self.c.decidir(
                    quien, Decision(accion=Accion.ATACAR, objetivo=otro.id)
                )
        with self.assertRaises(RuntimeError):
            self.c.usar_sello("h0", sellos.sello("mana"))

    def test_quien_cayo_no_gasta_sellos(self) -> None:
        self.yo.vida = 0
        with self.assertRaises(RuntimeError):
            self.c.usar_sello("h0", sellos.sello("mana"))


class PruebaLosTopes(unittest.TestCase):
    def setUp(self) -> None:
        self.g = _guerra()
        self.m = self.g.masters["h0"]

    def test_empieza_con_los_de_su_ficha(self) -> None:
        self.assertEqual(self.m.sellos, self.m.servant.rasgo.sellos)
        self.assertTrue(self.m.puede_usar_sello)

    def test_gastar_baja_los_dos_contadores_de_una_vez(self) -> None:
        """Por separado, uno de los dos topes deja de existir."""
        antes = self.m.sellos
        self.m.gastar_sello()
        self.assertEqual(self.m.sellos, antes - 1)
        self.assertEqual(self.m.sellos_en_la_batalla, SELLOS_POR_BATALLA)
        self.assertFalse(self.m.puede_usar_sello, "uno por batalla")

    def test_el_dia_nuevo_devuelve_el_de_la_batalla_y_no_los_de_la_guerra(self) -> None:
        self.m.gastar_sello()
        quedan = self.m.sellos
        self.m.nuevo_dia()
        self.assertEqual(self.m.sellos, quedan, "los gastados no vuelven")
        self.assertEqual(self.m.sellos_en_la_batalla, 0)
        self.assertTrue(self.m.puede_usar_sello)

    def test_se_acaban(self) -> None:
        for _ in range(SELLOS_POR_MASTER):
            self.m.nuevo_dia()
            self.m.gastar_sello()
        self.m.nuevo_dia()
        self.assertEqual(self.m.sellos, 0)
        self.assertFalse(self.m.puede_usar_sello)
        with self.assertRaises(RuntimeError):
            self.m.gastar_sello()


if __name__ == "__main__":
    unittest.main()
