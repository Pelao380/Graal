"""Pruebas de los efectos del 2026-11-09.

Esquivar un golpe, no caerte, y los tres efectos negativos (BAJAR_ATAQUE,
BAJAR_DEFENSA y BAJAR_MANA), que son los primeros que apuntan al rival. Los
dos primeros negativos son bonos con el signo cambiado; quitar mana no, porque
es el espejo de MANA, que tampoco era un bono.

Las reglas que cubren, todas de `docs/decisiones.md`:

- Esquivar y aguantar **se gastan de uno en uno**, no por turnos: si duraran
  por turnos, una evasion de dos turnos esquivaria los tres ataques de una
  batalla de cuatro, y eso es ser intocable.
- Los negativos no son reglas nuevas: son el bono de ataque o de defensa que
  ya existia, con el valor en negativo y puesto sobre otro. Por eso hay un
  suelo (`SUELO_BONO`): sin el, dos rivales turnandose dejan a alguien sin
  pegar nada.
- Un efecto negativo **nunca se lo puede poner nadie a si mismo**, y eso lo
  garantizan dos sitios: `Objetivo.OTRO` en la ficha y el importador, que solo
  acepta un efecto negativo si en FGO apuntaba al enemigo.
"""

from __future__ import annotations

import random
import unittest

from src.game import ai, personajes
from src.game.battle import (
    SUELO_BONO,
    Accion,
    Batalla,
    Decision,
)
from src.game.personajes import (
    BONO_DEL_NEGATIVO,
    EFECTOS_NEGATIVOS,
    VALOR_POR_EFECTO,
    Efecto,
    Habilidad,
    Objetivo,
)

# El ayudante de las pruebas de habilidades: un Rider (fuera del triangulo) de
# nivel 15 con las habilidades que se le pasen. Se reusa a proposito, para que
# las dos familias de pruebas midan sobre el mismo personaje.
from tests.test_habilidades import _combatiente

# Los efectos que entraron el 2026-11-09, los cuatro de la primera tanda y
# quitar mana, que llego despues.
NUEVOS = (
    Efecto.EVASION,
    Efecto.AGUANTAR,
    Efecto.BAJAR_ATAQUE,
    Efecto.BAJAR_DEFENSA,
    Efecto.BAJAR_MANA,
)

NIEBLA = Habilidad(
    nombre="Niebla",
    efecto=Efecto.EVASION,
    objetivo=Objetivo.UNO_MISMO,
)
TERCO = Habilidad(
    nombre="Terco",
    efecto=Efecto.AGUANTAR,
    objetivo=Objetivo.UNO_MISMO,
)
MALDICION = Habilidad(
    nombre="Maldicion",
    efecto=Efecto.BAJAR_ATAQUE,
    objetivo=Objetivo.OTRO,
)
GRIETA = Habilidad(
    nombre="Grieta",
    efecto=Efecto.BAJAR_DEFENSA,
    objetivo=Objetivo.OTRO,
)
DRENAJE = Habilidad(
    nombre="Drenaje",
    efecto=Efecto.BAJAR_MANA,
    objetivo=Objetivo.OTRO,
)


def _batalla(*combatientes, semilla: int = 1) -> Batalla:
    return Batalla(list(combatientes), rng=random.Random(semilla))


class PruebaEsquivar(unittest.TestCase):
    def test_el_golpe_no_toca(self) -> None:
        a, b = _combatiente("a", NIEBLA), _combatiente("b")
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        entera = a.vida
        batalla.resolver_turno({"b": Decision(Accion.ATACAR, "a")})
        self.assertEqual(a.vida, entera, "no le quito nada de vida")

    def test_se_gasta_con_el_primer_golpe(self) -> None:
        """Un golpe esquivado, no dos: es lo que la separa de ser intocable."""
        a, b, c = (
            _combatiente("a", NIEBLA),
            _combatiente("b"),
            _combatiente("c"),
        )
        batalla = _batalla(a, b, c)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        entera = a.vida
        batalla.resolver_turno(
            {
                "b": Decision(Accion.ATACAR, "a"),
                "c": Decision(Accion.ATACAR, "a"),
            }
        )
        self.assertLess(a.vida, entera, "el segundo golpe si entro")

    def test_no_queda_puesta_para_siempre(self) -> None:
        a, b = _combatiente("a", NIEBLA), _combatiente("b")
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        self.assertTrue(a.bono(Efecto.EVASION))
        # Dura los turnos de la tabla y ni uno mas.
        for _ in range(personajes.TURNOS_POR_EFECTO[Efecto.EVASION] + 1):
            batalla.resolver_turno({})
        self.assertFalse(a.bono(Efecto.EVASION), "caduco sin gastarse")


class PruebaAguantar(unittest.TestCase):
    def _a_punto_de_caer(self):
        a = _combatiente("a", TERCO, vida=1)
        b = _combatiente("b")
        return a, b, _batalla(a, b)

    def test_no_cae_con_el_golpe_mortal(self) -> None:
        a, b, batalla = self._a_punto_de_caer()
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        batalla.resolver_turno({"b": Decision(Accion.ATACAR, "a")})
        self.assertTrue(a.vivo, "aguanto en pie")
        self.assertEqual(
            a.vida,
            int(a.servant.vida_maxima * VALOR_POR_EFECTO[Efecto.AGUANTAR]),
        )
        self.assertNotIn("a", batalla.caidos)

    def test_el_segundo_golpe_mortal_si_tumba(self) -> None:
        """Se gasta cuando salva, asi que salva una vez."""
        a, b, batalla = self._a_punto_de_caer()
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        for _ in range(12):
            if not a.vivo:
                break
            batalla.resolver_turno({"b": Decision(Accion.ATACAR, "a")})
        self.assertFalse(a.vivo)
        self.assertFalse(a.bono(Efecto.AGUANTAR), "se gasto al salvarlo")

    def test_mientras_no_te_tumben_sigue_puesto(self) -> None:
        a = _combatiente("a", TERCO)
        b = _combatiente("b")
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        batalla.resolver_turno({"b": Decision(Accion.ATACAR, "a")})
        self.assertTrue(a.vivo)
        self.assertTrue(a.bono(Efecto.AGUANTAR), "no se gasta por un golpe")


class PruebaLosNegativos(unittest.TestCase):
    """Lo que tienen de raro: el bono se lo lleva el otro."""

    def test_bajar_el_ataque_es_un_bono_de_ataque_en_negativo(self) -> None:
        a, b = _combatiente("a", MALDICION), _combatiente("b")
        batalla = _batalla(a, b)
        pegaba = b.ataque_actual
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "b", 1)})
        self.assertLess(b.bono(Efecto.ATAQUE), 0)
        self.assertLess(b.ataque_actual, pegaba)
        self.assertEqual(a.bono(Efecto.ATAQUE), 0, "a el no le paso nada")

    def test_bajar_la_defensa_hace_que_reciba_mas(self) -> None:
        a, b = _combatiente("a", GRIETA), _combatiente("b")
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "b", 1)})
        self.assertLess(b.bono(Efecto.DEFENSA), 0)

    def test_no_se_lo_puede_poner_uno_a_si_mismo(self) -> None:
        a, b = _combatiente("a", MALDICION), _combatiente("b")
        batalla = _batalla(a, b)
        ofrecidos = [c.id for c in batalla.objetivos_posibles("a", 1)]
        self.assertEqual(ofrecidos, ["b"], "solo rivales")

    def test_apuntar_mal_no_lo_convierte_en_un_regalo(self) -> None:
        """Pedirlo sobre uno mismo cae en un rival, no en el que lo usa."""
        a, b = _combatiente("a", MALDICION), _combatiente("b")
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "a", 1)})
        self.assertEqual(a.bono(Efecto.ATAQUE), 0)
        self.assertLess(b.bono(Efecto.ATAQUE), 0)

    def test_el_suelo_no_deja_a_nadie_sin_pegar(self) -> None:
        """Dos bajadas seguidas no bajan mas que el suelo."""
        a = _combatiente("a", MALDICION, MALDICION)
        b = _combatiente("b")
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "b", 1)})
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "b", 2)})
        self.assertEqual(b.bono(Efecto.ATAQUE), SUELO_BONO[Efecto.ATAQUE])
        self.assertGreater(b.ataque_actual, 0)


class PruebaBajarMana(unittest.TestCase):
    """El espejo exacto de MANA: instantaneo, y no es un bono."""

    def test_le_quita_el_mana_al_rival(self) -> None:
        a, b = _combatiente("a", DRENAJE), _combatiente("b")
        b.mana = 80
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "b", 1)})
        self.assertEqual(b.mana, 80 - int(VALOR_POR_EFECTO[Efecto.BAJAR_MANA]))

    def test_no_baja_de_cero(self) -> None:
        a, b = _combatiente("a", DRENAJE), _combatiente("b")
        b.mana = 10
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "b", 1)})
        self.assertEqual(b.mana, 0)

    def test_no_deja_ningun_bono(self) -> None:
        """Si dejara uno, `bono()` lo leeria como un -60 de ataque o de vida."""
        a, b = _combatiente("a", DRENAJE), _combatiente("b")
        b.mana = 80
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "b", 1)})
        self.assertFalse(b.bonos)
        self.assertNotIn(Efecto.BAJAR_MANA, BONO_DEL_NEGATIVO)

    def test_el_que_la_usa_no_pierde_el_suyo(self) -> None:
        a, b = _combatiente("a", DRENAJE), _combatiente("b")
        a.mana, b.mana = 80, 80
        batalla = _batalla(a, b)
        antes = a.mana
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "b", 1)})
        self.assertGreaterEqual(a.mana, antes, "usarla da mana, no lo quita")

    def test_la_IA_no_la_usa_contra_quien_no_tiene_mana(self) -> None:
        """Quitarle 60 a quien tiene 0 no retrasa nada."""
        a, b = _combatiente("a", DRENAJE), _combatiente("b")
        b.mana = 0
        batalla = _batalla(a, b)
        d = ai.decidir(batalla, a, random.Random(1))
        self.assertIsNot(d.accion, Accion.HABILIDAD)

    def test_la_IA_la_usa_contra_quien_esta_cargado(self) -> None:
        a, b = _combatiente("a", DRENAJE), _combatiente("b")
        b.mana = 90
        batalla = _batalla(a, b)
        d = ai.decidir(batalla, a, random.Random(1))
        self.assertIs(d.accion, Accion.HABILIDAD)
        self.assertEqual(d.objetivo, "b")


class PruebaLaIA(unittest.TestCase):
    def test_usa_un_debuff_y_lo_apunta_al_rival(self) -> None:
        """Un debuff apunta a otro, pero no es un regalo: es un ataque."""
        a, b = _combatiente("a", GRIETA), _combatiente("b")
        batalla = _batalla(a, b)
        d = ai.decidir(batalla, a, random.Random(1))
        self.assertIs(d.accion, Accion.HABILIDAD)
        self.assertEqual(d.objetivo, "b")

    def test_no_lo_repite_sobre_quien_ya_lo_tiene(self) -> None:
        a, b = _combatiente("a", GRIETA, GRIETA), _combatiente("b")
        batalla = _batalla(a, b)
        batalla.resolver_turno({"a": Decision(Accion.HABILIDAD, "b", 1)})
        # Sin el freno de "ya lo tiene puesto" gastaria el turno otra vez.
        d = ai.decidir(batalla, a, random.Random(1))
        self.assertIsNot(d.accion, Accion.HABILIDAD)

    def test_sigue_sin_regalar_un_beneficio(self) -> None:
        """La regla vieja no se toco: un buff para otro no lo decide una IA."""
        regalo = Habilidad(
            nombre="Regalo",
            efecto=Efecto.ATAQUE,
            objetivo=Objetivo.OTRO,
            valor=1.5,
            turnos=1,
        )
        a, b = _combatiente("a", regalo), _combatiente("b")
        batalla = _batalla(a, b)
        d = ai.decidir(batalla, a, random.Random(1))
        self.assertIsNot(d.accion, Accion.HABILIDAD)

    def test_esquivar_y_aguantar_pagan_el_turno(self) -> None:
        """Si no pagaran, la IA no las usaria y serian letra muerta."""
        for hab in (NIEBLA, TERCO):
            with self.subTest(hab.nombre):
                a, b = _combatiente("a", hab), _combatiente("b")
                batalla = _batalla(a, b)
                d = ai.decidir(batalla, a, random.Random(1))
                self.assertIs(d.accion, Accion.HABILIDAD, hab.nombre)


class PruebaElPlantel(unittest.TestCase):
    """Lo que tiene que cumplir el plantel de verdad, no uno de mentira."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.plantel = personajes.cargar()

    def test_un_efecto_negativo_siempre_apunta_a_otro(self) -> None:
        for p in self.plantel:
            for h in p.habilidades:
                if h.efecto in EFECTOS_NEGATIVOS:
                    self.assertIs(
                        h.objetivo,
                        Objetivo.OTRO,
                        f"{p.nombre}: {h.nombre} se la podria poner a si mismo",
                    )

    def test_a_otro_no_siempre_es_negativo(self) -> None:
        """Regalar un beneficio sigue existiendo: no es lo mismo que un debuff."""
        regalos = [
            h
            for p in self.plantel
            for h in p.habilidades
            if h.objetivo is Objetivo.OTRO and h.efecto not in EFECTOS_NEGATIVOS
        ]
        self.assertTrue(regalos)

    def test_los_efectos_nuevos_estan_en_el_plantel(self) -> None:
        """Si alguno saliera a cero, la traduccion no llego a ningun personaje."""
        hay = {h.efecto for p in self.plantel for h in p.habilidades}
        for efecto in NUEVOS:
            self.assertIn(efecto, hay, efecto.value)

    def test_ninguna_habilidad_se_queda_sin_efecto(self) -> None:
        """Las 39 que quedaban se llenaron a mano el 2026-11-09.

        Si esto falla, es que una reimportacion trajo personajes nuevos con
        habilidades que el importador no sabe traducir: hay que llenarles el
        hueco en `data/personajes.json`, como los otros 39.
        """
        vacias = [
            f"{p.nombre}: {h.nombre}"
            for p in self.plantel
            for h in p.habilidades
            if h.efecto is Efecto.NINGUNO
        ]
        self.assertEqual(vacias, [], f"{len(vacias)} habilidades sin efecto")

    def test_la_ficha_los_sabe_contar(self) -> None:
        """Cada efecto necesita su linea; sin ella, `t()` reventaria."""
        for efecto in NUEVOS:
            objetivo = (
                Objetivo.OTRO
                if efecto in EFECTOS_NEGATIVOS
                else Objetivo.UNO_MISMO
            )
            hab = Habilidad(nombre="X", efecto=efecto, objetivo=objetivo)
            for idioma in ("es", "en"):
                with self.subTest(efecto=efecto.value, idioma=idioma):
                    self.assertTrue(hab.descripcion(idioma))

    def test_cada_negativo_es_un_bono_o_es_instantaneo(self) -> None:
        """Las dos unicas formas que tiene un negativo de existir.

        O es un bono con el signo cambiado (y entonces esta en
        `BONO_DEL_NEGATIVO`) o es instantaneo, como quitar mana. Un negativo
        que no fuera ninguna de las dos no lo sabria aplicar nadie.
        """
        self.assertTrue(set(BONO_DEL_NEGATIVO) <= set(EFECTOS_NEGATIVOS))
        for efecto in EFECTOS_NEGATIVOS:
            with self.subTest(efecto=efecto.value):
                self.assertTrue(
                    efecto in BONO_DEL_NEGATIVO
                    or efecto in personajes.EFECTOS_INSTANTANEOS,
                    f"{efecto.value}: ni es un bono ni es instantaneo",
                )


if __name__ == "__main__":
    unittest.main()
