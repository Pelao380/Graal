"""Los objetos y el inventario, sin Discord y sin red.

Lo que se prueba aqui es que un objeto no puede inventar una regla (la lista
de efectos es cerrada y se valida al cargar), que el inventario no pierde ni
duplica nada, y que el tope por batalla es de verdad un tope.
"""

from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path

from src.game import objetos
from src.game.clases import Clase
from src.game.objetos import (
    OBJETOS_POR_BATALLA,
    TOPE_INVENTARIO,
    VALOR_POR_EFECTO_DE_OBJETO,
    EfectoFuera,
    Inventario,
    Momento,
    Objeto,
    cargar,
    objeto,
    objeto_desde,
    sortear,
    sueltos,
)
from src.game.personajes import Efecto, VALOR_POR_EFECTO


class PruebaElCatalogo(unittest.TestCase):
    def test_el_catalogo_carga_y_se_valida(self) -> None:
        catalogo = cargar()
        self.assertTrue(catalogo, "el catalogo no puede estar vacio")
        for o in catalogo:
            o.validar()

    def test_las_claves_son_unicas(self) -> None:
        """La clave es el identificador, como el collectionNo de un personaje."""
        claves = [o.clave for o in cargar()]
        self.assertEqual(len(claves), len(set(claves)))

    def test_hay_un_objeto_por_cada_efecto_de_combate(self) -> None:
        """Si falta uno, hay un efecto de objeto que ningun objeto usa."""
        efectos = {
            o.efecto for o in cargar() if o.momento is Momento.COMBATE
        }
        self.assertEqual(efectos, set(VALOR_POR_EFECTO_DE_OBJETO))

    def test_un_objeto_no_puede_esquivar_ni_debilitar(self) -> None:
        """Los cuatro efectos nuevos no son de objeto, y es una decision.

        Un objeto no cuesta el turno. Esquivar un golpe, no caerte o bajarle
        la defensa al rival son justo los efectos que peor aguantan ser
        gratis, asi que `VALOR_POR_EFECTO_DE_OBJETO` no los tiene y un objeto
        que los traiga no entra. Si alguna vez se quieren, se cambia aqui y se
        mide, no al contrario.
        """
        fuera = {
            Efecto.EVASION,
            Efecto.AGUANTAR,
            Efecto.BAJAR_ATAQUE,
            Efecto.BAJAR_DEFENSA,
        }
        self.assertEqual(fuera & set(VALOR_POR_EFECTO_DE_OBJETO), set())
        self.assertTrue(
            fuera <= set(VALOR_POR_EFECTO),
            "pero si son efectos de habilidad",
        )

    def test_hay_un_objeto_por_cada_efecto_de_fuera(self) -> None:
        efectos = {
            o.efecto_fuera for o in cargar() if o.momento is Momento.PREPARACION
        }
        self.assertEqual(efectos, set(EfectoFuera))

    def test_hay_un_catalizador_por_clase(self) -> None:
        clases = {
            o.clase for o in cargar() if o.momento is Momento.INVOCACION
        }
        self.assertEqual(clases, set(Clase))

    def test_todas_las_claves_tienen_nombre_y_descripcion(self) -> None:
        """Si falta un texto, `t()` revienta: mejor que reviente aqui."""
        for o in cargar():
            for idioma in ("es", "en"):
                self.assertTrue(o.nombre_para(idioma))
                self.assertTrue(o.descripcion(idioma))

    def test_un_objeto_de_combate_da_menos_que_la_habilidad(self) -> None:
        """La razon de que los objetos tengan sus propios numeros.

        Una habilidad gasta el turno y por eso da mucho; un objeto no gasta
        nada. Con los mismos numeros, un objeto seria una habilidad gratis, o
        sea estrictamente mejor que cualquier habilidad. La unica excepcion a
        mano es curar, que esta explicada en `objetos.py`.
        """
        for o in cargar():
            if o.momento is not Momento.COMBATE or o.efecto is Efecto.CURAR:
                continue
            self.assertLess(
                o.valor,
                VALOR_POR_EFECTO[o.efecto],
                f"{o.clave} da igual o mas que la habilidad del mismo efecto",
            )


class PruebaLaValidacion(unittest.TestCase):
    """Un objeto que no cuadra no entra, igual que un personaje."""

    def test_un_objeto_tiene_que_hacer_una_sola_cosa(self) -> None:
        with self.assertRaises(ValueError):
            Objeto(
                clave="roto",
                momento=Momento.COMBATE,
                efecto=Efecto.ATAQUE,
                efecto_fuera=EfectoFuera.XP,
            ).validar()

    def test_un_objeto_tiene_que_hacer_algo(self) -> None:
        with self.assertRaises(ValueError):
            Objeto(clave="vacio", momento=Momento.COMBATE).validar()

    def test_el_efecto_tiene_que_valer_para_su_momento(self) -> None:
        """Un efecto de combate en un objeto de preparacion no vale."""
        with self.assertRaises(ValueError):
            Objeto(
                clave="confundido",
                momento=Momento.PREPARACION,
                efecto=Efecto.ATAQUE,
            ).validar()

    def test_ninguno_no_vale_para_un_objeto(self) -> None:
        """NINGUNO es para una habilidad de FGO que no supimos traducir."""
        with self.assertRaises(ValueError):
            Objeto(
                clave="nada", momento=Momento.COMBATE, efecto=Efecto.NINGUNO
            ).validar()

    def test_una_clave_repetida_no_carga(self) -> None:
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "objetos.json"
            ruta.write_text(
                json.dumps(
                    {
                        "objetos": [
                            {"clave": "x", "momento": "combate", "efecto": "ataque"},
                            {"clave": "x", "momento": "combate", "efecto": "mana"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                cargar(ruta)

    def test_sin_catalogo_no_revienta(self) -> None:
        self.assertEqual(cargar(Path("no_existe_este_archivo.json")), [])

    def test_el_valor_sale_del_juego_y_no_del_catalogo(self) -> None:
        """Un objeto nuevo no puede traer un numero roto: no trae numeros."""
        o = objeto_desde(
            {"clave": "x", "momento": "combate", "efecto": "ataque", "valor": 99}
        )
        self.assertNotEqual(o.valor, 99)


class PruebaLasSueltas(unittest.TestCase):
    def test_los_catalizadores_no_se_sueltan(self) -> None:
        """Apuntan la invocacion, que es del dia 1: llegarian tarde."""
        self.assertFalse(
            [o for o in sueltos() if o.momento is Momento.INVOCACION]
        )

    def test_sortear_siempre_da_algo_que_se_suelta(self) -> None:
        rng = random.Random(7)
        posibles = {o.clave for o in sueltos()}
        for _ in range(200):
            self.assertIn(sortear(rng).clave, posibles)

    def test_el_peso_manda(self) -> None:
        """Un objeto con peso 0 no sale nunca, y por eso los catalizadores."""
        rng = random.Random(7)
        salidos = {sortear(rng).clave for _ in range(400)}
        for o in sueltos():
            if o.peso == 0:
                self.assertNotIn(o.clave, salidos)

    def test_sortear_un_momento_da_solo_de_ese_momento(self) -> None:
        rng = random.Random(3)
        for _ in range(50):
            self.assertIs(sortear(rng, Momento.PREPARACION).momento, Momento.PREPARACION)


class PruebaElInventario(unittest.TestCase):
    def test_nace_vacio(self) -> None:
        inv = Inventario()
        self.assertTrue(inv.vacio)
        self.assertEqual(inv.total, 0)
        self.assertEqual(inv.lista(), [])

    def test_anadir_y_quitar(self) -> None:
        inv = Inventario()
        self.assertTrue(inv.anadir("elixir"))
        self.assertTrue(inv.anadir("elixir"))
        self.assertEqual(inv.cuantos_de("elixir"), 2)
        self.assertTrue(inv.quitar("elixir"))
        self.assertEqual(inv.cuantos_de("elixir"), 1)
        self.assertTrue(inv.quitar("elixir"))
        self.assertFalse(inv.tiene("elixir"))

    def test_al_quedarse_a_cero_la_clave_desaparece(self) -> None:
        """Para que la base de datos no arrastre objetos que no se tienen."""
        inv = Inventario()
        inv.anadir("elixir")
        inv.quitar("elixir")
        self.assertEqual(inv.cuantos, {})

    def test_no_se_quita_lo_que_no_se_tiene(self) -> None:
        inv = Inventario()
        self.assertFalse(inv.quitar("elixir"))
        inv.anadir("elixir")
        self.assertFalse(inv.quitar("elixir", 2), "ni de mas")
        self.assertEqual(inv.cuantos_de("elixir"), 1)

    def test_el_tope_no_se_pasa_y_no_revienta(self) -> None:
        """Una suelta con el inventario lleno no puede romperle el dia a nadie."""
        inv = Inventario()
        for _ in range(TOPE_INVENTARIO):
            self.assertTrue(inv.anadir("elixir"))
        self.assertTrue(inv.lleno)
        self.assertFalse(inv.anadir("gema_mana"))
        self.assertEqual(inv.total, TOPE_INVENTARIO)

    def test_la_lista_se_salta_lo_que_ya_no_esta_en_el_catalogo(self) -> None:
        """El catalogo puede cambiar; un inventario guardado no lo sabe."""
        inv = Inventario(cuantos={"elixir": 1, "objeto_que_ya_no_existe": 3})
        claves = [o.clave for o, _ in inv.lista()]
        self.assertEqual(claves, ["elixir"])
        self.assertEqual(inv.total, 4, "el total cuenta lo que lleva, no lo que ve")

    def test_la_lista_filtra_por_momento(self) -> None:
        inv = Inventario(cuantos={"elixir": 1, "vendaje": 1, "catalizador_saber": 1})
        self.assertEqual(
            [o.clave for o, _ in inv.lista(Momento.COMBATE)], ["elixir"]
        )
        self.assertEqual(
            [o.clave for o, _ in inv.lista(Momento.PREPARACION)], ["vendaje"]
        )
        self.assertEqual(
            [o.clave for o, _ in inv.lista(Momento.INVOCACION)],
            ["catalizador_saber"],
        )

    def test_la_lista_va_en_orden_estable(self) -> None:
        """El menu no puede cambiar de orden entre dos aperturas."""
        inv = Inventario(cuantos={"gema_mana": 1, "elixir": 1, "piedra_furia": 1})
        una = [o.clave for o, _ in inv.lista()]
        otra = [o.clave for o, _ in Inventario(cuantos=dict(inv.cuantos)).lista()]
        self.assertEqual(una, otra)
        self.assertEqual(una, sorted(una))

    def test_el_tope_por_batalla(self) -> None:
        inv = Inventario()
        self.assertTrue(inv.puede_usar_en_la_batalla)
        inv.usados_en_la_batalla = OBJETOS_POR_BATALLA
        self.assertFalse(inv.puede_usar_en_la_batalla)

    def test_la_batalla_nueva_devuelve_el_uso_pero_no_los_objetos(self) -> None:
        """Los objetos duran la guerra; el tope es por batalla."""
        inv = Inventario(cuantos={"elixir": 2}, usados_en_la_batalla=1)
        inv.nueva_batalla()
        self.assertTrue(inv.puede_usar_en_la_batalla)
        self.assertEqual(inv.cuantos_de("elixir"), 2, "no se pierden con el dia")


class PruebaLosCatalizadoresDeServant(unittest.TestCase):
    """Las unicas fichas que no estan en el catalogo: son 348 y se arman.

    Lo que tiene que aguantar es el viaje entero: se arma, se guarda la clave
    en el inventario, se lee de vuelta y sigue siendo la misma ficha. Si
    `objeto()` no reconociera la forma de la clave, un catalizador comprado por
    5 griales desapareceria del inventario al recargar la guerra.
    """

    def test_se_arma_por_numero_de_coleccion(self) -> None:
        o = objetos.catalizador_de_servant(91)
        self.assertIsNotNone(o)
        self.assertIs(o.momento, Momento.INVOCACION)
        self.assertEqual(o.collection_no, 91)
        self.assertTrue(o.es_catalizador_de_servant)
        o.validar()

    def test_la_clave_lleva_el_numero_y_no_el_nombre(self) -> None:
        """Los nombres no son unicos y se traducen; el numero si es unico."""
        self.assertEqual(
            objetos.catalizador_de_servant(91).clave, "catalizador_servant:91"
        )

    def test_la_clave_vuelve_a_ser_la_misma_ficha(self) -> None:
        o = objetos.catalizador_de_servant(91)
        self.assertEqual(objetos.objeto(o.clave), o)

    def test_un_numero_que_no_esta_en_el_plantel_no_existe(self) -> None:
        """Comprarlo serian 5 griales, o sea tres guerras ganadas, por nada."""
        self.assertIsNone(objetos.catalizador_de_servant(99_999))
        self.assertIsNone(objetos.objeto("catalizador_servant:99999"))

    def test_una_clave_con_forma_rara_no_revienta(self) -> None:
        for mala in (
            "catalizador_servant:",
            "catalizador_servant:abc",
            "catalizador_servant",
            "catalizador_servant:1.5",
            "catalizador_servant:-3",
        ):
            self.assertIsNone(objetos.objeto(mala), mala)

    def test_el_nombre_trae_al_servant(self) -> None:
        o = objetos.catalizador_de_servant(91)
        for idioma in ("es", "en"):
            self.assertIn("Ryougi Shiki", o.nombre_para(idioma))
            self.assertIn("Ryougi Shiki", o.descripcion(idioma))

    def test_no_se_sueltan_entrenando(self) -> None:
        """Se compran con griales; si se soltaran, los griales no valdrian."""
        self.assertEqual(objetos.catalizador_de_servant(91).peso, 0)
        self.assertFalse(
            [o for o in objetos.sueltos() if o.momento is Momento.INVOCACION]
        )

    def test_en_el_inventario_se_ve_y_se_cuenta(self) -> None:
        inv = Inventario()
        inv.anadir("catalizador_servant:91")
        inv.anadir("catalizador_saber")
        claves = [o.clave for o, _ in inv.lista(Momento.INVOCACION)]
        self.assertEqual(
            sorted(claves), ["catalizador_saber", "catalizador_servant:91"]
        )
        self.assertEqual(inv.total, 2)

    def test_uno_por_cada_personaje_del_plantel(self) -> None:
        """Se pueden pedir los 348, no una lista corta de favoritos."""
        from src.game import personajes

        plantel = personajes.cargar()
        self.assertGreater(len(plantel), 300)
        for p in plantel:
            o = objetos.catalizador_de_servant(p.collection_no)
            self.assertIsNotNone(o, p.nombre)
            self.assertEqual(objetos.objeto(o.clave), o)


class PruebaLosNombresLegibles(unittest.TestCase):
    def test_el_valor_se_ensena_en_porcentaje_cuando_toca(self) -> None:
        """Un 0.2 en la descripcion no le dice nada a nadie."""
        self.assertIn("20", objeto("elixir").descripcion("es"))
        self.assertIn("40", objeto("gema_mana").descripcion("es"), "el mana va suelto")


if __name__ == "__main__":
    unittest.main()
