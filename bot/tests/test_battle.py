"""Pruebas de la logica de combate.

Se ejecutan con:  python -m unittest discover -s tests   (desde bot/)
"""

from __future__ import annotations

import random
import unittest

from src.game.battle import Accion, Batalla, Combatiente, Decision, Estado
from src.game.clases import Clase
from src.game.personajes import Personaje, Rasgo
from src.game.servant import (
    COSTO_NOBLE_FANTASMA,
    MANA_INICIAL,
    MANA_POR_ATAQUE,
    MANA_POR_DEFENSA,
    Servant,
    xp_acumulada,
    xp_para_subir,
)


def _personaje(nombre: str, clase: Clase = Clase.RIDER, **kwargs) -> Personaje:
    """Personaje neutro para las pruebas: Rider queda fuera del triangulo."""
    return Personaje(nombre=nombre, clase=clase, **kwargs)


def _servant(nombre: str, nivel: int = 1, **kwargs) -> Servant:
    return Servant(personaje=_personaje(nombre, **kwargs), nivel=nivel)


def _combatiente(id_: str, nivel: int = 1, vida: int | None = None) -> Combatiente:
    s = _servant(id_.upper(), nivel)
    return Combatiente(id=id_, nombre=id_.upper(), servant=s, vida=vida or 0)


class PruebaXP(unittest.TestCase):
    def test_curva(self) -> None:
        self.assertEqual(xp_para_subir(1), 25)
        self.assertEqual(xp_acumulada(5), 130)
        self.assertEqual(xp_acumulada(10), 405)
        self.assertEqual(xp_acumulada(15), 805)

    def test_subir_varios_niveles_de_una(self) -> None:
        s = _servant("A")
        subidas = s.ganar_xp(130)
        self.assertEqual(s.nivel, 5)
        self.assertEqual(subidas, [2, 3, 4, 5])
        self.assertEqual(s.habilidades_desbloqueadas, 1)

    def test_tope_de_nivel(self) -> None:
        s = _servant("A")
        s.ganar_xp(10_000)
        self.assertEqual(s.nivel, 15)
        self.assertEqual(s.habilidades_desbloqueadas, 3)


class PruebaMana(unittest.TestCase):
    def test_atacar_y_defender_dan_mana(self) -> None:
        a, b = _combatiente("a"), _combatiente("b")
        batalla = Batalla([a, b], rng=random.Random(1))
        batalla.resolver_turno(
            {"a": Decision(Accion.ATACAR, "b"), "b": Decision(Accion.DEFENDER)}
        )
        self.assertEqual(a.mana, MANA_INICIAL + MANA_POR_ATAQUE)
        self.assertEqual(b.mana, MANA_INICIAL + MANA_POR_DEFENSA)

    def test_noble_fantasma_gasta_cien(self) -> None:
        a, b = _combatiente("a"), _combatiente("b")
        a.mana = COSTO_NOBLE_FANTASMA
        batalla = Batalla([a, b], rng=random.Random(2))
        batalla.resolver_turno(
            {"a": Decision(Accion.NOBLE_FANTASMA, "b"), "b": Decision(Accion.ATACAR, "a")}
        )
        self.assertEqual(a.mana, 0)
        self.assertEqual(a.nps_usados, 1)
        # Ya no se puede, pero por el mana, no por un tope.
        self.assertNotIn(Accion.NOBLE_FANTASMA, batalla.acciones_posibles("a"))

    def test_el_noble_fantasma_se_puede_repetir(self) -> None:
        """No hay tope: lo que lo limita es juntar el mana otra vez.

        Con el tope de uno por combate, el mana dejaba de valer en cuanto lo
        soltabas, y las habilidades de mana salian perdiendo el 27% de los
        espejos. Ver docs/decisiones.md.
        """
        a, b = _combatiente("a"), _combatiente("b")
        a.mana = COSTO_NOBLE_FANTASMA * 2
        batalla = Batalla([a, b], rng=random.Random(2))
        for _ in range(2):
            self.assertIn(Accion.NOBLE_FANTASMA, batalla.acciones_posibles("a"))
            batalla.resolver_turno(
                {
                    "a": Decision(Accion.NOBLE_FANTASMA, "b"),
                    "b": Decision(Accion.DEFENDER),
                }
            )
        self.assertEqual(a.nps_usados, 2)
        self.assertEqual(a.mana, 0)
        self.assertTrue(a.np_usado, "np_usado sigue diciendo si solto alguno")

    def test_sobra_mana_y_el_noble_fantasma_sigue_disponible(self) -> None:
        a, b = _combatiente("a"), _combatiente("b")
        a.mana = COSTO_NOBLE_FANTASMA + 30
        batalla = Batalla([a, b], rng=random.Random(3))
        batalla.resolver_turno(
            {"a": Decision(Accion.NOBLE_FANTASMA, "b"), "b": Decision(Accion.DEFENDER)}
        )
        self.assertEqual(a.mana, 30)
        self.assertNotIn(Accion.NOBLE_FANTASMA, batalla.acciones_posibles("a"))
        a.mana = COSTO_NOBLE_FANTASMA
        self.assertIn(Accion.NOBLE_FANTASMA, batalla.acciones_posibles("a"))


class PruebaDefensa(unittest.TestCase):
    def test_segunda_defensa_seguida_puede_fallar(self) -> None:
        exitos = 0
        intentos = 2000
        for semilla in range(intentos):
            a, b = _combatiente("a"), _combatiente("b")
            batalla = Batalla([a, b], rng=random.Random(semilla))
            batalla.resolver_turno(
                {"a": Decision(Accion.DEFENDER), "b": Decision(Accion.ATACAR, "a")}
            )
            mana_antes = a.mana
            batalla.resolver_turno(
                {"a": Decision(Accion.DEFENDER), "b": Decision(Accion.ATACAR, "a")}
            )
            if a.mana > mana_antes:
                exitos += 1
        # La regla dice 30% de exito.
        self.assertAlmostEqual(exitos / intentos, 0.30, delta=0.05)

    def test_defender_reduce_el_dano(self) -> None:
        total_sin, total_con = 0, 0
        for semilla in range(300):
            a, b = _combatiente("a"), _combatiente("b")
            Batalla([a, b], rng=random.Random(semilla)).resolver_turno(
                {"a": Decision(Accion.ATACAR, "b"), "b": Decision(Accion.ATACAR, "a")}
            )
            total_sin += b.servant.vida_maxima - b.vida

            c, d = _combatiente("c"), _combatiente("d")
            Batalla([c, d], rng=random.Random(semilla)).resolver_turno(
                {"c": Decision(Accion.ATACAR, "d"), "d": Decision(Accion.DEFENDER)}
            )
            total_con += d.servant.vida_maxima - d.vida
        self.assertLess(total_con, total_sin * 0.6)


class PruebaOrdenYConexion(unittest.TestCase):
    def test_el_mas_rapido_golpea_primero(self) -> None:
        rapido = _combatiente("rapido", nivel=15)
        lento = _combatiente("lento", nivel=1, vida=1)
        batalla = Batalla([rapido, lento], rng=random.Random(3))
        batalla.resolver_turno(
            {
                "rapido": Decision(Accion.ATACAR, "lento"),
                "lento": Decision(Accion.ATACAR, "rapido"),
            }
        )
        self.assertFalse(lento.vivo)
        self.assertEqual(rapido.vida, rapido.servant.vida_maxima)
        self.assertTrue(batalla.terminada)

    def test_ataque_que_no_conecta_solo_suma_mana(self) -> None:
        rapido = _combatiente("rapido", nivel=15)
        lento = _combatiente("lento", nivel=1, vida=1)
        tercero = _combatiente("tercero", nivel=1)
        batalla = Batalla([rapido, lento, tercero], rng=random.Random(4))
        batalla.resolver_turno(
            {
                "rapido": Decision(Accion.ATACAR, "lento"),
                "tercero": Decision(Accion.ATACAR, "lento"),
                "lento": Decision(Accion.DEFENDER),
            }
        )
        self.assertFalse(lento.vivo)
        # El tercero no redirige su ataque: solo suma el mana.
        self.assertEqual(tercero.mana, MANA_INICIAL + MANA_POR_ATAQUE)
        self.assertEqual(rapido.vida, rapido.servant.vida_maxima)


class PruebaVotacionYTurnoEspecial(unittest.TestCase):
    def _batalla_de_tres_con_una_caida(self) -> Batalla:
        a = _combatiente("a", nivel=15)
        b = _combatiente("b", nivel=1, vida=1)
        c = _combatiente("c", nivel=1)
        batalla = Batalla([a, b, c], rng=random.Random(5))
        batalla.resolver_turno(
            {
                "a": Decision(Accion.ATACAR, "b"),
                "b": Decision(Accion.DEFENDER),
                "c": Decision(Accion.DEFENDER),
            }
        )
        return batalla

    def test_cae_uno_y_se_abre_la_votacion(self) -> None:
        batalla = self._batalla_de_tres_con_una_caida()
        self.assertIs(batalla.estado, Estado.VOTACION)
        self.assertFalse(batalla.terminada)

    def test_si_todos_quieren_terminar_la_batalla_se_cierra(self) -> None:
        batalla = self._batalla_de_tres_con_una_caida()
        batalla.registrar_votos({"a": False, "c": False})
        self.assertTrue(batalla.terminada)

    def test_quien_quiso_terminar_pierde_el_turno_especial(self) -> None:
        batalla = self._batalla_de_tres_con_una_caida()
        batalla.registrar_votos({"a": True, "c": False})
        self.assertIs(batalla.estado, Estado.TURNO_ESPECIAL)
        self.assertEqual(batalla.acciones_posibles("c"), [Accion.ESPERAR])
        self.assertIn(Accion.ATACAR, batalla.acciones_posibles("a"))

        mana_c = batalla.combatientes["c"].mana
        batalla.resolver_turno(
            {"a": Decision(Accion.ATACAR, "c"), "c": Decision(Accion.ESPERAR)}
        )
        # c no actuo: no gana mana ni se defiende.
        self.assertEqual(batalla.combatientes["c"].mana, mana_c)
        self.assertLess(batalla.combatientes["c"].vida, c_vida_maxima(batalla))
        # Despues del turno especial se vuelve a los turnos normales.
        if not batalla.terminada:
            self.assertIs(batalla.estado, Estado.EN_CURSO)


def c_vida_maxima(batalla: Batalla) -> int:
    return batalla.combatientes["c"].servant.vida_maxima


class PruebaTope(unittest.TestCase):
    def test_no_se_admiten_cinco(self) -> None:
        with self.assertRaises(ValueError):
            Batalla([_combatiente(str(i)) for i in range(5)])

    def test_no_se_admite_uno(self) -> None:
        with self.assertRaises(ValueError):
            Batalla([_combatiente("a")])


if __name__ == "__main__":
    unittest.main()
