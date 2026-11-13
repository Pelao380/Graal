"""El vigilante de plazos: cierra los dias a los que se les agota la ventana.

Es lo que hace que una guerra avance sola. Sin esto alguien tiene que empujar
cada dia con `/empezar-batallas`, y una persona que no aparece deja la guerra
parada, porque el boton del creador espera a que todos acaben su dia.

**El plazo no espera a nadie**, al contrario que el boton: quien no entreno
tuvo la ventana entera para hacerlo. Es la razon de ser del plazo.

Lo que decide si un dia vencio es la propia `Guerra` (`plazo_cumplido`, con
su reloj), no este modulo. Aqui solo esta el despertador y lo de hablar por el
canal, que es lo unico que necesita a Discord.

Los plazos se guardan con su guerra (`vence_preparacion`, en la tabla
`plazos`), asi que un plazo que vencio con el bot apagado se nota en la
primera revision al volver: no hace falta nada especial aqui, porque lo que
mira este modulo es el reloj de la guerra y la guerra vuelve con su plazo
puesto. Lo que falta son los otros dos plazos, el maximo del dia y los 5
minutos por turno. Ver `docs/puntos-abiertos.md`.
"""

from __future__ import annotations

import logging

from discord.ext import tasks

from .game import dia
from .game.war import Fase, Guerra

registro = logging.getLogger(__name__)

# Cada cuanto mira el reloj. La ventana mas corta son 30 minutos, asi que con
# mirar cada medio minuto el dia se cierra con un retraso que nadie nota, y el
# bot no hace nada el 99% del tiempo.
SEGUNDOS_ENTRE_REVISIONES = 30


class Vigilante:
    """Revisa cada poco si a alguna guerra se le acabo el dia.

    Vive en el Cog y se enciende con el. Se le pasan dos cosas para no tener
    que conocerlo: de donde salen las guerras y que hacer con una que vencio.
    """

    def __init__(self, cog) -> None:
        self.cog = cog
        self.bucle = tasks.loop(seconds=SEGUNDOS_ENTRE_REVISIONES)(self.revisar)

    def arrancar(self) -> None:
        if not self.bucle.is_running():
            self.bucle.start()

    def parar(self) -> None:
        self.bucle.cancel()

    def vencidas(self) -> list[Guerra]:
        """Las guerras a las que se les agoto la ventana del dia."""
        return [g for g in self.cog.guerras.values() if g.plazo_cumplido]

    def combates_estancados(self) -> list[Guerra]:
        """Las guerras con alguna batalla esperando a alguien que no contesta."""
        vencidas = []
        for guerra in self.cog.guerras.values():
            estado = self.cog.combates.get(guerra.id)
            if estado is None:
                continue
            if any(c.plazo_cumplido() for c in estado.pendientes):
                vencidas.append(guerra)
        return vencidas

    def atascadas(self) -> list[Guerra]:
        """Las que se quedaron en `Fase.BATALLA` sin batallas en memoria.

        Es lo que deja un reinicio del bot a media batalla. Sin esto la guerra
        no vuelve a avanzar nunca, porque el dia lo cierra una decision que ya
        no va a llegar.
        """
        return [
            g
            for g in self.cog.guerras.values()
            if g.fase is Fase.BATALLA
            and not g.terminada
            and self.cog.combates.get(g.id) is None
        ]

    async def revisar(self) -> None:
        """Una pasada. Nunca deja que un error tumbe el bucle.

        Si al cerrar un dia algo falla, se registra y se sigue con las demas:
        una guerra rota no puede congelar a todas las del servidor.

        Son tres cosas y no una, porque hay tres formas de quedarse parado: el
        dia que se le agoto la ventana, el turno al que le falta alguien y la
        guerra que se quedo en batalla cuando el bot se reinicio.
        """
        for guerra, que in (
            [(g, self.cerrar) for g in self.vencidas()]
            + [(g, self.avanzar_combates) for g in self.combates_estancados()]
            + [(g, self.recuperar) for g in self.atascadas()]
        ):
            try:
                await que(guerra)
            except Exception:  # noqa: BLE001 - el bucle tiene que sobrevivir
                registro.exception(
                    "no se pudo avanzar el dia %s de la guerra %s",
                    guerra.dia,
                    guerra.id,
                )

    async def avanzar_combates(self, guerra: Guerra) -> None:
        """Decide por quien no contesto y, si con eso acaba el dia, lo cierra.

        Decidir por alguien no es castigarlo: la IA elige por el lo mismo que
        elegiria por un bot. Lo que no puede pasar es que el turno se quede
        quieto.
        """
        estado = self.cog.combates.get(guerra.id)
        if estado is None:
            return
        for combate in estado.pendientes:
            if combate.plazo_cumplido():
                combate.avanzar_con_ia()
        await self.cog.cerrar_combates_en_el_canal(guerra)

    async def recuperar(self, guerra: Guerra) -> None:
        """Pelea con la IA lo que quedo a medias y cuenta el dia."""
        canal = self._canal(guerra)
        if canal is None:
            return
        cierre = dia.recuperar_dia(guerra, self.cog.rng)
        self.cog.guardar(guerra)
        registro.warning(
            "la guerra %s se quedo en batalla; el dia %s lo acabo la IA",
            guerra.id,
            cierre.dia,
        )
        for mensaje in self.cog.narrar_cierre(guerra, cierre, por_plazo=True):
            await canal.send(mensaje)
        await self._dejar_el_boton(guerra, canal)

    def _canal(self, guerra: Guerra):
        """El canal de la guerra, o `None` si el bot no lo ve.

        Sin canal no se hace nada: avanzar el dia sin poder contarlo seria
        peor, porque la guerra cambia y nadie se entera.
        """
        canal = self.cog.bot.get_channel(int(guerra.canal_id))
        if canal is None:
            registro.warning(
                "la guerra %s apunta a un canal que no veo (%s)",
                guerra.id,
                guerra.canal_id,
            )
        return canal

    async def _dejar_el_boton(self, guerra: Guerra, canal) -> None:
        """El boton que toca en el canal: la batalla, el dia nuevo o nada."""
        aviso, vista = self.cog.aviso_y_vista_de_despues(guerra)
        if vista is not None:
            await canal.send(aviso, view=vista)

    async def cerrar(self, guerra: Guerra) -> None:
        """Cierra la preparacion del dia y lo cuenta en su canal.

        Es la cuarta de las puertas que cierran un dia, y pasa por el mismo
        `cog.cerrar_el_dia` que las otras tres para que las cuatro dejen la
        misma mesa. Lo unico suyo es el `por_plazo`, que cambia la primera
        linea: conviene que se vea si el dia lo cerro la gente o el reloj.
        """
        canal = self._canal(guerra)
        if canal is None:
            return
        await self.cog.cerrar_el_dia(
            guerra, self.cog.enviar_por_el_canal(canal), por_plazo=True
        )
