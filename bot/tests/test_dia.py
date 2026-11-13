"""Pruebas del cierre del dia: invocar, pelear, eliminar y pasar pagina."""

from __future__ import annotations

import random
import unittest

from src.game import dia, invocacion, personajes
from src.game.war import DERROTAS_PARA_ELIMINAR, Fase, Guerra

CATALOGO = personajes.cargar()


def _guerra(humanos: int = 2, semilla: int = 3) -> Guerra:
    """Una guerra empezada de verdad, con bots en los cupos que falten."""
    rng = random.Random(semilla)
    g = Guerra(id="1", canal_id="1", rng=rng)
    for i in range(humanos):
        g.inscribir(f"h{i}", f"Humano {i}")
    g.rellenar_con_bots()
    g.empezar(invocacion.invocar(CATALOGO, rng))
    return g


def _listos(g: Guerra) -> Guerra:
    """Todas las personas dicen que acabaron su dia."""
    for m in g.humanos:
        m.listo = True
    return g


class PruebaPuedeCerrar(unittest.TestCase):
    def test_solo_el_creador(self) -> None:
        g = _listos(_guerra())
        self.assertTrue(dia.puede_cerrar(g, g.creador_id))
        self.assertFalse(dia.puede_cerrar(g, "h1"))

    def test_solo_en_preparacion(self) -> None:
        g = _listos(_guerra())
        g.fase = Fase.BATALLA
        self.assertFalse(dia.puede_cerrar(g, g.creador_id))

    def test_no_se_cierra_si_falta_alguien_por_estar_listo(self) -> None:
        g = _guerra(humanos=2)
        g.masters["h0"].listo = True
        self.assertFalse(dia.puede_cerrar(g, "h0"))
        self.assertEqual([m.id for m in g.faltan_por_estar_listos], ["h1"])
        g.masters["h1"].listo = True
        self.assertTrue(dia.puede_cerrar(g, "h0"))

    def test_los_bots_nunca_hacen_esperar(self) -> None:
        """Hacen lo suyo al abrirse el dia, asi que ya estan listos."""
        g = _guerra(humanos=1)
        self.assertTrue(all(m.listo for m in g.bots))
        g.masters["h0"].listo = True
        self.assertTrue(dia.puede_cerrar(g, "h0"))

    def test_un_eliminado_no_hace_esperar(self) -> None:
        g = _guerra(humanos=2)
        g.masters["h0"].listo = True
        g.masters["h1"].derrotas = DERROTAS_PARA_ELIMINAR
        self.assertTrue(dia.puede_cerrar(g, "h0"))

    def test_el_dia_nuevo_borra_los_listos(self) -> None:
        g = _listos(_guerra())
        dia.cerrar_dia(g)
        for m in g.humanos:
            if not m.eliminado:
                self.assertFalse(m.listo, "hay que volver a decirlo cada dia")
        for m in g.bots:
            if not m.eliminado:
                self.assertTrue(m.listo, "los bots ya hicieron lo suyo")

    def test_no_en_el_lobby(self) -> None:
        g = Guerra(id="1", canal_id="1")
        g.inscribir("h0", "Humano 0")
        self.assertFalse(dia.puede_cerrar(g, "h0"))


class PruebaCerrarDia(unittest.TestCase):
    def test_cerrar_invoca_pelea_y_pasa_de_dia(self) -> None:
        g = _guerra()
        self.assertIsNone(g.masters["h0"].servant, "el humano no invoco")
        c = dia.cerrar_dia(g)

        self.assertEqual(c.dia, 1)
        self.assertIn("h0", c.invocados)
        self.assertTrue(all(m.servant for m in g.masters.values()))
        self.assertEqual(g.dia, 2)
        self.assertIs(g.fase, Fase.PREPARACION)

    def test_las_batallas_se_pelean_y_alguien_cae(self) -> None:
        g = _guerra()
        c = dia.cerrar_dia(g)
        # Los bots siempre atacan, asi que el dia 1 siempre hay batallas.
        self.assertTrue(c.batallas)
        for b in c.batallas:
            self.assertGreaterEqual(len(b.grupo), 2)
            self.assertLessEqual(len(b.grupo), 4)
            self.assertTrue(b.registro, "una batalla deja registro")
            self.assertGreater(b.turnos, 0)
        caidos = [id_ for b in c.batallas for id_ in b.caidos]
        self.assertTrue(caidos, "alguna batalla la gana alguien")
        for id_ in caidos:
            self.assertGreaterEqual(g.masters[id_].derrotas, 1)
        # Una derrota por cada caida, ni una menos: si una batalla siguio
        # despues de la votacion y cayo otro, ese tambien la cobra.
        for id_ in set(caidos):
            self.assertEqual(g.masters[id_].derrotas, caidos.count(id_))

    def test_nadie_pelea_dos_batallas_el_mismo_dia(self) -> None:
        g = _guerra()
        c = dia.cerrar_dia(g)
        peleando = [id_ for b in c.batallas for id_ in b.grupo]
        self.assertEqual(len(peleando), len(set(peleando)))

    def test_quien_no_pelea_descansa(self) -> None:
        g = _guerra()
        c = dia.cerrar_dia(g)
        peleando = {id_ for b in c.batallas for id_ in b.grupo}
        for id_ in c.descansan:
            self.assertNotIn(id_, peleando)

    def test_la_segunda_derrota_elimina(self) -> None:
        g = _guerra()
        g.invocar_a_los_que_falten()
        # Todos contra h0, que ya llega con una derrota encima.
        g.masters["h0"].derrotas = DERROTAS_PARA_ELIMINAR - 1
        for m in g.activos:
            m.objetivo = None
        g.orden_declaraciones.clear()
        g.declarar_ataque("h1", "h0")
        c = dia.cerrar_dia(g)
        if any("h0" in b.caidos for b in c.batallas):
            self.assertTrue(g.masters["h0"].eliminado)
            self.assertTrue(any("h0" in b.eliminados for b in c.batallas))

    def test_pelear_contra_alguien_es_verle_el_servant(self) -> None:
        g = _listos(_guerra())
        c = dia.cerrar_dia(g)
        for b in c.batallas:
            for id_ in b.grupo:
                otros = {o for o in b.grupo if o != id_}
                self.assertTrue(
                    otros <= g.masters[id_].conocidos,
                    f"{id_} deberia conocer a {otros}",
                )
                # Y a nadie mas.
                self.assertEqual(g.masters[id_].conocidos, otros)

    def test_quien_descansa_no_se_entera_de_nada(self) -> None:
        g = _listos(_guerra())
        c = dia.cerrar_dia(g)
        for id_ in c.descansan:
            self.assertEqual(g.masters[id_].conocidos, set())

    def test_lo_conocido_se_acumula_dia_a_dia(self) -> None:
        g = _listos(_guerra(humanos=1))
        primero = None
        for _ in range(3):
            if g.terminada:
                break
            for m in g.humanos:
                m.listo = True
            c = dia.cerrar_dia(g)
            ahora = {
                id_: set(m.conocidos) for id_, m in g.masters.items()
            }
            if primero is not None:
                for id_, conocidos in ahora.items():
                    self.assertTrue(
                        primero[id_] <= conocidos, "no se olvida a nadie"
                    )
            primero = ahora

    def test_no_se_cierra_fuera_de_preparacion(self) -> None:
        g = _guerra()
        g.fase = Fase.BATALLA
        with self.assertRaises(RuntimeError):
            dia.cerrar_dia(g)

    def test_cerrar_dias_hasta_el_final_deja_un_ganador(self) -> None:
        """El ciclo entero, que es la prueba de punta a punta del cierre."""
        g = _guerra(humanos=1)
        for _ in range(40):
            if g.terminada:
                break
            c = dia.cerrar_dia(g)
        self.assertTrue(g.terminada)
        self.assertIsNotNone(g.ganador())
        self.assertTrue(c.terminada)
        self.assertEqual(c.ganador, g.ganador().id)
        # Con una sola persona no hay Grial, gane quien gane.
        self.assertIsNone(c.grial)
        self.assertIsNone(g.gana_el_grial())

    def test_con_cuatro_personas_el_ganador_puede_llevarse_el_grial(self) -> None:
        g = _guerra(humanos=4)
        for _ in range(40):
            if g.terminada:
                break
            c = dia.cerrar_dia(g)
        ganador = g.ganador()
        self.assertIsNotNone(ganador)
        if not ganador.es_bot:
            self.assertEqual(c.grial, ganador.id)
        else:
            self.assertIsNone(c.grial)

    def test_el_dia_nuevo_trae_a_los_bots_entrenados(self) -> None:
        """Cerrar el dia llama a `siguiente_dia`, que abre el siguiente."""
        g = _guerra()
        dia.cerrar_dia(g)
        for m in g.bots:
            if m.eliminado:
                continue
            self.assertEqual(m.intentos_npc, 4)
            self.assertIsNotNone(m.objetivo)


if __name__ == "__main__":
    unittest.main()
