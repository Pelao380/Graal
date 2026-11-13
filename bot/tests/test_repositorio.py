"""Pruebas de guardar y cargar guerras: el viaje de ida y vuelta.

La base de datos va en memoria (`:memory:`), asi que no se toca `graal.db` ni
hace falta limpiar nada.
"""

from __future__ import annotations

import random
import unittest

from src import db, repositorio
from src.game import dia, invocacion, personajes, tienda
from src.game.war import Fase, Guerra

CATALOGO = personajes.cargar()


class Reloj:
    def __init__(self, ahora: float = 1_700_000_000.0) -> None:
        self.ahora = ahora

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


class PruebaIdaYVuelta(unittest.TestCase):
    def setUp(self) -> None:
        self.con = db.conectar(":memory:")
        repositorio.migrar(self.con)
        self.reloj = Reloj()

    def tearDown(self) -> None:
        self.con.close()

    def _guerra(self, humanos: int = 2, preparacion: str = "1h") -> Guerra:
        rng = random.Random(4)
        g = Guerra(
            id="100",
            canal_id="100",
            preparacion=preparacion,
            rng=rng,
            reloj=self.reloj,
        )
        for i in range(humanos):
            g.inscribir(f"h{i}", f"Humano {i}")
        g.rellenar_con_bots()
        g.empezar(invocacion.invocar(CATALOGO, rng))
        return g

    def _recargar(self) -> Guerra:
        guerras = repositorio.cargar_todas(self.con, CATALOGO)
        self.assertIn(100, guerras)
        g = guerras[100]
        g.reloj = self.reloj
        return g

    # --- lo basico ---

    def test_migrar_dos_veces_no_se_queja(self) -> None:
        repositorio.migrar(self.con)
        repositorio.migrar(self.con)

    def test_una_guerra_en_el_lobby_se_guarda_y_se_carga(self) -> None:
        g = Guerra(id="100", canal_id="100", idioma="es")
        g.inscribir("h0", "Humano 0")
        repositorio.guardar(self.con, g)

        vuelta = self._recargar()
        self.assertIs(vuelta.fase, Fase.LOBBY)
        self.assertEqual(vuelta.idioma, "es")
        self.assertEqual(vuelta.creador_id, "h0")
        self.assertEqual(list(vuelta.masters), ["h0"])
        self.assertIsNone(vuelta.masters["h0"].servant)

    def test_lo_que_no_se_reparte_se_guarda(self) -> None:
        g = self._guerra()
        repositorio.guardar(self.con, g)
        vuelta = self._recargar()
        # Los 6 bots invocaron al abrirse el dia, quedan 1 por repartir.
        self.assertEqual(len(vuelta.sin_repartir), len(g.sin_repartir))
        self.assertEqual(
            [s.personaje.nombre for s in vuelta.sin_repartir],
            [s.personaje.nombre for s in g.sin_repartir],
        )

    def test_los_servants_vuelven_con_su_nivel_y_su_xp(self) -> None:
        g = self._guerra()
        g.invocar_a_los_que_falten()
        m = g.masters["h0"]
        m.servant.nivel = 9
        m.servant.xp = 1234
        repositorio.guardar(self.con, g)

        vuelta = self._recargar()
        suyo = vuelta.masters["h0"].servant
        self.assertEqual(suyo.personaje.nombre, m.servant.nombre)
        self.assertEqual(suyo.clase, m.servant.clase)
        self.assertEqual(suyo.nivel, 9)
        self.assertEqual(suyo.xp, 1234)
        self.assertEqual(suyo.ataque, m.servant.ataque)

    def test_vuelve_todo_lo_del_master(self) -> None:
        g = self._guerra()
        g.invocar_a_los_que_falten()
        m = g.masters["h0"]
        m.derrotas = 1
        m.sellos = 2
        m.intentos_npc = 3
        m.derrotas_npc = 1
        m.listo = True
        g.declarar_ataque("h0", "h1")
        repositorio.guardar(self.con, g)

        suyo = self._recargar().masters["h0"]
        self.assertEqual(suyo.derrotas, 1)
        self.assertEqual(suyo.sellos, 2)
        self.assertEqual(suyo.intentos_npc, 3)
        self.assertEqual(suyo.derrotas_npc, 1)
        self.assertTrue(suyo.listo)
        self.assertEqual(suyo.objetivo, "h1")

    def test_lo_que_cada_uno_conoce_sobrevive(self) -> None:
        """Si se olvidara, al reiniciar volverias a no saber contra quien peleaste."""
        g = self._guerra()
        g.invocar_a_los_que_falten()
        g.masters["h0"].conocidos.update({"h1", "bot:2"})
        repositorio.guardar(self.con, g)

        suyo = self._recargar().masters["h0"]
        self.assertEqual(suyo.conocidos, {"h1", "bot:2"})
        self.assertTrue(suyo.conoce("h1"))
        self.assertTrue(suyo.conoce("h0"), "el suyo siempre")
        self.assertFalse(suyo.conoce("bot:3"))

    def test_lo_que_se_conoce_al_pelear_se_guarda(self) -> None:
        g = self._guerra()
        for m in g.humanos:
            m.listo = True
        c = dia.cerrar_dia(g)
        repositorio.guardar(self.con, g)
        vuelta = self._recargar()
        for b in c.batallas:
            for id_ in b.grupo:
                self.assertEqual(
                    vuelta.masters[id_].conocidos, g.masters[id_].conocidos
                )

    def test_los_bots_siguen_siendo_bots(self) -> None:
        g = self._guerra(humanos=1)
        repositorio.guardar(self.con, g)
        vuelta = self._recargar()
        self.assertEqual(len(vuelta.bots), 6)
        self.assertEqual(len(vuelta.humanos), 1)
        self.assertFalse(vuelta.otorga_grial)

    def test_el_orden_de_declaraciones_vuelve(self) -> None:
        g = self._guerra(humanos=2)
        g.invocar_a_los_que_falten()
        g.declarar_ataque("h0", "h1")
        repositorio.guardar(self.con, g)
        vuelta = self._recargar()
        self.assertEqual(vuelta.orden_declaraciones, g.orden_declaraciones)

    # --- el plazo, que es el motivo de todo esto ---

    def test_el_plazo_sobrevive(self) -> None:
        g = self._guerra(preparacion="30m")
        repositorio.guardar(self.con, g)
        vuelta = self._recargar()
        # Al segundo, que es lo que guarda la tabla.
        self.assertAlmostEqual(
            vuelta.vence_preparacion, g.vence_preparacion, delta=1
        )
        self.assertFalse(vuelta.plazo_cumplido)

    def test_un_plazo_que_vencio_con_el_bot_apagado_se_nota(self) -> None:
        g = self._guerra(preparacion="30m")
        repositorio.guardar(self.con, g)
        # El bot se apaga y pasa una hora.
        self.reloj.avanzar(60 * 60)
        vuelta = self._recargar()
        self.assertTrue(vuelta.plazo_cumplido)
        self.assertTrue(db.plazos_vencidos(self.con))

    def test_solo_queda_un_plazo_pendiente_por_guerra(self) -> None:
        g = self._guerra(preparacion="30m")
        repositorio.guardar(self.con, g)
        dia.cerrar_dia(g)
        repositorio.guardar(self.con, g)
        pendientes = self.con.execute(
            "SELECT COUNT(*) AS n FROM plazos WHERE atendido = 0"
        ).fetchone()["n"]
        self.assertEqual(pendientes, 1)

    def test_una_guerra_terminada_no_se_carga_ni_deja_plazo(self) -> None:
        g = self._guerra(humanos=1)
        for m in list(g.masters.values())[1:]:
            m.derrotas = 99
        g.fase = Fase.TERMINADA
        repositorio.guardar(self.con, g)
        self.assertEqual(repositorio.cargar_todas(self.con, CATALOGO), {})
        self.assertEqual(db.plazos_vencidos(self.con), [])

    # --- guardar dos veces ---

    def test_guardar_dos_veces_no_duplica_nada(self) -> None:
        g = self._guerra()
        repositorio.guardar(self.con, g)
        repositorio.guardar(self.con, g)
        for tabla, esperado in (("guerras", 1), ("masters", 7)):
            n = self.con.execute(
                f"SELECT COUNT(*) AS n FROM {tabla}"
            ).fetchone()["n"]
            self.assertEqual(n, esperado, tabla)

    def test_se_guarda_el_dia_nuevo_encima_del_viejo(self) -> None:
        g = self._guerra()
        repositorio.guardar(self.con, g)
        dia.cerrar_dia(g)
        repositorio.guardar(self.con, g)
        vuelta = self._recargar()
        self.assertEqual(vuelta.dia, g.dia)
        self.assertEqual(
            sum(m.derrotas for m in vuelta.masters.values()),
            sum(m.derrotas for m in g.masters.values()),
        )

    # --- la guerra sigue jugandose despues de volver ---

    def test_una_guerra_recargada_se_puede_terminar(self) -> None:
        g = self._guerra(humanos=1)
        repositorio.guardar(self.con, g)
        vuelta = self._recargar()
        for _ in range(40):
            if vuelta.terminada:
                break
            dia.cerrar_dia(vuelta)
            repositorio.guardar(self.con, vuelta)
        self.assertTrue(vuelta.terminada)
        self.assertIsNotNone(vuelta.ganador())
        # Y al terminar deja de cargarse.
        self.assertEqual(repositorio.cargar_todas(self.con, CATALOGO), {})

    # --- datos que ya no cuadran ---

    def test_un_servant_que_ya_no_esta_en_el_catalogo_no_tumba_el_arranque(
        self,
    ) -> None:
        g = self._guerra()
        g.invocar_a_los_que_falten()
        repositorio.guardar(self.con, g)
        self.con.execute(
            "UPDATE servants SET collection_no = -1, nombre = 'Quien Sabe'"
        )
        self.con.commit()
        with self.assertLogs("src.repositorio", level="WARNING"):
            self.assertEqual(repositorio.cargar_todas(self.con, CATALOGO), {})

    # --- el inventario ---

    def test_el_inventario_va_y_vuelve(self) -> None:
        """Los objetos duran la guerra, y una guerra dura dias y reinicios."""
        g = self._guerra()
        g.masters["h0"].inventario.anadir("elixir")
        g.masters["h0"].inventario.anadir("elixir")
        g.masters["h0"].inventario.anadir("tomo_saber")
        repositorio.guardar(self.con, g)

        vuelta = self._recargar()
        inv = vuelta.masters["h0"].inventario
        self.assertEqual(inv.cuantos_de("elixir"), 2)
        self.assertEqual(inv.cuantos_de("tomo_saber"), 1)
        self.assertEqual(inv.total, 3)

    def test_un_inventario_vacio_vuelve_vacio(self) -> None:
        g = self._guerra()
        repositorio.guardar(self.con, g)
        self.assertTrue(self._recargar().masters["h0"].inventario.vacio)

    def test_el_tope_por_batalla_no_se_guarda(self) -> None:
        """Es de la batalla en curso, que vive en memoria y dura minutos."""
        g = self._guerra()
        g.masters["h0"].inventario.usados_en_la_batalla = 1
        repositorio.guardar(self.con, g)
        self.assertTrue(
            self._recargar().masters["h0"].inventario.puede_usar_en_la_batalla
        )

    # --- las monedas ---

    def test_el_oro_va_y_vuelve(self) -> None:
        g = self._guerra()
        g.masters["h0"].oro = 175
        repositorio.guardar(self.con, g)
        self.assertEqual(self._recargar().masters["h0"].oro, 175)

    def test_una_guerra_sin_oro_vuelve_a_cero(self) -> None:
        g = self._guerra()
        repositorio.guardar(self.con, g)
        self.assertEqual(self._recargar().masters["h0"].oro, 0)

    def test_el_oro_no_esta_en_la_cuenta(self) -> None:
        """Las dos monedas no se guardan en el mismo sitio, y es a proposito.

        El oro va en la fila del Master, que se borra con la guerra. Los
        griales van en `cuentas`, que no cuelga de ninguna guerra. Si el oro
        estuviera en la cuenta, sobreviviria, y entonces una guerra nueva no
        empezaria empatada.
        """
        g = self._guerra()
        g.masters["h0"].oro = 500
        repositorio.guardar(self.con, g)
        self.assertEqual(repositorio.cargar_cuenta(self.con, "h0").griales, 0)

    def test_una_cuenta_que_no_existe_es_una_cuenta_a_cero(self) -> None:
        """Leer no crea la fila: la mayoria de la gente no va a tener griales."""
        cuenta = repositorio.cargar_cuenta(self.con, "nadie")
        self.assertEqual(cuenta.griales, 0)
        self.assertEqual(cuenta.usuario_id, "nadie")
        self.assertEqual(
            self.con.execute("SELECT COUNT(*) FROM cuentas").fetchone()[0], 0
        )

    def test_los_griales_van_y_vuelven(self) -> None:
        cuenta = repositorio.cargar_cuenta(self.con, "h0")
        cuenta.ganar_guerra()
        repositorio.guardar_cuenta(self.con, cuenta)
        vuelta = repositorio.cargar_cuenta(self.con, "h0")
        self.assertEqual(vuelta.griales, tienda.GRIALES_POR_GUERRA)
        self.assertEqual(vuelta.guerras_ganadas, 1)

    def test_guardar_la_cuenta_dos_veces_no_duplica_la_fila(self) -> None:
        cuenta = repositorio.cargar_cuenta(self.con, "h0")
        cuenta.ganar_guerra()
        repositorio.guardar_cuenta(self.con, cuenta)
        cuenta.ganar_guerra()
        repositorio.guardar_cuenta(self.con, cuenta)
        self.assertEqual(
            self.con.execute("SELECT COUNT(*) FROM cuentas").fetchone()[0], 1
        )
        self.assertEqual(
            repositorio.cargar_cuenta(self.con, "h0").guerras_ganadas, 2
        )

    def test_los_griales_sobreviven_a_la_guerra(self) -> None:
        """Es la razon de ser de la tabla: borrar la guerra no los toca."""
        g = self._guerra()
        repositorio.guardar(self.con, g)
        cuenta = repositorio.cargar_cuenta(self.con, "h0")
        cuenta.ganar_guerra()
        repositorio.guardar_cuenta(self.con, cuenta)

        self.con.execute("DELETE FROM guerras")
        self.con.commit()
        self.assertEqual(
            repositorio.cargar_cuenta(self.con, "h0").griales,
            tienda.GRIALES_POR_GUERRA,
        )

    def test_un_catalizador_de_servant_sobrevive_al_guardado(self) -> None:
        """Su clave no esta en el catalogo, se arma al leerla."""
        g = self._guerra()
        g.masters["h0"].inventario.anadir("catalizador_servant:91")
        repositorio.guardar(self.con, g)
        inv = self._recargar().masters["h0"].inventario
        self.assertTrue(inv.tiene("catalizador_servant:91"))
        fichas = [o.clave for o, _ in inv.lista()]
        self.assertIn("catalizador_servant:91", fichas)

    def test_un_inventario_ilegible_no_tumba_la_guerra(self) -> None:
        """Un objeto perdido no vale una guerra entera, al contrario que un
        Servant: sin Servant no hay con que pelear, sin objetos si."""
        g = self._guerra()
        g.masters["h0"].inventario.anadir("elixir")
        repositorio.guardar(self.con, g)
        self.con.execute("UPDATE masters SET inventario = 'no es json'")
        self.con.commit()
        with self.assertLogs("src.repositorio", level="WARNING"):
            vuelta = self._recargar()
        self.assertTrue(vuelta.masters["h0"].inventario.vacio)


if __name__ == "__main__":
    unittest.main()
