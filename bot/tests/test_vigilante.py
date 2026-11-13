"""Pruebas del plazo del dia y del vigilante que lo mira.

El reloj de la guerra se cambia por uno de mentira, asi que las 24 horas de
preparacion pasan en una linea.
"""

from __future__ import annotations

import asyncio
import random
import unittest

from src.game import dia, invocacion, personajes
from src.game.war import TIEMPOS_PREPARACION, Fase, Guerra

try:
    import discord  # noqa: F401

    HAY_DISCORD = True
except ModuleNotFoundError:  # pragma: no cover
    HAY_DISCORD = False

CATALOGO = personajes.cargar()


class Reloj:
    """Un reloj que solo avanza cuando se le dice."""

    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora

    def avanzar(self, segundos: float) -> None:
        self.ahora += segundos


def _guerra(preparacion: str = "1h", humanos: int = 1) -> tuple[Guerra, Reloj]:
    rng = random.Random(3)
    reloj = Reloj()
    g = Guerra(
        id="1",
        canal_id="100",
        preparacion=preparacion,
        rng=rng,
        reloj=reloj,
    )
    for i in range(humanos):
        g.inscribir(f"h{i}", f"Humano {i}")
    g.rellenar_con_bots()
    g.empezar(invocacion.invocar(CATALOGO, rng))
    return g, reloj


class PruebaPlazoDelDia(unittest.TestCase):
    def test_empezar_abre_el_plazo(self) -> None:
        g, reloj = _guerra("1h")
        self.assertEqual(g.vence_preparacion, reloj.ahora + 60 * 60)
        self.assertFalse(g.plazo_cumplido)

    def test_el_plazo_sale_de_la_ventana_elegida(self) -> None:
        for nombre, segundos in TIEMPOS_PREPARACION.items():
            g, reloj = _guerra(nombre)
            self.assertEqual(g.vence_preparacion, reloj.ahora + segundos)

    def test_el_plazo_vence(self) -> None:
        g, reloj = _guerra("30m")
        reloj.avanzar(30 * 60 - 1)
        self.assertFalse(g.plazo_cumplido)
        reloj.avanzar(1)
        self.assertTrue(g.plazo_cumplido)

    def test_lo_que_queda_no_baja_de_cero(self) -> None:
        g, reloj = _guerra("30m")
        reloj.avanzar(10 * 60)
        self.assertAlmostEqual(g.segundos_para_cerrar, 20 * 60)
        reloj.avanzar(60 * 60)
        self.assertEqual(g.segundos_para_cerrar, 0)

    def test_cada_dia_nuevo_trae_plazo_nuevo(self) -> None:
        g, reloj = _guerra("30m")
        reloj.avanzar(31 * 60)
        self.assertTrue(g.plazo_cumplido)
        dia.cerrar_dia(g)
        # `siguiente_dia` abre el dia, y abrir el dia pone el plazo.
        self.assertFalse(g.plazo_cumplido)
        self.assertEqual(g.vence_preparacion, reloj.ahora + 30 * 60)

    def test_una_guerra_terminada_no_tiene_plazo_pendiente(self) -> None:
        g, reloj = _guerra("30m")
        for m in list(g.masters.values())[1:]:
            m.derrotas = 99
        g.fase = Fase.TERMINADA
        reloj.avanzar(60 * 60)
        self.assertFalse(g.plazo_cumplido)

    def test_el_plazo_no_cuenta_fuera_de_preparacion(self) -> None:
        g, reloj = _guerra("30m")
        g.fase = Fase.BATALLA
        reloj.avanzar(60 * 60)
        self.assertFalse(g.plazo_cumplido)


class CogDeMentira:
    """Lo minimo que el vigilante mira del Cog."""

    def __init__(self, guerras: dict[int, Guerra]) -> None:
        self.guerras = guerras
        self.bot = self
        self.canales: dict[int, list[str]] = {}
        self.cerradas: list[str] = []
        # Las batallas en curso. Vacio es "aqui no se juega a mano", que es lo
        # que hacen falta estas pruebas: las del menu de combate van aparte.
        self.combates: dict[str, object] = {}
        self.rng = random.Random(3)

    # --- lo que el vigilante usa ---

    def get_channel(self, id_: int):
        return self.canales.setdefault(id_, [])

    def textos_del_cierre(self, guerra: Guerra, por_plazo: bool = False):
        self.cerradas.append(f"{guerra.id}:{guerra.dia}:plazo={por_plazo}")
        dia.cerrar_dia(guerra)
        return ["cierre"]

    def aviso_del_menu(self, guerra: Guerra) -> str:
        return "aviso"

    def vista_del_menu(self, guerra: Guerra) -> None:
        return None

    def aviso_y_vista_de_despues(self, guerra: Guerra):
        # Una vista que no sea `None` es lo que hace que el aviso se mande;
        # aqui da igual cual sea, porque el canal de mentira la ignora.
        if guerra.terminada:
            return None, None
        return "aviso", object()

    def guardar(self, guerra: Guerra) -> None:
        pass

    # --- la puerta compartida, prestada de la de verdad ---
    #
    # `cerrar_el_dia` es por donde pasan las cuatro formas de cerrar un dia, y
    # el vigilante es una de ellas. Se toma **tal cual** del Cog de verdad en
    # vez de copiarla aqui: si se copiara, estas pruebas pasarian con una
    # version propia y el vigilante de verdad podria dejar otra mesa, que es
    # justo el fallo que la puerta compartida existe para evitar.
    if HAY_DISCORD:
        from src.commands import ComandosGuerra as _DeVerdad

        cerrar_el_dia = _DeVerdad.cerrar_el_dia
        enviar_por_el_canal = _DeVerdad.enviar_por_el_canal
        del _DeVerdad


class Canal(list):
    async def send(self, texto: str = "", *, view: object = None) -> None:
        self.append(texto)


class CogConCanal(CogDeMentira):
    def get_channel(self, id_: int):
        return self.canales.setdefault(id_, Canal())


@unittest.skipUnless(HAY_DISCORD, "discord.py no esta instalado")
class PruebaVigilante(unittest.TestCase):
    def _vigilante(self, cog):
        from src.vigilante import Vigilante

        return Vigilante(cog)

    def test_no_cierra_nada_antes_del_plazo(self) -> None:
        g, _ = _guerra("1h")
        cog = CogConCanal({100: g})
        v = self._vigilante(cog)
        self.assertEqual(v.vencidas(), [])
        asyncio.run(v.revisar())
        self.assertEqual(cog.cerradas, [])
        self.assertEqual(g.dia, 1)

    def test_cierra_el_dia_cuando_vence(self) -> None:
        g, reloj = _guerra("1h")
        cog = CogConCanal({100: g})
        v = self._vigilante(cog)
        reloj.avanzar(60 * 60 + 1)
        self.assertEqual(v.vencidas(), [g])
        asyncio.run(v.revisar())
        self.assertEqual(cog.cerradas, ["1:1:plazo=True"])
        self.assertEqual(g.dia, 2)
        # Lo conto en el canal, y dejo el aviso del menu del dia nuevo.
        self.assertEqual(cog.canales[100], ["cierre", "aviso"])

    def test_el_plazo_no_espera_a_que_nadie_este_listo(self) -> None:
        """Es la diferencia con el boton del creador, y es a proposito."""
        g, reloj = _guerra("1h", humanos=2)
        self.assertTrue(g.faltan_por_estar_listos)
        cog = CogConCanal({100: g})
        reloj.avanzar(60 * 60 + 1)
        asyncio.run(self._vigilante(cog).revisar())
        self.assertEqual(g.dia, 2)

    def test_sin_canal_no_cierra_el_dia(self) -> None:
        """Cerrarlo sin poder contarlo seria peor: nadie sabria que paso."""
        g, reloj = _guerra("1h")
        cog = CogConCanal({100: g})
        cog.get_channel = lambda id_: None
        reloj.avanzar(60 * 60 + 1)
        # Se queja por el registro, y el `assertLogs` lo comprueba y lo calla.
        with self.assertLogs("src.vigilante", level="WARNING"):
            asyncio.run(self._vigilante(cog).revisar())
        self.assertEqual(g.dia, 1)

    def test_un_error_en_una_guerra_no_para_las_demas(self) -> None:
        buena, reloj = _guerra("1h")
        mala, _ = _guerra("1h")
        mala.id = "mala"
        mala.reloj = reloj
        mala.vence_preparacion = 0.0  # ya vencida
        cog = CogConCanal({100: buena, 200: mala})
        mala.canal_id = "200"
        original = cog.textos_del_cierre

        def falla(guerra, por_plazo=False):
            if guerra.id == "mala":
                raise RuntimeError("algo se rompio")
            return original(guerra, por_plazo)

        cog.textos_del_cierre = falla
        reloj.avanzar(60 * 60 + 1)
        with self.assertLogs("src.vigilante", level="ERROR"):
            asyncio.run(self._vigilante(cog).revisar())
        self.assertEqual(buena.dia, 2, "la buena se cerro igual")
        self.assertEqual(mala.dia, 1)

    def test_varios_dias_seguidos(self) -> None:
        g, reloj = _guerra("30m")
        cog = CogConCanal({100: g})
        v = self._vigilante(cog)
        for _ in range(3):
            if g.terminada:
                break
            reloj.avanzar(31 * 60)
            asyncio.run(v.revisar())
        self.assertGreaterEqual(g.dia, 3)


if __name__ == "__main__":
    unittest.main()
