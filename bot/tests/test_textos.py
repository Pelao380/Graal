"""Pruebas del catalogo de textos y del idioma.

Lo que se protege aqui:

- Ninguna traduccion a medias: si una clave le falta a un idioma, o sus huecos
  no cuadran, el catalogo revienta al cargar y no en medio de una batalla.
- El mismo combate se narra igual en los dos idiomas: el idioma solo cambia
  las frases, nunca lo que pasa.
"""

from __future__ import annotations

import json
import random
import tempfile
import unittest
from pathlib import Path

from src.game import ai, personajes
from src.game.battle import Accion, Batalla, Combatiente, Decision
from src.game.clases import Clase
from src.game.npc import pelear
from src.game.personajes import (
    SIN_HABILIDADES,
    Efecto,
    Habilidad,
    Objetivo,
    Personaje,
)
from src.game.servant import Servant
from src.game.textos import (
    IDIOMA_POR_DEFECTO,
    IDIOMAS,
    RUTA_TEXTOS,
    TEXTOS,
    _cargar,
    idioma_valido,
    plural,
    t,
    turnos,
)
from src.game.war import Guerra


def _personaje(nombre: str, *habilidades: Habilidad) -> Personaje:
    llenas = list(habilidades) + list(SIN_HABILIDADES)
    return Personaje(
        nombre=nombre, clase=Clase.RIDER, habilidades=tuple(llenas[:3])
    )


def _batalla(idioma: str, rng: random.Random) -> Batalla:
    p = _personaje(
        "A",
        Habilidad(
            nombre="Carisma", efecto=Efecto.ATAQUE, objetivo=Objetivo.ALIADO
        ),
    )
    q = _personaje("B")
    return Batalla(
        [
            Combatiente(id="a", nombre="A", servant=Servant(p, 15)),
            Combatiente(id="b", nombre="B", servant=Servant(q, 15)),
        ],
        rng=rng,
        idioma=idioma,
    )


class PruebaCatalogo(unittest.TestCase):
    def test_el_catalogo_trae_los_dos_idiomas(self) -> None:
        self.assertEqual(IDIOMAS, ("es", "en"))
        self.assertGreater(len(TEXTOS), 50)

    def test_ninguna_clave_se_queda_sin_traducir(self) -> None:
        for clave, frases in TEXTOS.items():
            for idioma in IDIOMAS:
                self.assertTrue(frases.get(idioma), f"{clave} en {idioma}")

    def test_el_json_del_repositorio_carga(self) -> None:
        """La validacion corre sobre el archivo de verdad, no sobre un fijo."""
        textos, idiomas = _cargar(RUTA_TEXTOS)
        self.assertEqual(idiomas, IDIOMAS)
        self.assertEqual(len(textos), len(TEXTOS))

    def test_una_traduccion_a_medias_no_carga(self) -> None:
        with self._catalogo({"saludo": {"es": "hola"}}) as ruta:
            with self.assertRaises(ValueError):
                _cargar(ruta)

    def test_un_hueco_que_no_cuadra_no_carga(self) -> None:
        with self._catalogo(
            {"saludo": {"es": "hola {nombre}", "en": "hello {name}"}}
        ) as ruta:
            with self.assertRaises(ValueError):
                _cargar(ruta)

    def test_un_catalogo_correcto_si_carga(self) -> None:
        with self._catalogo(
            {"saludo": {"es": "hola {nombre}", "en": "hello {nombre}"}}
        ) as ruta:
            textos, _ = _cargar(ruta)
            self.assertEqual(textos["saludo"]["en"], "hello {nombre}")

    def _catalogo(self, textos: dict):
        import contextlib

        @contextlib.contextmanager
        def escribir():
            with tempfile.TemporaryDirectory() as carpeta:
                ruta = Path(carpeta) / "textos.json"
                ruta.write_text(
                    json.dumps({"_idiomas": ["es", "en"], "textos": textos}),
                    encoding="utf-8",
                )
                yield ruta

        return escribir()

    def test_un_texto_que_no_existe_avisa(self) -> None:
        with self.assertRaises(KeyError):
            t("no.existe", "es")

    def test_un_dato_que_falta_avisa(self) -> None:
        with self.assertRaises(KeyError):
            t("batalla.cae", "es")  # le falta nombre

    def test_el_idioma_de_discord_se_normaliza(self) -> None:
        self.assertEqual(idioma_valido("en-GB"), "en")
        self.assertEqual(idioma_valido("es_ES"), "es")
        # Uno que no tenemos cae al por defecto en vez de reventar.
        self.assertEqual(idioma_valido("fr"), IDIOMA_POR_DEFECTO)
        self.assertEqual(idioma_valido(None), IDIOMA_POR_DEFECTO)

    def test_el_idioma_por_defecto_es_el_ingles(self) -> None:
        """Es el que entiende mas gente; el espanol es una traduccion mas."""
        self.assertEqual(IDIOMA_POR_DEFECTO, "en")
        self.assertEqual(t("batalla.critico"), "Critical hit.")

    def test_los_plurales(self) -> None:
        self.assertEqual(turnos(1, "es"), "1 turno")
        self.assertEqual(turnos(3, "es"), "3 turnos")
        self.assertEqual(turnos(1, "en"), "1 turn")
        self.assertEqual(turnos(3, "en"), "3 turns")

    def test_ninguna_frase_dice_persona_s(self) -> None:
        """Nada de "1 persona(s)": hay singular y plural de verdad."""
        self.assertEqual(plural("personas", 1, "es"), "1 persona")
        self.assertEqual(plural("personas", 4, "es"), "4 personas")
        self.assertEqual(plural("personas", 1, "en"), "1 person")
        self.assertEqual(plural("personas", 4, "en"), "4 people")
        self.assertEqual(plural("bots", 1, "en"), "1 AI Master")
        self.assertEqual(plural("bots", 6, "es"), "6 Masters de la IA")
        for frases in TEXTOS.values():
            for frase in frases.values():
                self.assertNotIn("(s)", frase)


class PruebaRegistroEnDosIdiomas(unittest.TestCase):
    def test_el_registro_sale_en_ingles(self) -> None:
        batalla = _batalla("en", random.Random(1))
        eventos = batalla.resolver_turno(
            {
                "a": Decision(Accion.HABILIDAD, "a", 1),
                "b": Decision(Accion.ATACAR, "a"),
            }
        )
        junto = " ".join(eventos)
        self.assertIn("Turn 1", junto)
        self.assertIn("uses Carisma", junto)
        self.assertNotIn("Turno", junto)

    def test_el_mismo_combate_pasa_igual_en_los_dos_idiomas(self) -> None:
        """El idioma escribe, no decide."""
        resultados = {}
        for idioma in IDIOMAS:
            batalla = _batalla(idioma, random.Random(7))
            rng = random.Random(7)
            while not batalla.terminada and batalla.turno < 40:
                if batalla.estado.value == "votacion":
                    batalla.registrar_votos(
                        {c.id: ai.votar_continuar(batalla, c) for c in batalla.vivos}
                    )
                    continue
                batalla.resolver_turno(
                    {c.id: ai.decidir(batalla, c, rng) for c in batalla.vivos}
                )
            ganador = batalla.ganador()
            resultados[idioma] = (
                batalla.turno,
                ganador.id if ganador else None,
                [c.vida for c in batalla.combatientes.values()],
            )
        self.assertEqual(resultados["es"], resultados["en"])

    def test_la_ficha_de_una_habilidad_se_traduce(self) -> None:
        hab = Habilidad(
            nombre="Carisma", efecto=Efecto.ATAQUE, objetivo=Objetivo.ALIADO
        )
        self.assertIn("enfriamiento", hab.descripcion("es"))
        self.assertIn("cooldown", hab.descripcion("en"))
        self.assertIn("hits for", hab.descripcion("en"))

    def test_la_sombra_del_entrenamiento_se_traduce(self) -> None:
        p = next(x for x in personajes.cargar() if x.clase is Clase.RIDER)
        resultado = pelear(
            Servant(p, 1), 0, 1, random.Random(3), idioma="en"
        )
        self.assertEqual(resultado.rival, "Shadow 1")
        self.assertIn("Turn 1", resultado.registro[0])


class PruebaFichaEnDosIdiomas(unittest.TestCase):
    def setUp(self) -> None:
        self.catalogo = personajes.cargar()
        self.altria = next(p for p in self.catalogo if p.collection_no == 2)

    def test_renombrar_al_espanol_guarda_el_nombre_en_ingles(self) -> None:
        """El nombre que trajo el importador no se pierde al traducirlo."""
        carisma = self.altria.habilidades[0]
        self.assertEqual(carisma.nombre, "Carisma")
        self.assertEqual(carisma.nombre_para("es"), "Carisma")
        self.assertEqual(carisma.nombre_para("en"), "Charisma B")

    def test_los_que_no_se_tocaron_valen_para_los_dos(self) -> None:
        """Sin traduccion a mano, se usa el nombre de los datos."""
        otro = next(
            p for p in self.catalogo if p.collection_no not in (2, 11, 17, 31, 40, 47, 59, 108)
        )
        hab = otro.habilidades[0]
        self.assertEqual(hab.nombre_para("en"), hab.nombre)

    def test_el_rasgo_tiene_su_version_en_ingles(self) -> None:
        self.assertIn("guardia", self.altria.rasgo.texto("es"))
        self.assertIn("guard", self.altria.rasgo.texto("en"))

    def test_un_rasgo_sin_traducir_no_se_queda_en_blanco(self) -> None:
        from src.game.personajes import Rasgo

        rasgo = Rasgo(descripcion="Solo en espanol")
        self.assertEqual(rasgo.texto("en"), "Solo en espanol")


class PruebaIdiomaDeLaGuerra(unittest.TestCase):
    def test_la_guerra_guarda_su_idioma(self) -> None:
        guerra = Guerra(id="1", canal_id="1", idioma="en")
        self.assertEqual(guerra.idioma, "en")
        m = guerra.inscribir("u1", "Cris")
        self.assertEqual(m.idioma, "en")

    def test_un_idioma_raro_cae_al_por_defecto(self) -> None:
        self.assertEqual(
            Guerra(id="1", canal_id="1", idioma="fr").idioma, IDIOMA_POR_DEFECTO
        )

    def test_los_errores_de_la_guerra_hablan_su_idioma(self) -> None:
        guerra = Guerra(id="1", canal_id="1", idioma="en")
        guerra.inscribir("u1", "Cris")
        with self.assertRaises(ValueError) as e:
            guerra.inscribir("u1", "Cris")
        self.assertIn("already", str(e.exception))


if __name__ == "__main__":
    unittest.main()
