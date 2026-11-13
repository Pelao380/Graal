"""IA que reemplaza a un Master ausente y maneja a los NPC.

Es a proposito simple y legible: juega bien lo evidente y no intenta leer la
mente del rival. Que tan fuerte debe jugar sigue abierto ("Que tan bien juega
la IA sustituta", en docs/puntos-abiertos.md), y se ajusta cambiando los
umbrales de aqui.

Con las habilidades mide todo en la misma unidad, "ataques", porque usar una
cuesta un turno de ataque: asi la decision no depende de numeros inventados y
se ajusta sola si cambia ESCALA_EFECTO.
"""

from __future__ import annotations

import random

from .battle import (
    ESCALA_EFECTO,
    MULTIPLICADOR_CRITICO,
    MULTIPLICADOR_NOBLE_FANTASMA,
    Accion,
    Batalla,
    Combatiente,
    Decision,
)
from .personajes import BONO_DEL_NEGATIVO, Efecto, Habilidad, Objetivo
from .servant import MANA_POR_ATAQUE, MANA_POR_HABILIDAD

UMBRAL_DEFENDER = 0.30  # defiende si le queda menos de este % de vida
UMBRAL_CURAR = 0.60  # no se cura por encima de este % de vida: lo tiraria

# Una habilidad cuesta el turno entero, o sea un ataque. Asi que la IA mide
# todo en la misma unidad, "ataques", y solo usa lo que devuelve mas de 1.
#
# Medido con el simulador (modo `habilidades`): con los valores de FGO tal
# cual casi nada llega a 1, y por eso la IA casi no las usa; eso es lo
# correcto mientras ESCALA_EFECTO siga en 1. Si se sube la escala, esta
# cuenta se da cuenta sola y las empieza a usar, sin tocar la IA.
PAGA_EL_TURNO = 1.0

# Aguantar un golpe mortal es una curacion que te cobras cuando hace falta, y
# por eso no vale lo mismo que curarse ahora: puede que la batalla se acabe
# antes de que te salve, o que te salve con el rival a punto de caer. El
# descuento es lo que separa "me guardo un seguro" de "me curo".
DESCUENTO_AGUANTAR = 0.5

# Aqui estuvo un `DESCUENTO_POR_EFECTO` de 0.8 para BAJAR_DEFENSA, con un
# razonamiento que suena bien: bajarle la defensa al rival solo se cobra en
# los turnos en que le pegas, y el turno que gastas poniendolo no es uno de
# ellos, asi que deberia valer menos que subirse el ataque. **Medido, salio
# peor**: los personajes que la llevan pasaron del 52.4% al 39.3% contra si
# mismos con esa habilidad muerta. Asi que no esta, y queda escrito para que
# no se vuelva a intentar sin medirlo.



def _cuanto_paga(
    hab: Habilidad,
    yo: Combatiente,
    vida_relativa: float,
    blanco: Combatiente | None = None,
) -> float:
    """Lo que da una habilidad, medido en ataques.

    - Un bono de +v durante t turnos vale v*t ataques, y eso vale igual para
      los dos negativos: bajarle el ataque al rival es como subirse la
      defensa, y bajarle la defensa es como subirse el ataque, solo que contra
      uno en vez de contra todos. Esta cuenta es optimista en una batalla de
      cuatro, porque da por hecho que el rival al que se lo pones es el que te
      pega y al que pegas.
    - Esquivar un golpe es un ataque del rival que no pasa: vale 1.
    - Aguantar es una curacion guardada para cuando haga falta. Vale lo mismo
      que curarse eso, con un descuento porque puede que no llegue a usarse.
    - Un punto de critico solo anade la parte que el critico multiplica.
    - Curar es dano negativo: vale lo que aguanta, en ataques del rival, y
      curarse con la vida casi llena es tirarlo.
    - El mana sustituye a un ataque, asi que cuenta solo lo que pasa de la
      diferencia entre lo que da atacar y lo que da usar una habilidad; y vale
      lo que ese mana adelanta del Noble Fantasma, que pega como tres ataques.
    - Quitarle mana al rival es la misma cuenta al reves, y por eso **mira el
      rival**: lo que retrasa su Noble Fantasma. Si no tiene mana, no retrasa
      nada y no vale nada, asi que esa es la unica habilidad que puede valer 0
      por quien hay enfrente y no por quien la lleva.
    """
    valor = hab.valor * ESCALA_EFECTO.get(hab.efecto, 1.0)

    if hab.efecto in (
        Efecto.ATAQUE,
        Efecto.DEFENSA,
        Efecto.BAJAR_ATAQUE,
        Efecto.BAJAR_DEFENSA,
    ):
        return valor * hab.turnos
    if hab.efecto is Efecto.EVASION:
        return valor
    if hab.efecto is Efecto.AGUANTAR:
        dano_tipico = max(1, yo.servant.ataque)
        return DESCUENTO_AGUANTAR * valor * yo.servant.vida_maxima / dano_tipico
    if hab.efecto is Efecto.CRITICO:
        return valor * hab.turnos * (MULTIPLICADOR_CRITICO - 1)
    if hab.efecto is Efecto.CURAR:
        if vida_relativa >= UMBRAL_CURAR:
            return 0.0
        dano_tipico = max(1, yo.servant.ataque)
        return valor * yo.servant.vida_maxima / dano_tipico
    if hab.efecto is Efecto.MANA:
        # Ya no se mira si solto el Noble Fantasma: se puede repetir, asi que
        # el mana sigue valiendo lo mismo despues del primero. Mientras habia
        # tope, esta cuenta era optimista hasta cuando devolvia 0, porque
        # llegar a 100 estaba asegurado en el turno 6 de un combate de 10 y
        # adelantarlo no compraba nada.
        por_punto = (MULTIPLICADOR_NOBLE_FANTASMA - 1) / max(1, yo.costo_np)
        return (valor - (MANA_POR_ATAQUE - MANA_POR_HABILIDAD)) * por_punto
    if hab.efecto is Efecto.BAJAR_MANA:
        if blanco is None:
            return 0.0
        # No se le puede quitar mas del que tiene, asi que lo que vale es lo
        # que de verdad le quita.
        quitado = min(valor, blanco.mana)
        por_punto = (MULTIPLICADOR_NOBLE_FANTASMA - 1) / max(1, blanco.costo_np)
        return quitado * por_punto
    return 0.0


def _habilidad_de_ataque(batalla: Batalla, yo: Combatiente) -> int | None:
    """Una habilidad de ataque lista, si no tiene ya el bono puesto.

    Sirve para la mejor jugada del combate: cargar el golpe y soltar el Noble
    Fantasma al turno siguiente, porque el bono de ataque lo multiplica igual
    que un golpe normal. El mana no se enfria ni se gasta esperando un turno.
    """
    if yo.bono(Efecto.ATAQUE) or yo.uso_habilidad_turno_anterior:
        return None
    for n in batalla.habilidades_disponibles(yo.id):
        hab = yo.servant.habilidad(n)
        if (
            hab
            and hab.efecto is Efecto.ATAQUE
            and hab.objetivo is not Objetivo.OTRO
            and hab.valor
        ):
            return n
    return None


def _prioridad(
    hab: Habilidad,
    yo: Combatiente,
    vida_relativa: float,
    blanco: Combatiente | None = None,
) -> float:
    """Cuanto le conviene a la IA gastar el turno en esta habilidad.

    0 significa "no ahora". Todo se mide en ataques, asi que se pueden
    comparar entre si: gana la que mas devuelve.
    """
    if hab.efecto in BONO_DEL_NEGATIVO:
        # El bono va al rival, asi que es ahi donde hay que mirar si ya esta
        # puesto. Y se mira el signo: el rival puede tener un bono de ataque
        # suyo, que no es lo mismo que estar debilitado.
        if blanco is None or blanco.bono(BONO_DEL_NEGATIVO[hab.efecto]) < 0:
            return 0.0
    elif not hab.instantanea and yo.bono(hab.efecto):
        return 0.0  # ya lo tiene puesto: repetirlo es tirar el turno
    paga = _cuanto_paga(hab, yo, vida_relativa, blanco)
    return paga if paga >= PAGA_EL_TURNO else 0.0


def _mejor_habilidad(
    batalla: Batalla, yo: Combatiente, blanco: Combatiente | None = None
) -> int | None:
    """El numero de la habilidad que la IA usaria ahora, si alguna.

    Dos frenos aprendidos midiendo: encadenar habilidades es la peor jugada
    que existe, porque cada una cuesta un turno entero y el bono de la
    anterior se va sin cobrarse. Asi que nunca dos turnos seguidos, y con un
    bono de dano puesto toca atacar, que es lo que lo cobra.
    """
    if yo.uso_habilidad_turno_anterior:
        return None
    if yo.bono(Efecto.ATAQUE) or yo.bono(Efecto.CRITICO):
        return None

    vida_relativa = yo.vida / yo.servant.vida_maxima
    mejor: tuple[float, int] | None = None
    for n in batalla.habilidades_disponibles(yo.id):
        hab = yo.servant.habilidad(n)
        if hab is None or not hab.hace_algo:
            continue
        # Las que solo sirven para **regalar** un beneficio a otro no las usa:
        # en una guerra de todos contra todos eso es una decision de Master y
        # no una jugada que una heuristica pueda tomar por el. Una habilidad
        # negativa tambien apunta a otro, pero no es un regalo: es un ataque,
        # y esa si la usa.
        if hab.objetivo is Objetivo.OTRO and not hab.negativa:
            continue
        p = _prioridad(hab, yo, vida_relativa, blanco)
        if p > 0 and (mejor is None or p > mejor[0]):
            mejor = (p, n)
    return mejor[1] if mejor else None


def decidir(
    batalla: Batalla, yo: Combatiente, rng: random.Random | None = None
) -> Decision:
    rng = rng or batalla.rng
    rivales = batalla.rivales_de(yo.id)
    if not rivales:
        return Decision(Accion.ESPERAR)

    posibles = batalla.acciones_posibles(yo.id)
    if Accion.ESPERAR in posibles:
        return Decision(Accion.ESPERAR)

    # Remata al mas debil: acorta la batalla y evita ataques que no conectan.
    objetivo = min(rivales, key=lambda c: c.vida)

    if Accion.NOBLE_FANTASMA in posibles:
        if Accion.HABILIDAD in posibles:
            n = _habilidad_de_ataque(batalla, yo)
            if n is not None:
                return Decision(Accion.HABILIDAD, yo.id, n)
        return Decision(Accion.NOBLE_FANTASMA, objetivo.id)

    if Accion.HABILIDAD in posibles:
        n = _mejor_habilidad(batalla, yo, objetivo)
        if n is not None:
            hab = yo.servant.habilidad(n)
            # Un beneficio se lo aplica a si misma, que es lo unico que una
            # heuristica puede decidir sin leer la mesa; un debuff va al mismo
            # rival que iba a atacar, que es el que esta rematando.
            a_quien = objetivo.id if hab is not None and hab.negativa else yo.id
            return Decision(Accion.HABILIDAD, a_quien, n)

    vida_relativa = yo.vida / yo.servant.vida_maxima
    if (
        vida_relativa < UMBRAL_DEFENDER
        and not yo.defendio_turno_anterior
        and Accion.DEFENDER in posibles
    ):
        return Decision(Accion.DEFENDER)

    # Con el Noble Fantasma a un paso, defender da mas mana que atacar.
    if (
        yo.mana >= yo.costo_np - 40
        and not yo.defendio_turno_anterior
        and Accion.DEFENDER in posibles
    ):
        return Decision(Accion.DEFENDER)

    return Decision(Accion.ATACAR, objetivo.id)


def votar_continuar(batalla: Batalla, yo: Combatiente) -> bool:
    """La IA sigue luchando si esta mejor que su rival."""
    rivales = batalla.rivales_de(yo.id)
    if not rivales:
        return False
    mejor_rival = max(rivales, key=lambda c: c.vida)
    return yo.vida > mejor_rival.vida
