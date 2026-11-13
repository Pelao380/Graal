"""Pruebas de la batalla que espera a las personas.

Lo que se fija aqui no son numeros de balance (eso es del simulador) sino las
reglas que, si se rompen, rompen el combate sin que nada avise: que un turno
no se resuelva a medias, que nadie decida dos veces, que un combate sin
personas no espere a nadie y que un turno sin contestar no deje la guerra
parada para siempre.
"""

from __future__ import annotations

import random
import unittest

from src.game import dia, invocacion, objetos, personajes
from src.game.battle import Accion, Decision, Estado
from src.game.combate import SEGUNDOS_POR_TURNO, Combate, Espera
from src.game.war import DERROTAS_PARA_ELIMINAR, Fase, Guerra

CATALOGO = personajes.cargar()


class Reloj:
    """Un reloj que solo avanza cuando se le dice."""

    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


def _guerra(humanos: int = 2, semilla: int = 7) -> tuple[Guerra, Reloj]:
    rng = random.Random(semilla)
    reloj = Reloj()
    g = Guerra(id="1", canal_id="100", rng=rng, reloj=reloj)
    for i in range(humanos):
        g.inscribir(f"h{i}", f"Humano {i}")
    g.rellenar_con_bots()
    g.empezar(invocacion.invocar(CATALOGO, rng))
    for m in g.sin_invocar:
        g.invocar_para(m.id, rng)
    for m in g.humanos:
        m.listo = True
    return g, reloj


def _combate(guerra: Guerra, ids: list[str], humanos: set[str]) -> Combate:
    return Combate(
        dia.armar_batalla(guerra, ids, guerra.rng),
        humanos=humanos,
        rng=guerra.rng,
        reloj=guerra.reloj,
    )


def _atacar(combate: Combate, id_: str) -> list[str]:
    rival = combate.batalla.rivales_de(id_)[0]
    return combate.decidir(id_, Decision(accion=Accion.ATACAR, objetivo=rival.id))


class PruebaEsperar(unittest.TestCase):
    def test_un_turno_no_se_resuelve_a_medias(self) -> None:
        """Si se resolviera, el orden de llegada valdria informacion."""
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        self.assertEqual(c.espera, Espera.TURNO)
        self.assertEqual(sorted(c.pendientes), ["h0", "h1"])
        self.assertEqual(_atacar(c, "h0"), [], "con uno solo no pasa nada")
        self.assertEqual(c.batalla.turno, 0)
        self.assertEqual(c.pendientes, ["h1"])
        self.assertTrue(_atacar(c, "h1"), "el ultimo cierra el turno")
        self.assertGreaterEqual(c.batalla.turno, 1)

    def test_nadie_decide_dos_veces(self) -> None:
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        _atacar(c, "h0")
        self.assertTrue(c.ya_decidio("h0"))
        with self.assertRaises(RuntimeError):
            _atacar(c, "h0")

    def test_un_bot_no_decide_a_mano(self) -> None:
        g, _ = _guerra(humanos=1)
        c = _combate(g, ["h0", "bot:1"], {"h0"})
        self.assertEqual(c.pendientes, ["h0"], "al bot no se le espera")
        with self.assertRaises(RuntimeError):
            _atacar(c, "bot:1")
        self.assertTrue(_atacar(c, "h0"), "la persona sola cierra el turno")

    def test_una_batalla_de_bots_se_juega_sola(self) -> None:
        """No hay a quien esperar, asi que esperar seria colgarse."""
        g, _ = _guerra(humanos=1)
        c = _combate(g, ["bot:1", "bot:2"], set())
        self.assertTrue(c.terminado)
        self.assertEqual(c.espera, Espera.NADA)
        self.assertEqual(c.pendientes, [])
        self.assertTrue(c.batalla.registro)

    def test_cuando_cae_la_persona_la_batalla_se_acaba_sola(self) -> None:
        g, _ = _guerra(humanos=1)
        c = _combate(g, ["h0", "bot:1", "bot:2"], {"h0"})
        c.batalla.combatientes["h0"].vida = 0
        # El turno siguiente lo juega la IA entera, y a partir de ahi nadie
        # tiene nada que decidir.
        c.avanzar_con_ia()
        self.assertEqual(c.pendientes, [])
        self.assertTrue(c.terminado)

    def test_no_se_decide_despues_de_acabar(self) -> None:
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        vueltas = 0
        while not c.terminado and vueltas < 200:
            vueltas += 1
            c.avanzar_con_ia()
        self.assertTrue(c.terminado)
        # Se llama a `decidir` a pelo y no por `_atacar`, que busca un rival
        # vivo: cuando el que decide es el que gano no queda ninguno, y lo que
        # se prueba aqui es que decidir despues del final no vale, gane quien
        # gane. Con `_atacar` el test dependia de quien hubiera ganado.
        with self.assertRaises(RuntimeError):
            c.decidir("h0", Decision(accion=Accion.ATACAR, objetivo="h1"))


class PruebaVotacion(unittest.TestCase):
    def _hasta_la_votacion(self) -> Combate:
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1", "bot:1"], {"h0", "h1"})
        # Se tumba a uno a mano: asi la votacion se abre en el turno siguiente
        # sin depender de la suerte de 20 turnos de combate.
        c.batalla.combatientes["bot:1"].vida = 1
        for _ in range(60):
            if c.espera is Espera.VOTACION or c.terminado:
                break
            c.avanzar_con_ia()
        return c

    def test_la_votacion_pide_votos_a_las_personas(self) -> None:
        c = self._hasta_la_votacion()
        if c.terminado:
            self.skipTest("la batalla acabo sin abrir votacion")
        self.assertEqual(c.espera, Espera.VOTACION)
        self.assertEqual(sorted(c.pendientes), ["h0", "h1"])
        self.assertEqual(c.votar("h0", True), [], "falta el otro voto")
        self.assertTrue(c.votar("h1", True))
        # Los dos siguen, asi que se abre el turno especial: ya no hay
        # votacion abierta, que es lo que importa.
        self.assertNotEqual(c.batalla.estado, Estado.VOTACION)

    def test_si_nadie_quiere_seguir_la_batalla_acaba(self) -> None:
        c = self._hasta_la_votacion()
        if c.terminado:
            self.skipTest("la batalla acabo sin abrir votacion")
        c.votar("h0", False)
        c.votar("h1", False)
        self.assertTrue(c.terminado)

    def test_en_el_turno_especial_solo_decide_quien_sigue(self) -> None:
        c = self._hasta_la_votacion()
        if c.terminado:
            self.skipTest("la batalla acabo sin abrir votacion")
        c.votar("h0", True)
        c.votar("h1", False)
        if c.terminado:
            self.skipTest("el turno especial dejo a uno solo en pie")
        self.assertEqual(c.batalla.estado, Estado.TURNO_ESPECIAL)
        self.assertEqual(c.pendientes, ["h0"], "al que se retiro no se le pide")
        self.assertEqual(
            c.batalla.acciones_posibles("h1"), [Accion.ESPERAR]
        )


class PruebaElPlazoDelTurno(unittest.TestCase):
    def test_el_plazo_vence_y_la_ia_decide_por_quien_falta(self) -> None:
        g, reloj = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        _atacar(c, "h0")
        self.assertFalse(c.plazo_cumplido())
        reloj.avanzar(SEGUNDOS_POR_TURNO - 1)
        self.assertFalse(c.plazo_cumplido())
        reloj.avanzar(1)
        self.assertTrue(c.plazo_cumplido())
        self.assertTrue(c.avanzar_con_ia())
        self.assertEqual(c.batalla.turno, 1)

    def test_el_reloj_se_pone_a_cero_en_cada_turno(self) -> None:
        """Son 5 minutos por turno, no 5 minutos por batalla."""
        g, reloj = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        reloj.avanzar(SEGUNDOS_POR_TURNO + 1)
        c.avanzar_con_ia()
        self.assertFalse(c.plazo_cumplido())

    def test_sin_nadie_pendiente_no_hay_plazo_que_vencer(self) -> None:
        g, reloj = _guerra(humanos=1)
        c = _combate(g, ["bot:1", "bot:2"], set())
        reloj.avanzar(SEGUNDOS_POR_TURNO * 10)
        self.assertFalse(c.plazo_cumplido())


class PruebaElDiaAMano(unittest.TestCase):
    def test_abrir_combates_deja_el_dia_en_batalla(self) -> None:
        g, _ = _guerra()
        g.declarar_ataque("h0", "h1")
        estado = dia.abrir_combates(g, g.rng)
        self.assertEqual(g.fase, Fase.BATALLA)
        self.assertEqual(g.dia, 1, "el dia no pasa hasta que se pelee")
        self.assertTrue(estado.pendientes)
        self.assertIsNotNone(estado.combate_de("h0"))

    def test_las_batallas_de_bots_salen_ya_resueltas(self) -> None:
        g, _ = _guerra(humanos=1)
        estado = dia.abrir_combates(g, g.rng)
        self.assertTrue(estado.resueltos, "alguna batalla es solo de bots")
        for b in estado.resueltos:
            self.assertNotIn("h0", b.grupo)

    def test_no_se_cierra_el_dia_con_batallas_a_medias(self) -> None:
        g, _ = _guerra()
        g.declarar_ataque("h0", "h1")
        estado = dia.abrir_combates(g, g.rng)
        with self.assertRaises(RuntimeError):
            dia.cerrar_combates(g, estado)

    def test_una_batalla_acabada_se_anota_una_sola_vez(self) -> None:
        """Si se anotara dos veces, una derrota contaria doble."""
        g, _ = _guerra()
        g.declarar_ataque("h0", "h1")
        estado = dia.abrir_combates(g, g.rng)
        for c in estado.pendientes:
            while not c.terminado:
                c.avanzar_con_ia()
        primeros = dia.recoger(g, estado)
        self.assertTrue(primeros)
        derrotas = {m.id: m.derrotas for m in g.masters.values()}
        self.assertEqual(dia.recoger(g, estado), [], "ya estaban anotadas")
        self.assertEqual({m.id: m.derrotas for m in g.masters.values()}, derrotas)

    def test_pelear_destapa_los_servants_igual_que_antes(self) -> None:
        g, _ = _guerra()
        g.declarar_ataque("h0", "h1")
        estado = dia.abrir_combates(g, g.rng)
        grupo = sorted(estado.pendientes[0].batalla.combatientes)
        dia.abandonar_combates(g, estado)
        for id_ in grupo:
            otros = {o for o in grupo if o != id_}
            self.assertTrue(otros <= g.masters[id_].conocidos)

    def test_abandonar_combates_cierra_el_dia(self) -> None:
        g, _ = _guerra()
        g.declarar_ataque("h0", "h1")
        estado = dia.abrir_combates(g, g.rng)
        cierre = dia.abandonar_combates(g, estado)
        self.assertEqual(cierre.dia, 1)
        self.assertTrue(g.dia == 2 or g.terminada)
        self.assertNotEqual(g.fase, Fase.BATALLA)

    def test_jugar_a_mano_deja_la_misma_mesa_que_la_ia(self) -> None:
        """Las dos formas de pelear el dia tienen que acabar igual de enteras."""
        a, _ = _guerra()
        b, _ = _guerra()
        a.declarar_ataque("h0", "h1")
        b.declarar_ataque("h0", "h1")
        de_corrido = dia.cerrar_dia(a, a.rng)
        a_mano = dia.abandonar_combates(b, dia.abrir_combates(b, b.rng))
        self.assertEqual(de_corrido.dia, a_mano.dia)
        # Los mismos grupos; el orden no, porque a mano las batallas se
        # apuntan segun acaban y las de bots acaban primero.
        self.assertEqual(
            sorted(tuple(sorted(x.grupo)) for x in de_corrido.batallas),
            sorted(tuple(sorted(x.grupo)) for x in a_mano.batallas),
        )
        self.assertEqual(a.dia, b.dia)
        self.assertEqual(a.fase, b.fase)


class PruebaLasDerrotas(unittest.TestCase):
    """Cada Servant que cae paga su derrota, no solo el primero.

    La batalla se acaba cuando cae uno, pero si quedan dos o mas en pie y
    alguien vota por seguir, se sigue y puede caer otro. Durante un tiempo
    solo contaba el primero y quien cayera despues salia gratis.
    """

    def _guerra_de_tres(self) -> tuple[Guerra, list[str]]:
        """Una guerra y un grupo de tres, para armar batallas a mano.

        Dos de las pruebas falsean el final de la batalla (`batalla.caidos`)
        en vez de pelear hasta que caigan dos: que caigan dos depende de como
        vote la IA, y lo que se prueba aqui es la cuenta de las derrotas, no
        la votacion. La ultima prueba de la clase si lo juega de verdad.
        """
        g, _ = _guerra(humanos=1)
        return g, ["h0", "bot:1", "bot:2"]

    def test_se_apuntan_todos_los_caidos(self) -> None:
        g, grupo = self._guerra_de_tres()
        batalla = dia.armar_batalla(g, grupo, g.rng)
        # Se falsea el final: dos cayeron, uno quedo en pie.
        batalla.caidos = ["bot:1", "bot:2"]
        b = dia.anotar_batalla(g, grupo, batalla)
        self.assertEqual(b.caidos, ["bot:1", "bot:2"])
        self.assertEqual(g.masters["bot:1"].derrotas, 1)
        self.assertEqual(g.masters["bot:2"].derrotas, 1)

    def test_el_segundo_caido_tambien_puede_quedar_eliminado(self) -> None:
        g, grupo = self._guerra_de_tres()
        g.masters["bot:2"].derrotas = DERROTAS_PARA_ELIMINAR - 1
        batalla = dia.armar_batalla(g, grupo, g.rng)
        batalla.caidos = ["bot:1", "bot:2"]
        b = dia.anotar_batalla(g, grupo, batalla)
        self.assertEqual(b.eliminados, ["bot:2"])
        self.assertTrue(g.masters["bot:2"].eliminado)
        self.assertFalse(g.masters["bot:1"].eliminado)

    def test_una_batalla_sin_caidos_no_cuesta_derrotas(self) -> None:
        g, grupo = self._guerra_de_tres()
        batalla = dia.armar_batalla(g, grupo, g.rng)
        b = dia.anotar_batalla(g, grupo, batalla)
        self.assertEqual(b.caidos, [])
        self.assertEqual(b.eliminados, [])
        self.assertTrue(all(g.masters[i].derrotas == 0 for i in grupo))

    def test_jugando_de_verdad_las_derrotas_cuadran_con_las_caidas(self) -> None:
        """La cuenta tiene que salir sin falsear nada, sobre muchas guerras."""
        for semilla in range(12):
            g, _ = _guerra(humanos=2, semilla=semilla)
            g.declarar_ataque("h0", "h1")
            estado = dia.abrir_combates(g, g.rng)
            cierre = dia.abandonar_combates(g, estado)
            caidas: dict[str, int] = {}
            for b in cierre.batallas:
                for id_ in b.caidos:
                    caidas[id_] = caidas.get(id_, 0) + 1
            for id_, cuantas in caidas.items():
                self.assertEqual(
                    g.masters[id_].derrotas,
                    cuantas,
                    f"semilla {semilla}: {id_} cayo {cuantas} veces",
                )


class PruebaRecuperarElDia(unittest.TestCase):
    """Lo que saca del atasco a una guerra que se quedo en `Fase.BATALLA`."""

    def test_recupera_lo_que_quedo_a_medias(self) -> None:
        g, _ = _guerra()
        g.declarar_ataque("h0", "h1")
        dia.abrir_combates(g, g.rng)
        # Y aqui el bot se reinicia: los combates estaban en memoria.
        cierre = dia.recuperar_dia(g, g.rng)
        self.assertEqual(cierre.dia, 1)
        self.assertTrue(g.dia == 2 or g.terminada)

    def test_no_repite_una_batalla_que_ya_se_peleo(self) -> None:
        """`ultimo_registro_dia` es lo que sobrevive, y es lo que lo evita."""
        g, _ = _guerra()
        g.declarar_ataque("h0", "h1")
        estado = dia.abrir_combates(g, g.rng)
        for c in estado.pendientes:
            while not c.terminado:
                c.avanzar_con_ia()
        dia.recoger(g, estado)
        derrotas = sum(m.derrotas for m in g.masters.values())
        dia.recuperar_dia(g, g.rng)
        self.assertEqual(
            sum(m.derrotas for m in g.masters.values()),
            derrotas,
            "una batalla ya peleada no puede volver a costar una derrota",
        )

    def test_solo_sirve_desde_la_fase_de_batalla(self) -> None:
        g, _ = _guerra()
        with self.assertRaises(RuntimeError):
            dia.recuperar_dia(g, g.rng)


class PruebaUsarUnObjeto(unittest.TestCase):
    """Usar un objeto no es la decision del turno, y eso es toda la regla.

    Si contara como decision, un objeto seria una habilidad gratis con otro
    nombre; si cerrara el turno, usarlo y atacar serian la misma pulsacion.
    """

    def test_no_cuenta_como_la_decision_del_turno(self) -> None:
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        self.assertTrue(c.usar_objeto("h0", objetos.objeto("piedra_furia")))
        self.assertFalse(c.ya_decidio("h0"), "sigue teniendo que elegir")
        self.assertEqual(sorted(c.pendientes), ["h0", "h1"])
        self.assertEqual(c.batalla.turno, 0, "no cerro el turno")

    def test_despues_de_usarlo_todavia_se_ataca(self) -> None:
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        c.usar_objeto("h0", objetos.objeto("piedra_furia"))
        _atacar(c, "h0")
        _atacar(c, "h1")
        self.assertGreaterEqual(c.batalla.turno, 1)

    def test_se_puede_usar_aunque_ya_hayas_decidido(self) -> None:
        """Esperando al otro no te queda nada que hacer; el objeto si."""
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        _atacar(c, "h0")
        self.assertTrue(c.usar_objeto("h0", objetos.objeto("gema_mana")))

    def test_el_mana_se_nota(self) -> None:
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        antes = c.batalla.combatientes["h0"].mana
        c.usar_objeto("h0", objetos.objeto("gema_mana"))
        self.assertGreater(c.batalla.combatientes["h0"].mana, antes)

    def test_curar_no_pasa_del_maximo(self) -> None:
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        combatiente = c.batalla.combatientes["h0"]
        c.usar_objeto("h0", objetos.objeto("elixir"))
        self.assertLessEqual(combatiente.vida, combatiente.servant.vida_maxima)

    def test_el_registro_lo_cuenta(self) -> None:
        """Nombra el objeto, porque el detalle solo lo lee quien peleo."""
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        piedra = objetos.objeto("piedra_furia")
        eventos = c.usar_objeto("h0", piedra)
        nombre = piedra.nombre_para(c.batalla.idioma)
        self.assertTrue(any(nombre in e for e in eventos), eventos)
        self.assertEqual(c.batalla.registro[-len(eventos):], eventos)

    def test_un_bot_no_usa_objetos_a_mano(self) -> None:
        g, _ = _guerra(humanos=1)
        c = _combate(g, ["h0", "bot:1"], {"h0"})
        with self.assertRaises(RuntimeError):
            c.usar_objeto("bot:1", objetos.objeto("piedra_furia"))

    def test_no_se_usa_fuera_del_combate(self) -> None:
        g, _ = _guerra()
        c = _combate(g, ["h0", "h1"], {"h0", "h1"})
        with self.assertRaises(RuntimeError):
            c.usar_objeto("h9", objetos.objeto("piedra_furia"))

    def test_no_se_usa_despues_de_acabar(self) -> None:
        g, _ = _guerra(humanos=1)
        c = _combate(g, ["h0", "bot:1"], {"h0"})
        while not c.terminado:
            c.avanzar_con_ia()
        with self.assertRaises(RuntimeError):
            c.usar_objeto("h0", objetos.objeto("piedra_furia"))

    def test_el_tope_por_batalla_lo_lleva_el_master(self) -> None:
        """El combate no sabe de inventarios; el tope es del Master."""
        g, _ = _guerra()
        master = g.masters["h0"]
        master.inventario.anadir("piedra_furia")
        master.inventario.anadir("piedra_furia")
        self.assertTrue(master.inventario.puede_usar_en_la_batalla)
        master.inventario.usados_en_la_batalla += 1
        self.assertFalse(master.inventario.puede_usar_en_la_batalla)
        self.assertEqual(master.inventario.cuantos_de("piedra_furia"), 2)

    def test_el_dia_nuevo_devuelve_el_uso(self) -> None:
        g, _ = _guerra()
        master = g.masters["h0"]
        master.inventario.usados_en_la_batalla = 1
        master.nuevo_dia()
        self.assertTrue(master.inventario.puede_usar_en_la_batalla)


if __name__ == "__main__":
    unittest.main()
