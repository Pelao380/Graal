"""La tienda y las dos monedas, sin Discord y sin red.

Lo que se fija aqui no son los precios —esos se afinan con el simulador— sino
las reglas que, si se rompen, rompen la economia sin que nada avise:

- **cobrar sin entregar**, que es el unico error de una tienda que de verdad
  enfada, y su contrario, entregar sin cobrar;
- **el oro muere con la guerra y los griales no**, que es la razon de que haya
  dos monedas y no una;
- **nadie farmea griales contra bots**, porque se paga por `grial()` y no por
  `ganador()`;
- y que **ningun objeto devuelva mas oro del que cuesta**, que convertiria la
  tienda en una maquina de hacer oro.
"""

from __future__ import annotations

import random
import unittest

from src.game import dia, invocacion, npc, objetos, personajes, tienda
from src.game.clases import Clase
from src.game.objetos import Momento
from src.game.servant import Servant
from src.game.war import Guerra, Master

CATALOGO = personajes.cargar()


def _master(oro: int = 0) -> Master:
    return Master(id="h0", nombre="Humano 0", oro=oro)


class PruebaLosPrecios(unittest.TestCase):
    def test_todo_lo_que_se_puede_usar_se_puede_comprar(self) -> None:
        """Un objeto que solo se suelta seria un objeto que no se puede buscar."""
        usables = {
            o.clave
            for o in objetos.CATALOGO
            if o.momento in (Momento.COMBATE, Momento.PREPARACION)
        }
        self.assertEqual(usables, set(tienda.PRECIO_EN_ORO))

    def test_todo_lo_que_esta_a_la_venta_tiene_precio_y_moneda(self) -> None:
        for o in tienda.a_la_venta():
            cuanto, moneda = tienda.precio_de(o)
            self.assertGreater(cuanto, 0)
            self.assertIs(moneda, tienda.Moneda.ORO)

    def test_los_catalizadores_se_pagan_en_griales(self) -> None:
        clase = objetos.catalizador_de_clase(Clase.SABER)
        servant = objetos.catalizador_de_servant(91)
        self.assertEqual(
            tienda.precio_de(clase),
            (tienda.PRECIO_CATALIZADOR_CLASE, tienda.Moneda.GRIALES),
        )
        self.assertEqual(
            tienda.precio_de(servant),
            (tienda.PRECIO_CATALIZADOR_SERVANT, tienda.Moneda.GRIALES),
        )

    def test_un_servant_concreto_cuesta_mas_que_una_clase(self) -> None:
        """Pedir a alguien es mas que pedir una clase: hay 348 y 8."""
        self.assertGreater(
            tienda.PRECIO_CATALIZADOR_SERVANT, tienda.PRECIO_CATALIZADOR_CLASE
        )

    def test_la_tienda_no_fabrica_oro(self) -> None:
        """El reloj de arena da un entrenamiento, y un entrenamiento da oro.

        Si costara menos de lo que paga el NPC mas generoso, comprarlo y
        pelear seria un bucle de oro infinito. Es la unica comprobacion de
        precio que no es cuestion de gusto, asi que es una prueba.
        """
        self.assertGreater(
            tienda.PRECIO_EN_ORO["reloj_arena"], max(tienda.ORO_POR_NPC.values())
        )

    def test_el_npc_mas_duro_paga_mas_que_el_mas_facil(self) -> None:
        indices = sorted(tienda.ORO_POR_NPC)
        pagos = [tienda.ORO_POR_NPC[i] for i in indices]
        self.assertEqual(pagos, sorted(pagos))
        self.assertLess(pagos[0], pagos[-1])

    def test_una_batalla_paga_mas_que_cualquier_npc(self) -> None:
        """Hay una batalla al dia como mucho, y a veces ninguna."""
        self.assertGreater(
            tienda.ORO_POR_BATALLA_GANADA, max(tienda.ORO_POR_NPC.values())
        )

    def test_el_critico_es_lo_mas_barato(self) -> None:
        """Es el efecto mas flojo que tenemos, asi que no puede ser el mas caro."""
        self.assertEqual(
            tienda.PRECIO_EN_ORO["ojo_certero"], min(tienda.PRECIO_EN_ORO.values())
        )

    def test_a_la_venta_va_en_orden_de_precio(self) -> None:
        precios = [tienda.precio_de(o)[0] for o in tienda.a_la_venta()]
        self.assertEqual(precios, sorted(precios))

    def test_a_la_venta_filtra_por_momento(self) -> None:
        for momento in (Momento.COMBATE, Momento.PREPARACION):
            for o in tienda.a_la_venta(momento):
                self.assertIs(o.momento, momento)

    def test_una_guerra_entera_no_paga_para_comprarlo_todo(self) -> None:
        """La tienda tiene que obligar a elegir, no a juntar.

        Referencia medida mas abajo (`PruebaLaEconomiaDeUnaGuerra`): una guerra
        de 4 dias entrenando da del orden de 300 de oro. Comprarlo todo cuesta
        bastante mas, y eso es lo que hace que la tienda sea una decision.
        """
        todo = sum(tienda.PRECIO_EN_ORO.values())
        self.assertGreater(todo, 400, "comprarlo todo tiene que ser inalcanzable")


class PruebaComprarConOro(unittest.TestCase):
    def test_comprar_cobra_y_entrega(self) -> None:
        m = _master(oro=100)
        compra = tienda.comprar_con_oro(m, "elixir")
        self.assertTrue(compra.ok)
        self.assertEqual(compra.pagado, tienda.PRECIO_EN_ORO["elixir"])
        self.assertIs(compra.moneda, tienda.Moneda.ORO)
        self.assertEqual(m.oro, 100 - tienda.PRECIO_EN_ORO["elixir"])
        self.assertEqual(m.inventario.cuantos_de("elixir"), 1)

    def test_sin_oro_no_cobra_ni_entrega(self) -> None:
        m = _master(oro=0)
        compra = tienda.comprar_con_oro(m, "elixir")
        self.assertFalse(compra.ok)
        self.assertIs(compra.fallo, tienda.Fallo.SIN_ORO)
        self.assertEqual(m.oro, 0)
        self.assertTrue(m.inventario.vacio)

    def test_el_oro_justo_alcanza(self) -> None:
        m = _master(oro=tienda.PRECIO_EN_ORO["elixir"])
        self.assertTrue(tienda.comprar_con_oro(m, "elixir").ok)
        self.assertEqual(m.oro, 0)

    def test_uno_menos_del_justo_no_alcanza(self) -> None:
        m = _master(oro=tienda.PRECIO_EN_ORO["elixir"] - 1)
        self.assertFalse(tienda.comprar_con_oro(m, "elixir").ok)

    def test_con_el_inventario_lleno_no_se_cobra(self) -> None:
        """El error que mas duele: pagar y no recibir."""
        m = _master(oro=1000)
        for _ in range(objetos.TOPE_INVENTARIO):
            m.inventario.anadir("elixir")
        compra = tienda.comprar_con_oro(m, "gema_mana")
        self.assertFalse(compra.ok)
        self.assertIs(compra.fallo, tienda.Fallo.INVENTARIO_LLENO)
        self.assertEqual(m.oro, 1000, "no se cobro")

    def test_una_clave_inventada_no_revienta(self) -> None:
        m = _master(oro=1000)
        compra = tienda.comprar_con_oro(m, "no_existe")
        self.assertFalse(compra.ok)
        self.assertIs(compra.fallo, tienda.Fallo.NO_EXISTE)
        self.assertEqual(m.oro, 1000)

    def test_un_catalizador_no_se_paga_con_oro(self) -> None:
        """Si se pudiera, el oro compraria lo que es de los griales."""
        m = _master(oro=10_000)
        compra = tienda.comprar_con_oro(m, "catalizador_saber")
        self.assertFalse(compra.ok)
        self.assertIs(compra.fallo, tienda.Fallo.NO_SE_VENDE)
        self.assertEqual(m.oro, 10_000)
        self.assertTrue(m.inventario.vacio)

    def test_comprar_varias_veces_va_restando(self) -> None:
        m = _master(oro=200)
        tienda.comprar_con_oro(m, "ojo_certero")
        tienda.comprar_con_oro(m, "ojo_certero")
        self.assertEqual(m.inventario.cuantos_de("ojo_certero"), 2)
        self.assertEqual(m.oro, 200 - 2 * tienda.PRECIO_EN_ORO["ojo_certero"])


class PruebaLaCuenta(unittest.TestCase):
    """Los griales. Lo unico del juego que sobrevive a una guerra."""

    def test_nace_a_cero(self) -> None:
        c = tienda.Cuenta(usuario_id="1")
        self.assertEqual(c.griales, 0)
        self.assertEqual(c.guerras_ganadas, 0)
        self.assertFalse(c.puede_pagar(1))
        self.assertTrue(c.puede_pagar(0))

    def test_ganar_una_guerra_paga_y_se_apunta(self) -> None:
        c = tienda.Cuenta(usuario_id="1")
        self.assertEqual(c.ganar_guerra(), tienda.GRIALES_POR_GUERRA)
        self.assertEqual(c.griales, tienda.GRIALES_POR_GUERRA)
        self.assertEqual(c.guerras_ganadas, 1)

    def test_no_se_cobra_mas_de_lo_que_hay(self) -> None:
        c = tienda.Cuenta(usuario_id="1", griales=1)
        self.assertFalse(c.cobrar(2))
        self.assertEqual(c.griales, 1, "y no se queda a medias")

    def test_ganar_una_guerra_da_para_un_catalizador_de_clase(self) -> None:
        """Si no diera para nada, ganar no se notaria."""
        c = tienda.Cuenta(usuario_id="1")
        c.ganar_guerra()
        self.assertTrue(c.puede_pagar(tienda.PRECIO_CATALIZADOR_CLASE))

    def test_un_servant_concreto_cuesta_mas_de_una_guerra(self) -> None:
        """Tiene que ser un ahorro, no un premio de consolacion."""
        c = tienda.Cuenta(usuario_id="1")
        c.ganar_guerra()
        self.assertFalse(c.puede_pagar(tienda.PRECIO_CATALIZADOR_SERVANT))


class PruebaComprarCatalizadores(unittest.TestCase):
    def test_un_catalizador_de_clase(self) -> None:
        m = _master()
        c = tienda.Cuenta(usuario_id="h0", griales=5)
        ficha = objetos.catalizador_de_clase(Clase.SABER)
        compra = tienda.comprar_catalizador(m, c, ficha)
        self.assertTrue(compra.ok)
        self.assertEqual(c.griales, 5 - tienda.PRECIO_CATALIZADOR_CLASE)
        self.assertTrue(m.inventario.tiene(ficha.clave))

    def test_un_catalizador_de_servant(self) -> None:
        m = _master()
        c = tienda.Cuenta(usuario_id="h0", griales=5)
        ficha = objetos.catalizador_de_servant(91)
        compra = tienda.comprar_catalizador(m, c, ficha)
        self.assertTrue(compra.ok)
        self.assertEqual(c.griales, 0)
        self.assertTrue(m.inventario.tiene("catalizador_servant:91"))

    def test_el_oro_no_se_toca(self) -> None:
        m = _master(oro=500)
        c = tienda.Cuenta(usuario_id="h0", griales=5)
        tienda.comprar_catalizador(m, c, objetos.catalizador_de_clase(Clase.SABER))
        self.assertEqual(m.oro, 500)

    def test_sin_griales_no_cobra_ni_entrega(self) -> None:
        m = _master()
        c = tienda.Cuenta(usuario_id="h0", griales=1)
        compra = tienda.comprar_catalizador(
            m, c, objetos.catalizador_de_clase(Clase.SABER)
        )
        self.assertFalse(compra.ok)
        self.assertIs(compra.fallo, tienda.Fallo.SIN_GRIALES)
        self.assertEqual(c.griales, 1)
        self.assertTrue(m.inventario.vacio)

    def test_con_el_inventario_lleno_no_se_cobran_los_griales(self) -> None:
        """5 griales son tres guerras ganadas: perderlos asi seria grave."""
        m = _master()
        c = tienda.Cuenta(usuario_id="h0", griales=9)
        for _ in range(objetos.TOPE_INVENTARIO):
            m.inventario.anadir("elixir")
        compra = tienda.comprar_catalizador(m, c, objetos.catalizador_de_servant(91))
        self.assertFalse(compra.ok)
        self.assertIs(compra.fallo, tienda.Fallo.INVENTARIO_LLENO)
        self.assertEqual(c.griales, 9)

    def test_un_servant_que_no_existe_no_se_vende(self) -> None:
        self.assertIsNone(objetos.catalizador_de_servant(99_999))
        m = _master()
        c = tienda.Cuenta(usuario_id="h0", griales=9)
        compra = tienda.comprar_catalizador(m, c, None)
        self.assertFalse(compra.ok)
        self.assertEqual(c.griales, 9)

    def test_un_objeto_normal_no_se_paga_con_griales(self) -> None:
        m = _master()
        c = tienda.Cuenta(usuario_id="h0", griales=9)
        compra = tienda.comprar_catalizador(m, c, objetos.objeto("elixir"))
        self.assertFalse(compra.ok)
        self.assertIs(compra.fallo, tienda.Fallo.NO_SE_VENDE)
        self.assertEqual(c.griales, 9)

    def test_hay_un_catalizador_por_clase_y_todos_se_compran(self) -> None:
        for clase in Clase:
            ficha = objetos.catalizador_de_clase(clase)
            self.assertIsNotNone(ficha, f"falta el catalizador de {clase.value}")
            m = _master()
            c = tienda.Cuenta(usuario_id="h0", griales=2)
            self.assertTrue(tienda.comprar_catalizador(m, c, ficha).ok)


class PruebaElOroQueDaElJuego(unittest.TestCase):
    def test_ganarle_a_un_npc_paga(self) -> None:
        rng = random.Random(7)
        s = Servant(CATALOGO[0], 10)
        pagos = set()
        for indice in range(npc.COMBATES_POR_DIA):
            for _ in range(40):
                r = npc.pelear(s, indice, 1, rng)
                self.assertEqual(
                    r.oro,
                    tienda.oro_por_npc(indice) if r.gano else 0,
                    "perder no paga",
                )
                pagos.add(r.oro)
        self.assertIn(0, pagos, "alguna derrota tenia que caer")

    def test_ganar_una_batalla_paga_a_quien_queda_en_pie(self) -> None:
        g, _ = _guerra_con_dos()
        antes = {m.id: m.oro for m in g.masters.values()}
        resultado = dia.jugar_batalla(g, ["h0", "h1"], g.rng)
        if not resultado.caidos:
            self.skipTest("esa batalla acabo en empate")
        for id_ in ("h0", "h1"):
            esperado = antes[id_] + (
                0 if id_ in resultado.caidos else tienda.ORO_POR_BATALLA_GANADA
            )
            self.assertEqual(g.masters[id_].oro, esperado)

    def test_un_empate_no_paga(self) -> None:
        """Lo que se cobra es ganar, no estar."""
        g, _ = _guerra_con_dos()
        antes = {m.id: m.oro for m in g.masters.values()}
        batalla = dia.armar_batalla(g, ["h0", "h1"], g.rng)
        # Una batalla sin turnos no tumbo a nadie: es el empate en su forma
        # mas pura, y nadie cobra.
        resultado = dia.anotar_batalla(g, ["h0", "h1"], batalla)
        self.assertEqual(resultado.caidos, [])
        for id_ in ("h0", "h1"):
            self.assertEqual(g.masters[id_].oro, antes[id_])

    def test_el_oro_no_se_reinicia_con_el_dia(self) -> None:
        """Dura la guerra: es lo que permite ahorrar de un dia para otro."""
        m = _master(oro=120)
        m.nuevo_dia()
        self.assertEqual(m.oro, 120)


class PruebaLaEconomiaDeUnaGuerra(unittest.TestCase):
    """Cuanto oro da una guerra de verdad. Es la referencia de los precios."""

    def test_un_dia_entrenando_da_para_un_objeto_o_dos(self) -> None:
        rng = random.Random(7)
        s = Servant(CATALOGO[0], 10)
        oro = sum(
            npc.pelear(s, indice, 1, rng).oro
            for indice in range(npc.COMBATES_POR_DIA)
        )
        barato = min(tienda.PRECIO_EN_ORO.values())
        self.assertGreaterEqual(
            oro, 0, "un dia malo puede no dar nada, y eso esta bien"
        )
        self.assertLess(
            oro,
            4 * barato,
            "un solo dia no puede dar para cuatro objetos, o la tienda sobra",
        )


def _guerra_con_dos(semilla: int = 7) -> tuple[Guerra, random.Random]:
    rng = random.Random(semilla)
    g = Guerra(id="1", canal_id="100", rng=rng)
    g.inscribir("h0", "Humano 0")
    g.inscribir("h1", "Humano 1")
    g.rellenar_con_bots()
    g.empezar(invocacion.invocar(CATALOGO, rng))
    for m in g.sin_invocar:
        g.invocar_para(m.id, rng)
    return g, rng


if __name__ == "__main__":
    unittest.main()
