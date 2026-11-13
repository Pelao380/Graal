"""Pruebas del ciclo de la guerra y de la formacion de batallas."""

from __future__ import annotations

import random
import unittest

from src.game.clases import CLASES_BASE
from src.game.npc import PENALIZACION_VIDA, vida_inicial
from src.game.personajes import Personaje
from src.game.servant import Servant
from src.game.war import (
    MAXIMO_MASTERS,
    MINIMO_HUMANOS_PARA_GRIAL,
    MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA,
    MINIMO_MASTERS,
    Fase,
    Guerra,
)


def _guerra(n: int = MINIMO_MASTERS) -> Guerra:
    g = Guerra(id="1", canal_id="1")
    for i in range(n):
        g.inscribir(f"m{i}", f"Master {i}")
    return g


def _empezar(g: Guerra) -> Guerra:
    """Empieza la guerra y reparte ya todos los Servants.

    Desde que la invocacion la pide cada Master, empezar no reparte nada. La
    mayoria de las pruebas no van de eso y necesitan a los siete con Servant,
    que es como queda la guerra al cerrarse el dia 1; las que si van de la
    invocacion estan en `PruebaInvocacion`.
    """
    g.empezar(_servants())
    g.invocar_a_los_que_falten()
    return g


def _servants() -> list[Servant]:
    """Un Servant por clase base, como los reparte la invocacion."""
    return [
        Servant(personaje=Personaje(nombre=f"S-{c.value}", clase=c))
        for c in CLASES_BASE
    ]




class PruebaLobby(unittest.TestCase):
    def test_no_empieza_con_menos_de_siete(self) -> None:
        g = _guerra(6)
        self.assertFalse(g.puede_empezar)
        with self.assertRaises(RuntimeError):
            _empezar(g)

    def test_empieza_con_siete(self) -> None:
        g = _guerra()
        g.empezar(_servants())
        self.assertEqual(g.dia, 1)
        self.assertIs(g.fase, Fase.PREPARACION)
        # El sorteo esta hecho, pero sin repartir: lo pide cada Master.
        self.assertEqual(len(g.sin_repartir), 7)
        self.assertTrue(all(m.servant is None for m in g.masters.values()))
        self.assertEqual(len(g.sin_invocar), 7)

    def test_un_lobby_con_una_persona_no_es_una_guerra_terminada(self) -> None:
        """Lo encontro la persistencia: solo hay uno en pie, pero no ha empezado."""
        g = _guerra(1)
        self.assertFalse(g.terminada)
        self.assertIsNone(g.ganador())

    def test_no_se_puede_inscribir_dos_veces(self) -> None:
        g = _guerra()
        with self.assertRaises(ValueError):
            g.inscribir("m0", "Master 0")


class PruebaInvocacion(unittest.TestCase):
    """La invocacion la pide cada Master, y hay plazo."""

    def setUp(self) -> None:
        self.g = _guerra()
        self.g.rng = random.Random(11)
        self.g.empezar(_servants())

    def test_no_se_puede_invocar_antes_de_empezar(self) -> None:
        g = _guerra()
        with self.assertRaises(RuntimeError):
            g.invocar_para("m0")

    def test_invocar_da_un_servant_y_sus_sellos(self) -> None:
        s = self.g.invocar_para("m0")
        m = self.g.masters["m0"]
        self.assertIs(m.servant, s)
        self.assertEqual(m.sellos, s.rasgo.sellos)
        self.assertEqual(len(self.g.sin_repartir), 6)
        self.assertNotIn(m, self.g.sin_invocar)

    def test_no_se_invoca_dos_veces(self) -> None:
        self.g.invocar_para("m0")
        with self.assertRaises(RuntimeError):
            self.g.invocar_para("m0")

    def test_cada_uno_recibe_un_servant_distinto(self) -> None:
        self.g.invocar_a_los_que_falten()
        servants = [m.servant for m in self.g.masters.values()]
        self.assertEqual(len(servants), 7)
        self.assertEqual(len({id(s) for s in servants}), 7)
        self.assertEqual(len({s.clase for s in servants}), 7)
        self.assertEqual(self.g.sin_repartir, [])

    def test_sin_servant_no_se_puede_atacar(self) -> None:
        self.g.invocar_para("m1")
        with self.assertRaises(RuntimeError):
            self.g.declarar_ataque("m0", "m1")

    def test_se_puede_atacar_a_quien_no_ha_invocado(self) -> None:
        """Al objetivo le toca pelear igual: lo tendra antes de la batalla."""
        self.g.invocar_para("m0")
        self.g.declarar_ataque("m0", "m1")
        self.assertEqual(self.g.masters["m0"].objetivo, "m1")

    def test_formar_batallas_cierra_el_plazo(self) -> None:
        self.g.invocar_para("m0")
        self.g.declarar_ataque("m0", "m1")
        batallas, _ = self.g.formar_batallas(random.Random(4))
        self.assertEqual(batallas, [["m0", "m1"]])
        # Nadie pelea sin Servant, asi que esperar no libra del dia.
        self.assertEqual(self.g.sin_invocar, [])
        self.assertTrue(all(m.servant for m in self.g.masters.values()))

    def test_esperar_no_evita_la_batalla(self) -> None:
        self.g.invocar_para("m0")
        self.g.declarar_ataque("m0", "m1")
        self.g.formar_batallas(random.Random(4))
        self.assertIsNotNone(self.g.masters["m1"].servant)

    def test_los_bots_invocan_al_abrir_el_dia(self) -> None:
        g = _guerra(1)
        g.rng = random.Random(5)
        g.rellenar_con_bots()
        g.empezar(_servants())
        self.assertTrue(all(m.servant for m in g.bots))
        self.assertIsNone(g.humanos[0].servant)


class PruebaQuienConoceAQuien(unittest.TestCase):
    """De un Master solo se sabe su Servant si se ha peleado contra el."""

    def setUp(self) -> None:
        self.g = _empezar(_guerra())

    def test_al_principio_nadie_conoce_a_nadie(self) -> None:
        for m in self.g.masters.values():
            self.assertEqual(m.conocidos, set())

    def test_cada_uno_conoce_el_suyo(self) -> None:
        self.assertTrue(self.g.masters["m0"].conoce("m0"))

    def test_no_conoce_a_los_demas(self) -> None:
        self.assertFalse(self.g.masters["m0"].conoce("m1"))

    def test_apuntar_a_uno_no_apunta_a_los_demas(self) -> None:
        self.g.masters["m0"].conocidos.add("m1")
        self.assertTrue(self.g.masters["m0"].conoce("m1"))
        self.assertFalse(self.g.masters["m0"].conoce("m2"))
        # Y no es mutuo por si solo: lo hace la batalla, no el apunte.
        self.assertFalse(self.g.masters["m1"].conoce("m0"))


class PruebaFormacionDeBatallas(unittest.TestCase):
    def setUp(self) -> None:
        self.g = _empezar(_guerra())

    def test_dos_que_atacan_al_mismo_pelean_los_tres(self) -> None:
        self.g.declarar_ataque("m0", "m2")
        self.g.declarar_ataque("m1", "m2")
        batallas, excluidos = self.g.formar_batallas()
        self.assertEqual(batallas, [["m0", "m1", "m2"]])
        self.assertEqual(excluidos, [])

    def test_cadena_de_ataques_une_a_todos(self) -> None:
        self.g.declarar_ataque("m0", "m1")
        self.g.declarar_ataque("m1", "m2")
        batallas, _ = self.g.formar_batallas()
        self.assertEqual(batallas, [["m0", "m1", "m2"]])

    def test_el_tope_son_cuatro(self) -> None:
        for i in range(1, 5):
            self.g.declarar_ataque(f"m{i}", "m0")
        batallas, _ = self.g.formar_batallas(random.Random(1))
        self.assertEqual(max(len(b) for b in batallas), 4)

    def test_quien_se_queda_fuera_se_sortea(self) -> None:
        """El orden de declaracion no decide quien entra.

        Si decidiera, declarar tarde seria la mejor jugada del dia: al que se
        queda fuera le tocaba descansar, y descansar no arriesga nada.
        """
        fuera = set()
        for semilla in range(40):
            g = _guerra()
            _empezar(g)
            for i in range(1, 5):
                g.declarar_ataque(f"m{i}", "m0")
            batallas, _ = g.formar_batallas(random.Random(semilla))
            cadena = next(b for b in batallas if len(b) == 4)
            fuera |= {f"m{i}" for i in range(1, 5)} - set(cadena)
        # A los cuatro les puede tocar quedarse fuera, no solo al ultimo.
        self.assertEqual(fuera, {"m1", "m2", "m3", "m4"})

    def test_el_que_no_cabe_pelea_contra_un_libre(self) -> None:
        """Declarar un ataque es comprometerse a pelear."""
        for i in range(1, 5):
            self.g.declarar_ataque(f"m{i}", "m0")
        batallas, descansan = self.g.formar_batallas(random.Random(1))
        parejas = [b for b in batallas if len(b) == 2]
        self.assertEqual(len(parejas), 1)
        self.assertEqual(descansan, [])
        atacantes = {f"m{i}" for i in range(1, 5)}
        excluido = next(x for x in parejas[0] if x in atacantes)
        rival = next(x for x in parejas[0] if x != excluido)
        # Su nuevo rival es uno de los que no estaban en ninguna batalla.
        self.assertIn(rival, {"m5", "m6"})
        self.assertEqual(self.g.masters[excluido].objetivo, rival)

    def test_dos_que_no_caben_pelean_entre_ellos(self) -> None:
        for i in range(1, 7):
            self.g.declarar_ataque(f"m{i}", "m0")
        batallas, descansan = self.g.formar_batallas(random.Random(3))
        self.assertEqual(sorted(len(b) for b in batallas), [2, 4])
        # Quedan tres fuera: dos se emparejan y el tercero no tiene con quien.
        self.assertEqual(len(descansan), 1)

    def test_solo_descansa_quien_no_tiene_con_quien_pelear(self) -> None:
        for i in range(1, 5):
            self.g.declarar_ataque(f"m{i}", "m0")
        self.g.declarar_ataque("m5", "m6")  # los dos libres, ocupados
        batallas, descansan = self.g.formar_batallas(random.Random(2))
        self.assertEqual(sorted(len(b) for b in batallas), [2, 4])
        self.assertEqual(len(descansan), 1)
        self.assertIn(descansan[0], {f"m{i}" for i in range(1, 5)})

    def test_quien_no_ataca_ni_es_atacado_descansa(self) -> None:
        self.g.declarar_ataque("m0", "m1")
        batallas, _ = self.g.formar_batallas()
        descansan = self.g.descansan(batallas)
        self.assertNotIn("m0", descansan)
        self.assertNotIn("m1", descansan)
        self.assertEqual(len(descansan), MINIMO_MASTERS - 2)

    def test_no_puedes_atacarte_a_ti_mismo(self) -> None:
        with self.assertRaises(ValueError):
            self.g.declarar_ataque("m0", "m0")


class PruebaEliminacion(unittest.TestCase):
    def test_dos_derrotas_eliminan(self) -> None:
        g = _guerra()
        _empezar(g)
        self.assertFalse(g.registrar_derrota("m0"))
        self.assertTrue(g.registrar_derrota("m0"))
        self.assertTrue(g.masters["m0"].eliminado)
        self.assertEqual(len(g.activos), MINIMO_MASTERS - 1)

    def test_la_guerra_termina_con_un_solo_master(self) -> None:
        g = _guerra()
        _empezar(g)
        for i in range(1, MINIMO_MASTERS):
            g.registrar_derrota(f"m{i}")
            g.registrar_derrota(f"m{i}")
        g.siguiente_dia()
        self.assertTrue(g.terminada)
        self.assertEqual(g.ganador().id, "m0")


class PruebaRendirse(unittest.TestCase):
    """Salirse de la guerra: no la cierra, pero te saca.

    Lo que lo sostiene es que `Master.eliminado` mira las dos vias (perder y
    rendirse), asi que no hizo falta una regla nueva en ningun otro sitio.
    """

    def test_rendirse_te_saca_de_los_activos(self) -> None:
        g = _guerra()
        _empezar(g)
        self.assertFalse(g.rendirse("m0"))
        self.assertTrue(g.masters["m0"].retirado)
        self.assertTrue(g.masters["m0"].eliminado)
        self.assertEqual(len(g.activos), MINIMO_MASTERS - 1)
        self.assertFalse(g.terminada)

    def test_no_se_le_espera_para_cerrar_el_dia(self) -> None:
        g = _guerra()
        _empezar(g)
        g.rendirse("m0")
        self.assertNotIn("m0", [m.id for m in g.faltan_por_estar_listos])

    def test_no_entra_en_las_batallas_del_dia(self) -> None:
        g = _guerra()
        _empezar(g)
        g.rendirse("m0")
        grupos, _ = g.formar_batallas(random.Random(1))
        self.assertNotIn("m0", [id_ for grupo in grupos for id_ in grupo])

    def test_el_que_queda_gana_la_guerra(self) -> None:
        g = _guerra()
        _empezar(g)
        for i in range(1, MINIMO_MASTERS - 1):
            g.rendirse(f"m{i}")
        self.assertFalse(g.terminada)
        self.assertTrue(g.rendirse(f"m{MINIMO_MASTERS - 1}"))
        self.assertTrue(g.terminada)
        self.assertEqual(g.ganador().id, "m0")

    def _todos_se_van(self, humanos: int) -> Guerra:
        g = _guerra(humanos)
        g.rng = random.Random(3)
        g.rellenar_con_bots()
        _empezar(g)
        for m in list(g.masters.values()):
            if m.id != "m0":
                g.rendirse(m.id)
        return g

    def test_con_cuatro_personas_no_se_lleva_el_grial(self) -> None:
        """Lo que impide que cuatro amigos se repartan griales rindiendose."""
        g = self._todos_se_van(MINIMO_HUMANOS_PARA_GRIAL)
        self.assertTrue(g.otorga_grial)
        self.assertEqual(g.ganador().id, "m0")
        self.assertTrue(g.acabo_por_retirada)
        self.assertIsNone(g.gana_el_grial())

    def test_con_seis_personas_si_se_lo_lleva(self) -> None:
        """Mas de 5 apuntadas: juntar a seis para farmear ya es mas trabajo."""
        g = self._todos_se_van(MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA)
        self.assertTrue(g.acabo_por_retirada)
        self.assertEqual(g.gana_el_grial().id, "m0")

    def test_con_cinco_todavia_no(self) -> None:
        g = self._todos_se_van(MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA - 1)
        self.assertIsNone(g.gana_el_grial())

    def test_una_guerra_que_se_pelea_si_paga_el_grial(self) -> None:
        """La retirada de uno no anula el Grial de una guerra jugada."""
        g = _guerra(MINIMO_HUMANOS_PARA_GRIAL)
        g.rng = random.Random(3)
        g.rellenar_con_bots()
        _empezar(g)
        g.rendirse("m1")
        for m in list(g.masters.values()):
            if m.id in ("m0", "m1"):
                continue
            g.registrar_derrota(m.id)
            g.registrar_derrota(m.id)
        g.siguiente_dia()
        self.assertFalse(g.acabo_por_retirada)
        self.assertEqual(g.gana_el_grial().id, "m0")

    def test_rendirse_dos_veces_no_hace_nada(self) -> None:
        g = _guerra()
        _empezar(g)
        g.rendirse("m0")
        self.assertFalse(g.rendirse("m0"))
        self.assertEqual(len(g.activos), MINIMO_MASTERS - 1)


class PruebaCancelar(unittest.TestCase):
    """Cerrar la guerra a mano: se acaba, pero no la gana nadie."""

    def test_cancelar_la_termina(self) -> None:
        g = _guerra()
        _empezar(g)
        g.cancelar()
        self.assertTrue(g.cancelada)
        self.assertTrue(g.terminada)
        self.assertIs(g.fase, Fase.TERMINADA)

    def test_cancelar_no_corona_a_nadie(self) -> None:
        g = _guerra()
        _empezar(g)
        g.cancelar()
        self.assertIsNone(g.ganador())
        self.assertIsNone(g.gana_el_grial())

    def test_cancelar_no_corona_ni_al_ultimo_que_quedaba(self) -> None:
        """La razon de que `cancelada` exista aparte de la fase.

        Si solo se mirara la fase, cortar una guerra en la que ya solo queda
        uno en pie seria lo mismo que ganarla, y cancelar no es ganar.
        """
        g = _guerra()
        _empezar(g)
        for i in range(1, MINIMO_MASTERS):
            g.registrar_derrota(f"m{i}")
            g.registrar_derrota(f"m{i}")
        self.assertEqual(len(g.activos), 1)
        g.cancelar()
        self.assertIsNone(g.ganador())

    def test_cancelar_quita_el_plazo(self) -> None:
        """Para que el vigilante no intente cerrar un dia que ya no existe."""
        g = _guerra()
        _empezar(g)
        self.assertGreater(g.vence_preparacion, 0)
        g.cancelar()
        self.assertEqual(g.vence_preparacion, 0.0)

    def test_se_puede_cancelar_un_lobby(self) -> None:
        """Una guerra abierta por error se cierra sin haber empezado."""
        g = _guerra(2)
        self.assertIs(g.fase, Fase.LOBBY)
        g.cancelar()
        self.assertTrue(g.terminada)
        self.assertIsNone(g.ganador())


class PruebaBotsYGrial(unittest.TestCase):
    """Los cupos que no llena nadie los llena la IA, y entonces no hay Grial."""

    def _con_bots(self, humanos: int) -> Guerra:
        g = _guerra(humanos)
        g.rng = random.Random(3)
        g.rellenar_con_bots()
        _empezar(g)
        return g

    def test_una_persona_sola_llena_la_mesa_con_seis_bots(self) -> None:
        g = self._con_bots(1)
        self.assertEqual(len(g.masters), MAXIMO_MASTERS)
        self.assertEqual(len(g.humanos), 1)
        self.assertEqual(len(g.bots), 6)
        self.assertTrue(all(m.servant for m in g.masters.values()))

    def test_jugar_contra_bots_no_entrega_el_grial(self) -> None:
        g = self._con_bots(1)
        self.assertFalse(g.otorga_grial)
        # Gana la persona, pero el Grial no se entrega.
        for m in g.bots:
            g.registrar_derrota(m.id)
            g.registrar_derrota(m.id)
        g.siguiente_dia()
        self.assertEqual(g.ganador().id, "m0")
        self.assertIsNone(g.gana_el_grial())

    def test_con_cuatro_personas_el_grial_esta_en_juego(self) -> None:
        g = self._con_bots(MINIMO_HUMANOS_PARA_GRIAL)
        self.assertTrue(g.otorga_grial)
        self.assertEqual(len(g.bots), MAXIMO_MASTERS - MINIMO_HUMANOS_PARA_GRIAL)
        for id_ in [m.id for m in g.masters.values() if m.id != "m0"]:
            g.registrar_derrota(id_)
            g.registrar_derrota(id_)
        g.siguiente_dia()
        self.assertEqual(g.gana_el_grial().id, "m0")

    def test_con_tres_personas_todavia_no(self) -> None:
        self.assertFalse(self._con_bots(MINIMO_HUMANOS_PARA_GRIAL - 1).otorga_grial)

    def test_si_gana_un_bot_no_hay_grial(self) -> None:
        g = self._con_bots(MINIMO_HUMANOS_PARA_GRIAL)
        ganador = g.bots[0]
        for m in list(g.masters.values()):
            if m.id == ganador.id:
                continue
            g.registrar_derrota(m.id)
            g.registrar_derrota(m.id)
        g.siguiente_dia()
        self.assertEqual(g.ganador().id, ganador.id)
        self.assertIsNone(g.gana_el_grial())

    def test_una_guerra_llena_de_gente_no_recibe_bots(self) -> None:
        g = _guerra()
        self.assertEqual(g.rellenar_con_bots(), [])
        self.assertTrue(g.otorga_grial)

    def test_sin_nadie_no_se_puede_empezar(self) -> None:
        g = Guerra(id="1", canal_id="1")
        self.assertFalse(g.puede_empezar_con_bots)
        with self.assertRaises(RuntimeError):
            g.rellenar_con_bots()

    def test_no_se_rellena_una_guerra_ya_empezada(self) -> None:
        g = self._con_bots(1)
        with self.assertRaises(RuntimeError):
            g.rellenar_con_bots()

    def test_los_bots_declaran_ataque_siempre(self) -> None:
        # Sin llamar a nada: `empezar` abre el dia por su cuenta.
        g = self._con_bots(1)
        for m in g.bots:
            self.assertIsNotNone(m.objetivo)
            self.assertNotEqual(m.objetivo, m.id)
        self.assertEqual(len(g.orden_declaraciones), 6)

    def test_los_bots_entrenan_y_suben_de_nivel(self) -> None:
        g = self._con_bots(1)
        for m in g.bots:
            self.assertEqual(m.intentos_npc, 4)
            self.assertGreater(m.servant.nivel, 1)

    def test_la_persona_no_entrena_sola(self) -> None:
        """Abrir el dia es cosa de la IA: al jugador no le gasta sus combates."""
        g = self._con_bots(1)
        persona = g.humanos[0]
        self.assertEqual(persona.intentos_npc, 0)
        self.assertIsNone(persona.objetivo)

    def test_cada_dia_nuevo_los_bots_vuelven_a_entrenar(self) -> None:
        g = self._con_bots(1)
        niveles = {m.id: m.servant.nivel for m in g.bots}
        g.siguiente_dia()
        for m in g.bots:
            self.assertEqual(m.intentos_npc, 4)
            self.assertIsNotNone(m.objetivo)
            self.assertGreaterEqual(m.servant.nivel, niveles[m.id])
        self.assertEqual(g.humanos[0].intentos_npc, 0)

    def test_el_creador_es_el_primero_que_se_inscribe(self) -> None:
        g = _guerra(2)
        self.assertEqual(g.creador_id, "m0")


class PruebaPenalizacionNPC(unittest.TestCase):
    def test_tabla_de_vida(self) -> None:
        s = _servants()[0]
        maximo = s.vida_maxima
        for derrotas, factor in PENALIZACION_VIDA.items():
            self.assertEqual(vida_inicial(s, derrotas), int(maximo * factor))

    def test_el_dia_nuevo_borra_las_penalizaciones(self) -> None:
        g = _guerra()
        _empezar(g)
        m = g.masters["m0"]
        m.derrotas_npc = 3
        m.intentos_npc = 4
        g.siguiente_dia()
        self.assertEqual(m.derrotas_npc, 0)
        self.assertEqual(m.intentos_npc_restantes, 4)
        self.assertEqual(g.dia, 2)


if __name__ == "__main__":
    unittest.main()
