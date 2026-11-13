"""Pruebas de las habilidades: a quien se le dan y cada cuanto se repiten.

Las dos reglas que cubren estas pruebas:

- En Graal no hay equipos, asi que un efecto que beneficia se le puede dar a
  cualquiera de la batalla: el Master elige. `objetivos_posibles` es lo que
  Discord le va a ofrecer.
- Una habilidad tiene enfriamiento, para que nadie repita la mejor cada turno.
  La duracion y el enfriamiento no cuentan el turno en que se usa, porque
  usarla ya gasta ese turno.
"""

from __future__ import annotations

import random
import unittest

from src.game import ai
from src.game.battle import Accion, Batalla, Combatiente, Decision
from src.game.clases import Clase
from src.game.personajes import (
    ENFRIAMIENTO_POR_EFECTO,
    SIN_HABILIDADES,
    TURNOS_POR_EFECTO,
    VALOR_POR_EFECTO,
    Efecto,
    Habilidad,
    Objetivo,
    Personaje,
    habilidad_desde,
)
from src.game.servant import MANA_POR_ATAQUE, MANA_POR_HABILIDAD, Servant

CARISMA = Habilidad(
    nombre="Carisma",
    efecto=Efecto.ATAQUE,
    objetivo=Objetivo.ALIADO,
    valor=0.50,
    turnos=2,
)
INSTINTO = Habilidad(
    nombre="Instinto",
    efecto=Efecto.CRITICO,
    objetivo=Objetivo.UNO_MISMO,
    valor=0.20,
    turnos=2,
)
TACTICA = Habilidad(
    nombre="Tactica",
    efecto=Efecto.ATAQUE,
    objetivo=Objetivo.OTRO,
    valor=0.30,
    turnos=2,
)
RUNAS = Habilidad(
    nombre="Runas", efecto=Efecto.MANA, objetivo=Objetivo.ALIADO, valor=30
)
CURA = Habilidad(
    nombre="Cura", efecto=Efecto.CURAR, objetivo=Objetivo.ALIADO, valor=0.30
)


def _combatiente(
    id_: str, *habilidades: Habilidad, nivel: int = 15, vida: int | None = None
) -> Combatiente:
    """Un Rider (fuera del triangulo) de nivel 15, con las 3 habilidades."""
    llenas = list(habilidades) + list(SIN_HABILIDADES)
    p = Personaje(
        nombre=id_.upper(), clase=Clase.RIDER, habilidades=tuple(llenas[:3])
    )
    return Combatiente(
        id=id_, nombre=id_.upper(), servant=Servant(p, nivel), vida=vida or 0
    )


class PruebaObjetivos(unittest.TestCase):
    def test_lo_que_es_para_uno_mismo_no_se_puede_regalar(self) -> None:
        a, b = _combatiente("a", INSTINTO), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(1))
        self.assertEqual([c.id for c in batalla.objetivos_posibles("a", 1)], ["a"])

    def test_un_beneficio_se_le_puede_dar_a_cualquiera(self) -> None:
        a, b, c = _combatiente("a", CARISMA), _combatiente("b"), _combatiente("c")
        batalla = Batalla([a, b, c], rng=random.Random(1))
        self.assertEqual(
            sorted(x.id for x in batalla.objetivos_posibles("a", 1)),
            ["a", "b", "c"],
        )

    def test_lo_que_es_para_otro_excluye_a_uno_mismo(self) -> None:
        a, b = _combatiente("a", TACTICA), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(1))
        self.assertEqual([c.id for c in batalla.objetivos_posibles("a", 1)], ["b"])

    def test_el_efecto_cae_en_el_objetivo_elegido(self) -> None:
        """La traicion al revés: el beneficio se lo lleva quien tu digas."""
        a, b = _combatiente("a", CARISMA), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(2))
        batalla.resolver_turno(
            {
                "a": Decision(Accion.HABILIDAD, "b", 1),
                "b": Decision(Accion.DEFENDER),
            }
        )
        self.assertAlmostEqual(b.bono(Efecto.ATAQUE), 0.50)
        self.assertEqual(a.bono(Efecto.ATAQUE), 0.0)

    def test_sin_objetivo_valido_el_beneficio_se_queda_en_casa(self) -> None:
        a, b = _combatiente("a", CARISMA), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(2))
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, None, 1)})
        self.assertAlmostEqual(a.bono(Efecto.ATAQUE), 0.50)

    def test_si_el_elegido_ya_cayo_el_efecto_se_pierde(self) -> None:
        """Igual que el Noble Fantasma: no se redirige."""
        # c es de nivel 15 y a de nivel 5, asi que c golpea antes.
        a = _combatiente("a", CARISMA, nivel=5)
        b = _combatiente("b", nivel=5, vida=1)
        c = _combatiente("c", nivel=15)
        batalla = Batalla([a, b, c], rng=random.Random(3))
        batalla.resolver_turno(
            {
                "c": Decision(Accion.ATACAR, "b"),
                "a": Decision(Accion.HABILIDAD, "b", 1),
                "b": Decision(Accion.ATACAR, "a"),
            }
        )
        self.assertFalse(b.vivo)
        self.assertEqual(a.bono(Efecto.ATAQUE), 0.0)
        self.assertEqual(c.bono(Efecto.ATAQUE), 0.0)
        # Aun asi la gasto: queda enfriando.
        self.assertEqual(a.enfriamiento_restante(1), CARISMA.turnos_de_enfriamiento)

    def test_una_habilidad_sin_desbloquear_no_se_puede_usar(self) -> None:
        a = _combatiente("a", CARISMA, INSTINTO, nivel=5)
        b = _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(1))
        self.assertEqual(batalla.habilidades_disponibles("a"), [1])
        self.assertEqual(batalla.objetivos_posibles("a", 2), [])


class PruebaEnfriamiento(unittest.TestCase):
    def test_los_enfriamientos_salen_del_efecto(self) -> None:
        """La regla de la casa: ataque y defensa 2, mana 3, critico 5."""
        self.assertEqual(ENFRIAMIENTO_POR_EFECTO[Efecto.ATAQUE], 2)
        self.assertEqual(ENFRIAMIENTO_POR_EFECTO[Efecto.DEFENSA], 2)
        self.assertEqual(ENFRIAMIENTO_POR_EFECTO[Efecto.MANA], 3)
        self.assertEqual(ENFRIAMIENTO_POR_EFECTO[Efecto.CRITICO], 5)
        self.assertEqual(CARISMA.turnos_de_enfriamiento, 2)
        self.assertEqual(INSTINTO.turnos_de_enfriamiento, 5)

    def test_una_habilidad_de_enfriamiento_dos_vuelve_en_el_turno_cuatro(self) -> None:
        a, b = _combatiente("a", CARISMA), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(4))
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        self.assertEqual(batalla.habilidades_disponibles("a"), [])
        self.assertNotIn(Accion.HABILIDAD, batalla.acciones_posibles("a"))

        batalla.resolver_turno({"a": Decision(Accion.ATACAR, "b")})  # turno 2
        self.assertEqual(batalla.habilidades_disponibles("a"), [])
        batalla.resolver_turno({"a": Decision(Accion.ATACAR, "b")})  # turno 3
        self.assertEqual(batalla.habilidades_disponibles("a"), [1])  # vuelve en el 4

    def test_repetirla_mientras_enfria_pierde_el_turno(self) -> None:
        a, b = _combatiente("a", CARISMA), _combatiente("b")
        # En espanol a proposito: la prueba mira lo que dice el registro.
        batalla = Batalla([a, b], rng=random.Random(5), idioma="es")
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        mana = a.mana
        eventos = batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        # No se apila el bono y tampoco gana mana: el turno se fue.
        self.assertAlmostEqual(a.bono(Efecto.ATAQUE), 0.50)
        self.assertEqual(a.mana, mana)
        self.assertTrue(any("enfriamiento" in e for e in eventos))


class PruebaDuracion(unittest.TestCase):
    def test_el_turno_en_que_se_usa_no_cuenta(self) -> None:
        """Usarla gasta el turno; si ese turno contara, duraria la mitad."""
        a, b = _combatiente("a", CARISMA), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(6))
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        self.assertAlmostEqual(a.bono(Efecto.ATAQUE), 0.50)  # vale el turno 2
        batalla.resolver_turno({"a": Decision(Accion.ATACAR, "b")})
        self.assertAlmostEqual(a.bono(Efecto.ATAQUE), 0.50)  # y el turno 3
        batalla.resolver_turno({"a": Decision(Accion.ATACAR, "b")})
        self.assertEqual(a.bono(Efecto.ATAQUE), 0.0)  # se acabo

    def test_el_bono_de_ataque_pega_mas(self) -> None:
        total_sin, total_con = 0, 0
        for semilla in range(300):
            a, b = _combatiente("a"), _combatiente("b")
            Batalla([a, b], rng=random.Random(semilla)).resolver_turno(
                {"a": Decision(Accion.ATACAR, "b")}
            )
            total_sin += b.servant.vida_maxima - b.vida

            c, d = _combatiente("c", CARISMA), _combatiente("d")
            batalla = Batalla([c, d], rng=random.Random(semilla))
            batalla.resolver_turno({"c": Decision(Accion.HABILIDAD, "c", 1)})
            batalla.resolver_turno({"c": Decision(Accion.ATACAR, "d")})
            total_con += d.servant.vida_maxima - d.vida
        self.assertGreater(total_con, total_sin * 1.3)

    def test_el_bono_de_defensa_recibe_menos(self) -> None:
        escudo = Habilidad(
            nombre="Escudo",
            efecto=Efecto.DEFENSA,
            objetivo=Objetivo.ALIADO,
            valor=0.50,
            turnos=3,
        )
        total_sin, total_con = 0, 0
        for semilla in range(300):
            a, b = _combatiente("a"), _combatiente("b")
            Batalla([a, b], rng=random.Random(semilla)).resolver_turno(
                {"a": Decision(Accion.ATACAR, "b")}
            )
            total_sin += b.servant.vida_maxima - b.vida

            c, d = _combatiente("c"), _combatiente("d", escudo)
            batalla = Batalla([c, d], rng=random.Random(semilla))
            batalla.resolver_turno({"d": Decision(Accion.HABILIDAD, "d", 1)})
            vida = d.vida
            batalla.resolver_turno({"c": Decision(Accion.ATACAR, "d")})
            total_con += vida - d.vida
        self.assertLess(total_con, total_sin * 0.7)


class PruebaEfectosInstantaneos(unittest.TestCase):
    def test_el_mana_llega_entero(self) -> None:
        a, b = _combatiente("a", RUNAS), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(7))
        antes = a.mana
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        # Los 30 de la habilidad mas lo que da usar una.
        self.assertEqual(a.mana, antes + 30 + MANA_POR_HABILIDAD)

    def test_usar_una_habilidad_da_mana(self) -> None:
        """Si no, gastar el turno costaria tambien los 15 de atacar."""
        a, b = _combatiente("a", INSTINTO), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(7))
        antes = a.mana
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        self.assertEqual(a.mana, antes + MANA_POR_HABILIDAD)
        self.assertLess(MANA_POR_HABILIDAD, MANA_POR_ATAQUE)

    def test_curar_no_pasa_de_la_vida_maxima(self) -> None:
        a, b = _combatiente("a", CURA), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(8))
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        self.assertEqual(a.vida, a.servant.vida_maxima)

    def test_curar_devuelve_vida_al_herido(self) -> None:
        a = _combatiente("a", CURA, vida=100)
        b = _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(9))
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        esperado = 100 + int(a.servant.vida_maxima * 0.30)
        self.assertEqual(a.vida, esperado)

    def test_un_efecto_instantaneo_no_deja_bono(self) -> None:
        a, b = _combatiente("a", RUNAS), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(10))
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        self.assertEqual(a.bonos, [])


class PruebaFicha(unittest.TestCase):
    def test_la_ficha_admite_solo_el_nombre(self) -> None:
        h = habilidad_desde("Carisma")
        self.assertEqual(h.nombre, "Carisma")
        self.assertFalse(h.hace_algo)

    def test_la_ficha_admite_el_efecto_completo(self) -> None:
        h = habilidad_desde(
            {
                "nombre": "Carisma",
                "efecto": "ataque",
                "objetivo": "aliado",
                "valor": 0.09,
                "turnos": 3,
            }
        )
        self.assertIs(h.efecto, Efecto.ATAQUE)
        self.assertIs(h.objetivo, Objetivo.ALIADO)
        self.assertEqual(h.turnos_de_enfriamiento, 2)

    def test_un_efecto_fuera_de_rango_no_se_carga(self) -> None:
        with self.assertRaises(ValueError):
            habilidad_desde(
                {"nombre": "Roto", "efecto": "ataque", "valor": 7, "turnos": 3}
            )

    def test_lo_que_da_cada_efecto_sale_de_la_tabla(self) -> None:
        """La ficha normal solo trae el efecto: el cuanto lo pone el juego."""
        h = habilidad_desde(
            {"nombre": "Carisma", "efecto": "ataque", "objetivo": "aliado"}
        )
        self.assertAlmostEqual(h.valor, VALOR_POR_EFECTO[Efecto.ATAQUE])
        self.assertEqual(h.turnos, TURNOS_POR_EFECTO[Efecto.ATAQUE])
        # La regla de la casa: una habilidad de ataque hace pegar x2.5 el
        # turno siguiente.
        self.assertAlmostEqual(1 + h.valor, 2.5)
        self.assertEqual(h.turnos, 1)

    def test_una_ficha_a_mano_puede_traer_su_propio_valor(self) -> None:
        h = habilidad_desde(
            {"nombre": "Rara", "efecto": "ataque", "valor": 0.4, "turnos": 4}
        )
        self.assertAlmostEqual(h.valor, 0.4)
        self.assertEqual(h.turnos, 4)

    def test_un_efecto_instantaneo_no_puede_durar(self) -> None:
        with self.assertRaises(ValueError):
            habilidad_desde(
                {"nombre": "Roto", "efecto": "mana", "valor": 20, "turnos": 2}
            )


class PruebaIA(unittest.TestCase):
    def test_la_ia_usa_lo_que_la_mejora(self) -> None:
        a, b = _combatiente("a", CARISMA), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(11))
        d = ai.decidir(batalla, a, random.Random(11))
        self.assertIs(d.accion, Accion.HABILIDAD)
        self.assertEqual(d.objetivo, "a")

    def test_la_ia_no_regala_beneficios(self) -> None:
        """Una habilidad que solo sirve para otro es decision de Master."""
        a, b = _combatiente("a", TACTICA), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(12))
        d = ai.decidir(batalla, a, random.Random(12))
        self.assertIsNot(d.accion, Accion.HABILIDAD)

    def test_la_ia_no_repite_lo_que_ya_tiene_puesto(self) -> None:
        largo = Habilidad(
            nombre="Carisma largo",
            efecto=Efecto.ATAQUE,
            objetivo=Objetivo.ALIADO,
            valor=0.50,
            turnos=4,
        )
        a, b = _combatiente("a", largo), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(13))
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        batalla.resolver_turno({"a": Decision(Accion.ATACAR, "b")})
        batalla.resolver_turno({"a": Decision(Accion.ATACAR, "b")})
        # Vuelve a estar disponible (enfriamiento 2) y el bono sigue puesto.
        self.assertEqual(batalla.habilidades_disponibles("a"), [1])
        self.assertAlmostEqual(a.bono(Efecto.ATAQUE), 0.50)
        d = ai.decidir(batalla, a, random.Random(13))
        self.assertIsNot(d.accion, Accion.HABILIDAD)


if __name__ == "__main__":
    unittest.main()
