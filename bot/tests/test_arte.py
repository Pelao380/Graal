"""La regla del arte oficial, puesta en una prueba.

Decidido en `docs/decisiones.md` (*El bot enlaza el arte, no lo sube*): el bot
manda la **URL** de Atlas Academy en un embed y la imagen la pide el cliente de
quien mira. Lo que no se hace nunca es **subir el archivo**, porque eso deja una
copia del arte en el CDN de Discord servida por nosotros.

Esa diferencia son dos lineas de codigo y es facil de cruzar sin darse cuenta,
asi que la regla no se queda en un documento que nadie relee: si alguien sube un
archivo, esto falla y le manda a cambiar la decision primero.

Esta prueba ya hizo su trabajo una vez. Prohibia tambien `set_image`, y cuando
hubo que ensenar el arte en la ficha, fallo y forzo la conversacion en lugar de
dejar que pasara de rebote. Al relajarla se escribio antes la decision nueva.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "src"
GENERADOS = RAIZ / "data" / "personajes_generados.json"
GITIGNORE = RAIZ.parent / ".gitignore"

# Subir un archivo: las formas que tiene discord.py de hacerlo, y el
# directorio de la copia local, que es de donde saldria el archivo.
SENALES = (
    "data/imagenes",
    "data\\imagenes",
    "discord.File",
    "discord.Attachment",
    "attachment://",
    "files=",
)

PORQUE = (
    "El bot enlaza el arte, no lo sube: ver 'El bot enlaza el arte, no lo "
    "sube' en docs/decisiones.md. Un embed con set_image(url=...) si vale; "
    "mandar el archivo, no. Si de verdad hay que cruzar esa linea, cambia "
    "primero la decision y luego esta prueba."
)


class PruebaElBotNoSubeArchivos(unittest.TestCase):
    def test_ningun_modulo_sube_una_imagen(self) -> None:
        culpables = []
        for ruta in sorted(FUENTES.rglob("*.py")):
            texto = ruta.read_text(encoding="utf-8")
            for senal in SENALES:
                if senal in texto:
                    culpables.append(f"{ruta.name}: {senal}")
        self.assertEqual(culpables, [], f"{culpables}\n\n{PORQUE}")

    def test_el_arte_se_manda_como_url_de_atlas_academy(self) -> None:
        """Lo que el bot pone en el embed es un enlace, y a donde esperamos."""
        from src.game.personajes import cargar
        from src.game.servant import Servant

        for personaje in cargar()[:40]:
            url = Servant(personaje=personaje, nivel=1).imagen
            self.assertTrue(
                url.startswith("https://static.atlasacademy.io/"),
                f"#{personaje.collection_no}: {url!r}",
            )

    def test_la_copia_local_no_va_al_repositorio(self) -> None:
        """La copia local es de cada uno: el repositorio lleva el script."""
        self.assertTrue(GITIGNORE.exists(), "falta el .gitignore")
        texto = GITIGNORE.read_text(encoding="utf-8")
        self.assertIn("bot/data/imagenes/", texto)


class PruebaLasUrlsSiguenEnElPlantel(unittest.TestCase):
    """Lo que se perdio el 2026-11-07 y nadie noto durante dos dias.

    `imagenes_de()` desaparecio del importador al reconstruirlo, el plantel
    salio sin URLs y `tools/descargar_imagenes.py` quedo sin nada que bajar:
    una herramienta que solo podia fallar. Esto lo habria dicho el mismo dia.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.fichas = json.loads(GENERADOS.read_text(encoding="utf-8"))["personajes"]

    def test_todas_las_fichas_traen_su_arte(self) -> None:
        sin_arte = [f["collectionNo"] for f in self.fichas if not f.get("imagenes")]
        self.assertEqual(
            sin_arte,
            [],
            "fichas sin URL de arte: reimporta con el export grande "
            "(python tools/importar_servants.py)",
        )

    def test_no_hay_nadie_sin_cupo_en_la_coleccion(self) -> None:
        """El `collectionNo` 0 no se invoca, asi que no entra al plantel.

        Es el caso de Hyde, la forma Berserker de Jekyll, que ya esta con el
        numero 81: tenerlo era tenerlo dos veces y sus cuatro URLs daban 404.
        Si el export vuelve a traer una forma asi, esto lo dice.
        """
        sin_cupo = [f["nombre"] for f in self.fichas if f["collectionNo"] == 0]
        self.assertEqual(sin_cupo, [])

    def test_las_urls_son_del_sitio_que_esperamos(self) -> None:
        """Una URL de otro sitio seria un dato raro, no una mejora."""
        for f in self.fichas:
            for ascension, url in (f.get("imagenes") or {}).items():
                self.assertIn(ascension, ("1", "2", "3", "4"))
                self.assertTrue(
                    url.startswith("https://static.atlasacademy.io/"),
                    f"#{f['collectionNo']} ascension {ascension}: {url}",
                )


class PruebaLaAscensionPorNivel(unittest.TestCase):
    """Las cuatro ascensiones repartidas por nivel: 1-4, 5-9, 10-14 y 15."""

    def _servant(self, nivel: int):
        from src.game.clases import Clase
        from src.game.personajes import Personaje
        from src.game.servant import Servant

        return Servant(personaje=Personaje(nombre="X", clase=Clase.SABER), nivel=nivel)

    def test_la_tabla_entera(self) -> None:
        esperado = {
            1: "1", 2: "1", 3: "1", 4: "1",
            5: "2", 6: "2", 7: "2", 8: "2", 9: "2",
            10: "3", 11: "3", 12: "3", 13: "3", 14: "3",
            15: "4",
        }
        for nivel, ascension in esperado.items():
            self.assertEqual(self._servant(nivel).ascension, ascension, f"nivel {nivel}")

    def test_cambia_justo_cuando_se_desbloquea_una_habilidad(self) -> None:
        """No es coincidencia: las bandas salen de `NIVELES_HABILIDAD`.

        Si alguien mueve los niveles de habilidad, el arte se mueve con ellos.
        Esta prueba es la que lo dice en voz alta.
        """
        from src.game.servant import NIVELES_HABILIDAD

        for nivel in NIVELES_HABILIDAD:
            antes = self._servant(nivel - 1).ascension
            despues = self._servant(nivel).ascension
            self.assertEqual(int(despues), int(antes) + 1, f"nivel {nivel}")

    def test_nunca_se_pasa_de_la_cuarta(self) -> None:
        """Hay 4 artes y el nivel maximo es 15: no puede pedir una quinta."""
        from src.game.servant import NIVEL_MAXIMO

        self.assertEqual(self._servant(NIVEL_MAXIMO).ascension, "4")
        # Por si algun dia sube el tope de nivel sin que nadie mire aqui.
        self.assertLessEqual(int(self._servant(NIVEL_MAXIMO + 20).ascension), 4)

    def test_la_ascension_que_pide_existe_para_todo_el_plantel(self) -> None:
        """Lo que une las dos mitades: el numero existe como URL."""
        from src.game.personajes import cargar
        from src.game.servant import NIVEL_MAXIMO, Servant

        fichas = json.loads(GENERADOS.read_text(encoding="utf-8"))["personajes"]
        por_no = {f["collectionNo"]: f for f in fichas}
        for personaje in cargar():
            ficha = por_no.get(personaje.collection_no)
            if ficha is None:
                continue
            for nivel in (1, 5, 10, NIVEL_MAXIMO):
                pedida = Servant(personaje=personaje, nivel=nivel).ascension
                self.assertIn(
                    pedida,
                    ficha["imagenes"],
                    f"#{personaje.collection_no} nivel {nivel}",
                )


if __name__ == "__main__":
    unittest.main()
