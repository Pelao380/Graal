"""Comandos de barra y menus del bot.

Por ahora cubren el lobby, la invocacion, la ficha del Servant y los
combates contra NPC. Las batallas por turnos son lo ultimo que se construye,
porque son la parte mas compleja.

Dos reglas de esta capa:

- Ninguna frase se escribe aqui: todas salen de `data/textos.json` a traves de
  `game.textos.t`, para poder jugar la misma guerra en espanol o en ingles. El
  idioma lo elige quien crea la guerra y vale para todo el canal, porque una
  guerra se narra en publico y media conversacion en cada idioma no se
  entiende. Si no elige, se usa el que trae Discord del creador.
- Lo que hace cada accion vive en un metodo `_texto_*` del Cog, y tanto el
  comando como el boton del menu llaman al mismo. Asi las dos puertas no se
  pueden desincronizar.

Las guerras se leen y se escriben en SQLite a traves de `src.repositorio`: el
Cog las carga en `cog_load` y llama a `self.guardar(guerra)` al final de cada
accion que cambia algo. Si anades una accion, acuerdate de llamarla.
"""

from __future__ import annotations

import logging
import math
import random
import sqlite3

import discord
from discord import app_commands
from discord.ext import commands

from . import repositorio
from .game import combate as combate_mod
from .game import dia, invocacion, npc, objetos, personajes, sellos, tienda
from .game.battle import MULTIPLICADOR_NOBLE_FANTASMA, Accion, Decision
from .game.clases import Clase
from .game.npc import COMBATES_POR_DIA
from .game.servant import Servant, xp_para_subir
from .game.textos import IDIOMA_POR_DEFECTO, IDIOMAS, plural, t
from .game.war import (
    DERROTAS_PARA_ELIMINAR,
    MINIMO_HUMANOS_PARA_GRIAL,
    MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA,
    MINIMO_MASTERS,
    TIEMPOS_PREPARACION,
    Fase,
    Guerra,
    Master,
)
from .vigilante import Vigilante

registro = logging.getLogger(__name__)

CATALOGO = personajes.cargar()

# Cuanto dura abierto un menu privado antes de dejar de responder. El boton
# del canal no caduca: la guerra dura dias.
SEGUNDOS_MENU = 10 * 60

# Cuantas lineas del registro de una batalla se ensenan. El registro entero de
# una batalla larga no cabe en un mensaje de Discord (2000 caracteres), y lo
# que interesa es el final.
LINEAS_DE_REGISTRO = 14


def idioma_de_discord(interaction: discord.Interaction) -> str | None:
    """El idioma del usuario segun Discord, si es uno de los nuestros.

    Llega como "es-ES" o "en-GB"; nos quedamos con la parte de delante.
    """
    bruto = str(getattr(interaction, "locale", "") or "")
    return _idioma_de_locale(bruto)


def _idioma_de_locale(locale: str) -> str | None:
    corto = str(locale or "").replace("_", "-").split("-")[0].lower()
    return corto if corto in IDIOMAS else None


def etiqueta(clave: str) -> app_commands.locale_str:
    """Un texto del catalogo que Discord traducira segun quien mire.

    El valor por defecto es el espanol; `Traductor` da el resto a partir de
    la clave.
    """
    return app_commands.locale_str(t(clave), clave=clave)


class Traductor(app_commands.Translator):
    """Traduce los nombres y las ayudas de los comandos.

    Ojo con lo que decide el idioma aqui: **el de Discord de quien mira**, no
    el de la guerra. Un comando se escribe antes de que exista ninguna guerra,
    asi que no puede depender de ella; quien tenga Discord en ingles vera
    `/create-war` aunque la guerra se juegue en espanol, y los mensajes del
    bot seguiran saliendo en el idioma de la guerra.
    """

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContext,
    ) -> str | None:
        clave = string.extras.get("clave")
        if not clave:
            return None
        idioma = _idioma_de_locale(locale.value)
        if idioma is None:
            return None  # idioma que no tenemos: se queda el por defecto
        return t(clave, idioma)


class MenuAccion(discord.ui.View):
    """El menu privado de un Master: lo que puede hacer ahora mismo.

    Cada boton llama al mismo metodo del Cog que su comando equivalente.
    """

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra, master: Master) -> None:
        super().__init__(timeout=SEGUNDOS_MENU)
        self.cog = cog
        self.guerra = guerra
        self.master = master
        # De que dia es este menu. Hace falta desde que decirse listo cierra el
        # dia: un menu efimero se queda abierto en la pantalla de quien lo
        # abrio, y si otro cierra el dia mientras tanto, lo que tiene delante
        # es de ayer. Decirse listo ahi le cerraria el dia nuevo sin haberlo
        # jugado. Ver `boton_listo`.
        self.dia_del_menu = guerra.dia
        idioma = guerra.idioma

        self.boton_invocar.label = t("menu.invocar", idioma)
        self.boton_estadisticas.label = t("menu.estadisticas", idioma)
        self.boton_conocidos.label = t("menu.conocidos", idioma)
        self.boton_entrenar.label = t(
            "menu.entrenar", idioma, restantes=master.intentos_npc_restantes
        )
        self.boton_planear.label = t("menu.planear", idioma)
        self.boton_estado.label = t("menu.estado", idioma)
        self.boton_inventario.label = t(
            "menu.inventario", idioma, cuantos=master.inventario.total
        )
        self.boton_tienda.label = t("menu.tienda", idioma, oro=master.oro)
        self.boton_ultima_batalla.label = t("menu.ultima_batalla", idioma)
        self.boton_listo.label = t("menu.listo", idioma)
        self.boton_batallas.label = t("menu.batallas", idioma)
        self.boton_rendirse.label = t("menu.rendirse", idioma)
        # Rendirse no se deshace, asi que el boton pide pulsarlo dos veces:
        # el primer clic lo convierte en la pregunta y el segundo lo hace.
        # Vive en el propio boton y no en una vista aparte porque asi el
        # menu no se va a ninguna parte si cambias de idea.
        self.confirmando_rendirse = False
        # Cerrar el dia es del creador: a los demas ni se les ensena, en vez
        # de ensenarselo apagado y que parezca que les falta algo.
        if master.id != guerra.creador_id:
            self.remove_item(self.boton_batallas)
        self._refrescar()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Un menu es de quien lo abrio, aunque el mensaje sea efimero."""
        if str(interaction.user.id) == self.master.id:
            return True
        await interaction.response.send_message(
            t("menu.no_estas", self.guerra.idioma), ephemeral=True
        )
        return False

    def _refrescar(self) -> None:
        # Cualquier otro boton deshace la pregunta de rendirse: si no, el
        # "Seguro?" se quedaria puesto y el siguiente clic ahi se rendiria
        # sin preguntar.
        self.confirmando_rendirse = False
        self.boton_rendirse.label = t("menu.rendirse", self.guerra.idioma)
        self.boton_rendirse.disabled = self.master.eliminado
        self.boton_entrenar.label = t(
            "menu.entrenar",
            self.guerra.idioma,
            restantes=self.master.intentos_npc_restantes,
        )
        # Sin Servant no hay nada que hacer salvo invocarlo, y una vez
        # invocado ese boton ya no sirve para nada.
        invocado = self.master.servant is not None
        listo = self.master.listo
        self.boton_invocar.disabled = invocado
        self.boton_estadisticas.disabled = not invocado
        # El inventario se apaga vacio y lleva la cuenta en la etiqueta, que
        # es lo que te dice si vale la pena abrirlo.
        self.boton_inventario.disabled = self.master.inventario.vacio
        self.boton_inventario.label = t(
            "menu.inventario",
            self.guerra.idioma,
            cuantos=self.master.inventario.total,
        )
        # La tienda lleva el oro en la etiqueta, que es lo que te dice si vale
        # la pena abrirla. No se apaga sin oro: los catalizadores se pagan con
        # griales, y mirar los precios es parte de decidir si entrenas otra vez.
        self.boton_tienda.label = t(
            "menu.tienda", self.guerra.idioma, oro=self.master.oro
        )
        # Apagado mientras no hayas visto a nadie: es lo que te dice, de un
        # vistazo, que todavia atacas a ciegas.
        self.boton_conocidos.disabled = not self.cog.servants_conocidos(
            self.guerra, self.master
        )
        self.boton_entrenar.disabled = (
            not invocado or listo or self.master.intentos_npc_restantes <= 0
        )
        self.boton_listo.disabled = listo
        self.boton_ultima_batalla.disabled = not self.master.ultimo_registro
        # El de planear se apaga por lo mismo que el de entrenar, y ademas
        # cuando no queda nadie a quien atacar. El motivo lo decide el Cog,
        # para que el boton y el desplegable no digan cosas distintas.
        self.boton_planear.disabled = (
            self.cog.motivo_para_no_planear(self.guerra, self.master) is not None
        )
        # Si ya hay objetivo, el boton lo dice: es lo unico que te recuerda a
        # quien ibas a atacar, porque no se anuncia en ningun sitio.
        if self.master.objetivo in self.guerra.masters:
            self.boton_planear.label = t(
                "menu.planear_a",
                self.guerra.idioma,
                master=self.guerra.masters[self.master.objetivo].nombre,
            )
        if listo:
            self.boton_listo.label = t("menu.listo_hecho", self.guerra.idioma)
        # El de las batallas se enciende cuando no falta nadie **mas**: a si
        # mismo no se espera, porque pulsarlo ya es decir que acabo su dia.
        if self.boton_batallas in self.children:
            self.boton_batallas.disabled = any(
                m.id != self.master.id
                for m in self.guerra.faltan_por_estar_listos
            )

    @discord.ui.button(label="...", style=discord.ButtonStyle.success)
    async def boton_invocar(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        privado, publico = self.cog.texto_invocacion(self.guerra, self.master)
        self._refrescar()
        await interaction.response.edit_message(
            content=self.cog.cabecera_menu(self.guerra, self.master), view=self
        )
        # El arte va **solo aqui**, en lo que ve quien invoco. El mensaje del
        # canal cuenta que invoco, no a quien: ensenar el dibujo en publico
        # seria regalarle el Servant a los otros seis.
        await interaction.followup.send(
            privado,
            embed=self.cog.arte_del_servant(self.master.servant),
            ephemeral=True,
        )
        if publico:
            await interaction.followup.send(publico, ephemeral=False)

    @discord.ui.button(label="...", style=discord.ButtonStyle.primary)
    async def boton_estadisticas(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        # La ficha va en el orden que pidio Cristopher: el texto arriba (nombre,
        # clase y estadisticas), el arte debajo y el menu al final. En Discord
        # ese orden no se elige, es el de un mensaje: contenido, embeds y
        # componentes. Y lleva el menu para no dejar al Master en una pantalla
        # sin salida: desde la ficha se sigue jugando.
        await interaction.response.send_message(
            self.cog.texto_ficha(self.guerra, self.master),
            embed=self.cog.arte_del_servant(self.master.servant),
            view=MenuAccion(self.cog, self.guerra, self.master),
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.secondary)
    async def boton_conocidos(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Abre el desplegable de Servants rivales ya vistos."""
        if not self.cog.servants_conocidos(self.guerra, self.master):
            await interaction.response.send_message(
                t("conocidos.todavia_ninguno", self.guerra.idioma), ephemeral=True
            )
            return
        await interaction.response.send_message(
            t("conocidos.elige", self.guerra.idioma),
            view=VistaConocidos(self.cog, self.guerra, self.master),
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.success)
    async def boton_entrenar(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        texto = self.cog.pelear_npc(self.guerra, self.master)
        self._refrescar()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(texto, ephemeral=True)

    @discord.ui.button(label="...", style=discord.ButtonStyle.primary)
    async def boton_planear(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Abre el desplegable de rivales. No cambia nada por si solo."""
        aviso = self.cog.motivo_para_no_planear(self.guerra, self.master)
        if aviso:
            await interaction.response.send_message(aviso, ephemeral=True)
            return
        await interaction.response.send_message(
            t("bot.planear_elige", self.guerra.idioma),
            view=VistaPlanear(self.cog, self.guerra, self.master),
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.secondary)
    async def boton_estado(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            self.cog.texto_estado(self.guerra, self.master), ephemeral=True
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.secondary)
    async def boton_ultima_batalla(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            self.cog.texto_ultima_batalla(self.guerra, self.master),
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.secondary)
    async def boton_listo(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Dice que acabaste tu dia, y **cierra el dia si eras el ultimo**.

        Esta es la cuarta puerta. Antes decirse listo solo apuntaba que ya
        estabas, y el dia lo tenia que cerrar el creador con el boton rojo
        aunque no quedara nadie a quien esperar: el boton rojo ya exigia que
        todos estuvieran listos (`aviso_si_no_se_puede_cerrar`), asi que
        pulsarlo no decidia nada, solo hacia falta. Ahora, si al decirte listo
        no falta nadie, las batallas empiezan solas.

        Y por eso se comprueba el dia: si mientras tenias el menu abierto
        alguien cerro el dia, lo que tienes delante es de ayer, y decirte listo
        ahi te cerraria el dia nuevo sin haberlo jugado. Lo encontro una
        prueba, no una partida.
        """
        if self.guerra.dia != self.dia_del_menu:
            await interaction.response.send_message(
                t(
                    "menu.dia_viejo",
                    self.guerra.idioma,
                    dia=self.dia_del_menu,
                    actual=self.guerra.dia,
                ),
                ephemeral=True,
            )
            return
        privado, publico = self.cog.texto_listo(self.guerra, self.master)
        # El boton rojo sobra si el dia se va a cerrar ahora mismo, y dejarlo
        # a la vista seria ofrecer cerrar lo que ya esta cerrado.
        cerrar = self.cog.puede_cerrarse_ya(self.guerra)
        if cerrar and self.boton_batallas in self.children:
            self.remove_item(self.boton_batallas)
        self._refrescar()
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(privado, ephemeral=True)
        if publico:
            await interaction.followup.send(publico, ephemeral=False)
        if cerrar:
            await self.cog.cerrar_el_dia(
                self.guerra, self.cog.enviar_por(interaction)
            )

    @discord.ui.button(label="...", style=discord.ButtonStyle.danger)
    async def boton_batallas(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Cierra el dia ya, sin esperar la ventana de preparacion."""
        self.master.listo = True
        aviso = self.cog.aviso_si_no_se_puede_cerrar(self.guerra)
        if aviso:
            self._refrescar()
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(aviso, ephemeral=True)
            return
        # El menu se queda sin este boton: el dia que cerraba ya no existe.
        self.remove_item(self.boton_batallas)
        await interaction.response.edit_message(view=self)
        # Lo demas lo hace el Cog: narrar el cierre y dejar en el canal el
        # boton que toque (el de abrir tu batalla si hay batallas, el del dia
        # nuevo si empieza otro, ninguno si la guerra acabo). Las cuatro
        # puertas por las que se cierra un dia tienen que dejar la misma mesa,
        # asi que ninguna lo hace por su cuenta.
        await self.cog.cerrar_el_dia(self.guerra, self.cog.enviar_por(interaction))

    @discord.ui.button(label="...", style=discord.ButtonStyle.danger, row=4)
    async def boton_rendirse(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Se sale de la guerra. Pide pulsarlo dos veces.

        El primer clic solo cambia la etiqueta a la pregunta; el segundo lo
        hace. No hay vuelta atras y no es lo mismo que terminar la guerra:
        esta sigue para los demas, y si solo queda uno, ese gana (pero sin
        Grial, ver `Guerra.gana_el_grial`).

        Cambiar de idea es pulsar un boton que reescriba el menu (invocar,
        entrenar, listo): todos pasan por `_refrescar`, que deshace la
        pregunta. Los que solo mandan un mensaje aparte (el estado, el
        inventario) no la deshacen, y esta bien: la etiqueta sigue diciendo
        "Pulsa otra vez" en la pantalla de quien lo tiene delante, asi que lo
        que se ve y lo que pasa son la misma cosa.
        """
        if not self.confirmando_rendirse:
            self._refrescar()
            self.confirmando_rendirse = True
            boton.label = t("menu.rendirse_seguro", self.guerra.idioma)
            await interaction.response.edit_message(view=self)
            return
        privado, publico = self.cog.rendir_al_master(self.guerra, self.master)
        # El menu se apaga entero: ya no hay nada que hacer en esta guerra.
        for hijo in self.children:
            hijo.disabled = True
        self.stop()
        await interaction.response.edit_message(content=privado, view=self)
        await interaction.followup.send(publico, ephemeral=False)
        # Si se fue el ultimo que faltaba, el dia tiene que poder cerrarse;
        # y si la guerra acabo, `cerrar_el_dia` no hace nada.
        if not self.guerra.terminada and self.cog.puede_cerrarse_ya(self.guerra):
            await self.cog.cerrar_el_dia(
                self.guerra, self.cog.enviar_por(interaction)
            )

    @discord.ui.button(label="...", style=discord.ButtonStyle.secondary)
    async def boton_inventario(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Ensena lo que lleva, y deja usar lo que sirva ahora mismo.

        La lista entera siempre, aunque no se pueda usar nada: saber que
        tienes un elixir guardado es parte de decidir si entras a la batalla.
        El desplegable solo aparece si hay algo usable.
        """
        usables = self.cog.objetos_usables_ahora(self.guerra, self.master)
        vista = (
            VistaInventario(self.cog, self.guerra, self.master) if usables else None
        )
        await interaction.response.send_message(
            self.cog.texto_inventario(self.guerra, self.master),
            view=vista,
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.success)
    async def boton_tienda(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Abre la tienda. El escaparate siempre, los botones si se puede comprar.

        Igual que el inventario: ver lo que hay y a cuanto es parte de decidir
        si merece la pena entrenar otra vez, asi que el texto se ensena aunque
        no se pueda comprar nada ahora mismo.
        """
        aviso = self.cog.motivo_para_no_comprar(self.guerra, self.master)
        texto = self.cog.texto_tienda(self.guerra, self.master)
        if aviso:
            await interaction.response.send_message(
                f"{aviso}\n\n{texto}", ephemeral=True
            )
            return
        await interaction.response.send_message(
            texto,
            view=VistaTienda(self.cog, self.guerra, self.master),
            ephemeral=True,
        )


class VistaPlanear(discord.ui.View):
    """El desplegable para elegir a quien atacar hoy.

    Se abre desde el menu y es otro mensaje efimero, porque un desplegable
    ocupa una fila entera y el menu ya va lleno de botones.

    Las opciones las arma el Cog (`opciones_de_ataque`), no esta clase: lo que
    se ve de cada rival depende de si se ha peleado con el, y esa regla no
    puede vivir en dos sitios.
    """

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra, master: Master) -> None:
        super().__init__(timeout=SEGUNDOS_MENU)
        self.cog = cog
        self.guerra = guerra
        self.master = master
        self.selector = discord.ui.Select(
            placeholder=t("bot.planear_placeholder", guerra.idioma),
            options=[
                discord.SelectOption(
                    label=etiqueta_, value=id_, description=descripcion, default=actual
                )
                for id_, etiqueta_, descripcion, actual in cog.opciones_de_ataque(
                    guerra, master
                )
            ],
        )
        self.selector.callback = self._elegido
        self.add_item(self.selector)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) == self.master.id:
            return True
        await interaction.response.send_message(
            t("menu.no_estas", self.guerra.idioma), ephemeral=True
        )
        return False

    async def _elegido(self, interaction: discord.Interaction) -> None:
        await self.elegir(interaction, self.selector.values[0])

    async def elegir(self, interaction: discord.Interaction, objetivo: str) -> None:
        """Lo que pasa al elegir un rival, aparte de como se eligio.

        Separado del callback a proposito: asi se puede probar sin tener que
        falsear por dentro el desplegable de discord.py.
        """
        texto = self.cog.texto_planear(self.guerra, self.master, objetivo)
        # El desplegable se va con la respuesta: el objetivo ya esta puesto y
        # para cambiarlo se vuelve a abrir desde el menu, que es donde dice a
        # quien estas atacando.
        await interaction.response.edit_message(content=texto, view=None)


class VistaObjetivo(discord.ui.View):
    """Un desplegable de objetivos para una accion ya elegida.

    Sirve para las tres cosas que necesitan apuntar a alguien: atacar, el
    Noble Fantasma y el objetivo de una habilidad. Las opciones y lo que pasa
    al elegir los trae quien la abre, porque eso depende de la accion; lo que
    esta clase sabe es ensenar la lista y comprobar que quien pulsa es quien
    la abrio.
    """

    def __init__(
        self,
        guerra: Guerra,
        master: Master,
        opciones: list[tuple[str, str, str]],
        hacer,
        placeholder: str,
    ) -> None:
        super().__init__(timeout=SEGUNDOS_MENU)
        self.guerra = guerra
        self.master = master
        self.hacer = hacer
        self.selector = discord.ui.Select(
            placeholder=placeholder,
            options=[
                discord.SelectOption(label=etiqueta_, value=valor, description=desc)
                for valor, etiqueta_, desc in opciones
            ],
        )
        self.selector.callback = self._elegido
        self.add_item(self.selector)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) == self.master.id:
            return True
        await interaction.response.send_message(
            t("menu.no_estas", self.guerra.idioma), ephemeral=True
        )
        return False

    async def _elegido(self, interaction: discord.Interaction) -> None:
        await self.elegir(interaction, self.selector.values[0])

    async def elegir(self, interaction: discord.Interaction, valor: str) -> None:
        """Separado del callback para poder probarlo sin falsear el Select."""
        await self.hacer(interaction, valor)


class MenuCombate(discord.ui.View):
    """El menu privado de una batalla en curso: lo que puedes hacer este turno.

    Es el sitio donde se juega, y es privado por lo mismo que el registro de
    una batalla: las frases nombran las habilidades, y el nombre de una
    habilidad delata al Servant. Dentro de una batalla si se ven los Servants
    de los rivales, porque estar delante es justo lo que los destapa.

    **No se refresca solo.** Los turnos se resuelven cuando el ultimo decide,
    y Discord no deja empujar un mensaje efimero de otra persona, asi que hay
    un boton de refrescar. Quien cierra el turno ve el resultado al momento;
    los demas, al refrescar.
    """

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra, master: Master) -> None:
        super().__init__(timeout=SEGUNDOS_MENU)
        self.cog = cog
        self.guerra = guerra
        self.master = master
        idioma = guerra.idioma
        self.boton_atacar.label = t("combate.boton_atacar", idioma)
        self.boton_defender.label = t("combate.boton_defender", idioma)
        self.boton_habilidad.label = t("combate.boton_habilidad", idioma)
        self.boton_np.label = t("combate.boton_np", idioma)
        self.boton_seguir.label = t("combate.boton_seguir", idioma)
        self.boton_parar.label = t("combate.boton_parar", idioma)
        self.boton_refrescar.label = t("combate.boton_refrescar", idioma)
        self.boton_registro.label = t("combate.boton_registro", idioma)
        self.boton_objeto.label = t("combate.objeto", idioma)
        self.boton_sello.label = t("combate.sello", idioma)
        self.refrescar()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) == self.master.id:
            # Cada vez que tocas tu menu, el Cog se queda con por donde
            # hablarte: es lo que le deja contarte el turno que cierre otro.
            # Va aqui porque por aqui pasan **todos** los botones del menu, y
            # asi no hay forma de olvidarlo en uno.
            self.cog.apuntar_mesa(interaction, self.guerra, self.master, self)
            return True
        await interaction.response.send_message(
            t("menu.no_estas", self.guerra.idioma), ephemeral=True
        )
        return False

    def refrescar(self) -> None:
        """Deja a la vista los botones que valen ahora y apaga el resto.

        Los de pelear y los de votar no se ensenan juntos: una votacion no es
        un turno, y un boton que no significa nada todavia solo despista.

        No lleva guion bajo porque **se llama desde fuera**: cuando otro cierra
        el turno, el Cog le reescribe el menu a cada uno (`_avisar_del_turno`),
        y para eso tiene que poder refrescarlo.
        """
        combate = self.cog.combate_de(self.guerra, self.master)
        votando = combate is not None and combate.espera is combate_mod.Espera.VOTACION
        de_pelea = (
            self.boton_atacar,
            self.boton_defender,
            self.boton_habilidad,
            self.boton_np,
        )
        de_voto = (self.boton_seguir, self.boton_parar)
        for boton in de_voto if not votando else de_pelea:
            if boton in self.children:
                self.remove_item(boton)
        for boton in de_pelea if not votando else de_voto:
            if boton not in self.children:
                self.add_item(boton)

        puede = self.cog.motivo_para_no_decidir(self.guerra, self.master) is None
        acciones = self.cog.acciones_posibles(self.guerra, self.master)
        for boton, accion in (
            (self.boton_atacar, Accion.ATACAR),
            (self.boton_defender, Accion.DEFENDER),
            (self.boton_habilidad, Accion.HABILIDAD),
            (self.boton_np, Accion.NOBLE_FANTASMA),
        ):
            if boton in self.children:
                boton.disabled = not puede or accion not in acciones
        for boton in de_voto:
            if boton in self.children:
                boton.disabled = not puede
        self.boton_registro.disabled = combate is None
        # El de objetos no depende de que te toque decidir: usar uno no es tu
        # accion del turno. Depende de que lleves alguno de combate y de que
        # no hayas gastado el de esta batalla.
        self.boton_objeto.disabled = not self.cog.objetos_de_combate(
            self.guerra, self.master
        )
        # Y el de los Sellos, por lo mismo: gastar uno no es tu accion del
        # turno, asi que sigue encendido aunque ya hayas decidido.
        self.boton_sello.disabled = not self.cog.usos_de_sello(
            self.guerra, self.master
        )

    async def _responder(self, interaction: discord.Interaction, texto: str) -> None:
        """Deja el menu al dia y cuenta lo que paso, en privado.

        El menu se reescribe siempre: elegir cambia lo que se puede hacer, y
        un turno que se resuelve cambia la vida de todo el mundo.
        """
        self.refrescar()
        await interaction.response.edit_message(
            content=self.cog.texto_combate(self.guerra, self.master), view=self
        )
        if texto:
            await interaction.followup.send(texto, ephemeral=True)
        await self.cog.despues_de_decidir(interaction, self.guerra, self.master)

    async def _elegir_objetivo(
        self, interaction: discord.Interaction, accion: Accion
    ) -> None:
        """Pide el rival para atacar o para el Noble Fantasma.

        **En un duelo no pregunta nada**: si solo queda un rival en pie,
        elegirlo no es una decision, es un clic de mas. El desplegable sale
        cuando hay de verdad a quien elegir.
        """
        aviso = self.cog.motivo_para_no_decidir(self.guerra, self.master)
        if aviso:
            await interaction.response.send_message(aviso, ephemeral=True)
            return
        opciones = self.cog.opciones_de_objetivo(self.guerra, self.master)
        if not opciones:
            await interaction.response.send_message(
                t("combate.no_te_toca", self.guerra.idioma), ephemeral=True
            )
            return
        if len(opciones) == 1:
            texto = self.cog.decidir_en_combate(
                self.guerra,
                self.master,
                Decision(accion=accion, objetivo=opciones[0][0]),
            )
            await self._responder(interaction, texto)
            return

        async def hacer(inter: discord.Interaction, valor: str) -> None:
            texto = self.cog.decidir_en_combate(
                self.guerra, self.master, Decision(accion=accion, objetivo=valor)
            )
            await inter.response.edit_message(content=texto, view=None)
            await self.cog.despues_de_decidir(inter, self.guerra, self.master)

        await interaction.response.send_message(
            t("combate.elige_objetivo", self.guerra.idioma),
            view=VistaObjetivo(
                self.guerra,
                self.master,
                opciones,
                hacer,
                t("combate.placeholder_objetivo", self.guerra.idioma),
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.success, row=2)
    async def boton_objeto(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Usa un objeto. **No gasta el turno**, asi que no decide nada.

        Por eso despues de usarlo el menu sigue pidiendote tu accion, y por
        eso este boton funciona tambien cuando ya decidiste: lo unico que te
        lo apaga es no llevar ninguno o haber gastado el de esta batalla.
        """
        opciones = self.cog.objetos_de_combate(self.guerra, self.master)
        if not opciones:
            await interaction.response.send_message(
                t("inventario.nada_que_usar", self.guerra.idioma), ephemeral=True
            )
            return

        async def hacer(inter: discord.Interaction, clave: str) -> None:
            texto = self.cog.usar_objeto_en_combate(self.guerra, self.master, clave)
            await inter.response.edit_message(content=texto, view=None)

        await interaction.response.send_message(
            t("inventario.placeholder", self.guerra.idioma),
            view=VistaObjetivo(
                self.guerra,
                self.master,
                [
                    (
                        o.clave,
                        f"{o.nombre_para(self.guerra.idioma)} x{n}",
                        o.descripcion(self.guerra.idioma)[:100],
                    )
                    for o, n in opciones
                ],
                hacer,
                t("inventario.placeholder", self.guerra.idioma),
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.success, row=2)
    async def boton_sello(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Gasta un Sello de Comando. **No gasta el turno**, como el objeto.

        No pide confirmar dos veces, al contrario que rendirse, porque los tres
        usos se leen en el desplegable y elegir uno ya es la confirmacion:
        abrirlo y cerrarlo no gasta nada.
        """
        opciones = self.cog.usos_de_sello(self.guerra, self.master)
        if not opciones:
            aviso = (
                t("sello.sin_sellos", self.guerra.idioma)
                if self.master.sellos <= 0
                else t("sello.ya_en_esta_batalla", self.guerra.idioma)
            )
            await interaction.response.send_message(aviso, ephemeral=True)
            return

        async def hacer(inter: discord.Interaction, clave: str) -> None:
            texto = self.cog.usar_sello_en_combate(self.guerra, self.master, clave)
            await inter.response.edit_message(content=texto, view=None)

        await interaction.response.send_message(
            t("combate.elige_sello", self.guerra.idioma),
            view=VistaObjetivo(
                self.guerra,
                self.master,
                [
                    (
                        s.clave,
                        s.nombre_para(self.guerra.idioma),
                        s.descripcion(self.guerra.idioma)[:100],
                    )
                    for s in opciones
                ],
                hacer,
                t("combate.placeholder_sello", self.guerra.idioma),
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.danger)
    async def boton_atacar(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        await self._elegir_objetivo(interaction, Accion.ATACAR)

    @discord.ui.button(label="...", style=discord.ButtonStyle.secondary)
    async def boton_defender(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        texto = self.cog.decidir_en_combate(
            self.guerra, self.master, Decision(accion=Accion.DEFENDER)
        )
        await self._responder(interaction, texto)

    @discord.ui.button(label="...", style=discord.ButtonStyle.primary)
    async def boton_habilidad(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        """Dos pasos: primero cual, luego sobre quien.

        Dos desplegables y no uno porque los objetivos dependen de la
        habilidad: una que va "a otro" no se puede usar sobre uno mismo.
        """
        aviso = self.cog.motivo_para_no_decidir(self.guerra, self.master)
        if aviso:
            await interaction.response.send_message(aviso, ephemeral=True)
            return
        opciones = self.cog.opciones_de_habilidad(self.guerra, self.master)
        if not opciones:
            await interaction.response.send_message(
                t("combate.sin_habilidades", self.guerra.idioma), ephemeral=True
            )
            return

        async def elegida(inter: discord.Interaction, valor: str) -> None:
            numero = int(valor)
            objetivos = self.cog.opciones_de_objetivo_de_habilidad(
                self.guerra, self.master, numero
            )

            def decidir(destino: str) -> str:
                return self.cog.decidir_en_combate(
                    self.guerra,
                    self.master,
                    Decision(
                        accion=Accion.HABILIDAD, objetivo=destino, habilidad=numero
                    ),
                )

            async def hacer(inter2: discord.Interaction, destino: str) -> None:
                await inter2.response.edit_message(
                    content=decidir(destino), view=None
                )
                await self.cog.despues_de_decidir(inter2, self.guerra, self.master)

            # Una habilidad que solo puede ir a un sitio (a uno mismo, o al
            # unico rival que queda) no pregunta a donde va.
            if len(objetivos) == 1:
                await inter.response.edit_message(
                    content=decidir(objetivos[0][0]), view=None
                )
                await self.cog.despues_de_decidir(inter, self.guerra, self.master)
                return

            await inter.response.edit_message(
                content=t(
                    "combate.habilidad_sobre",
                    self.guerra.idioma,
                    habilidad=self.cog.nombre_de_habilidad(
                        self.guerra, self.master, numero
                    ),
                ),
                view=VistaObjetivo(
                    self.guerra,
                    self.master,
                    objetivos,
                    hacer,
                    t("combate.placeholder_objetivo", self.guerra.idioma),
                ),
            )

        await interaction.response.send_message(
            t("combate.elige_habilidad", self.guerra.idioma),
            view=VistaObjetivo(
                self.guerra,
                self.master,
                opciones,
                elegida,
                t("combate.placeholder_habilidad", self.guerra.idioma),
            ),
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.danger)
    async def boton_np(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        await self._elegir_objetivo(interaction, Accion.NOBLE_FANTASMA)

    @discord.ui.button(label="...", style=discord.ButtonStyle.success)
    async def boton_seguir(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        texto = self.cog.votar_en_combate(self.guerra, self.master, True)
        await self._responder(interaction, texto)

    @discord.ui.button(label="...", style=discord.ButtonStyle.secondary)
    async def boton_parar(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        texto = self.cog.votar_en_combate(self.guerra, self.master, False)
        await self._responder(interaction, texto)

    @discord.ui.button(label="...", style=discord.ButtonStyle.primary)
    async def boton_refrescar(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        await self._responder(interaction, "")

    @discord.ui.button(label="...", style=discord.ButtonStyle.secondary)
    async def boton_registro(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        await interaction.response.send_message(
            self.cog.texto_registro_del_combate(self.guerra, self.master),
            ephemeral=True,
        )


class AbrirCombate(discord.ui.View):
    """El boton publico del canal para abrir tu batalla, en privado.

    Igual que `AbrirMenu` y por lo mismo: el aviso es publico, lo que ensena
    no lo es. No caduca, porque una batalla puede tardar lo que tarde la gente
    en volver a Discord.
    """

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.guerra = guerra
        self.boton.label = t("combate.abrir", guerra.idioma)

    @discord.ui.button(label="...", style=discord.ButtonStyle.danger)
    async def boton(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        master = self.guerra.masters.get(str(interaction.user.id))
        if master is None:
            await interaction.response.send_message(
                t("menu.no_estas", self.guerra.idioma), ephemeral=True
            )
            return
        if self.cog.combate_de(self.guerra, master) is None:
            await interaction.response.send_message(
                t("combate.sin_combate", self.guerra.idioma), ephemeral=True
            )
            return
        vista = MenuCombate(self.cog, self.guerra, master)
        await interaction.response.send_message(
            self.cog.texto_combate(self.guerra, master),
            view=vista,
            ephemeral=True,
        )
        # Y se apunta ya, sin esperar a que toque un boton: el que abre su
        # combate y se queda mirando tambien tiene que ver el turno que cierre
        # otro. Este es el caso del fallo que conto Cristopher.
        self.cog.apuntar_mesa(interaction, self.guerra, master, vista)


class VistaInventario(discord.ui.View):
    """El desplegable para usar un objeto durante la preparacion.

    Solo lista lo que se puede usar **ahora**: lo que el Cog diga en
    `objetos_usables_ahora`, que es donde vive esa regla. Lo demas se ve en el
    texto del inventario pero no se puede elegir, para que elegir no sea
    adivinar si servia.
    """

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra, master: Master) -> None:
        super().__init__(timeout=SEGUNDOS_MENU)
        self.cog = cog
        self.guerra = guerra
        self.master = master
        self.selector = discord.ui.Select(
            placeholder=t("inventario.placeholder", guerra.idioma),
            options=[
                discord.SelectOption(
                    label=f"{o.nombre_para(guerra.idioma)} x{n}",
                    value=o.clave,
                    description=o.descripcion(guerra.idioma)[:100],
                )
                for o, n in cog.objetos_usables_ahora(guerra, master)
            ],
        )
        self.selector.callback = self._elegido
        self.add_item(self.selector)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) == self.master.id:
            return True
        await interaction.response.send_message(
            t("menu.no_estas", self.guerra.idioma), ephemeral=True
        )
        return False

    async def _elegido(self, interaction: discord.Interaction) -> None:
        await self.usar(interaction, self.selector.values[0])

    async def usar(self, interaction: discord.Interaction, clave: str) -> None:
        """Lo que pasa al elegir, aparte de como se eligio.

        El mensaje es privado: lo que llevas y lo que gastas es tuyo, y
        anunciarlo en el canal le diria a los demas con que vas a la batalla.
        """
        texto = self.cog.usar_objeto_en_preparacion(self.guerra, self.master, clave)
        await interaction.response.send_message(texto, ephemeral=True)


class ModalServant(discord.ui.Modal):
    """Donde se escribe el nombre del Servant de un catalizador.

    Es un formulario y no un desplegable porque **son 348** y un desplegable
    de Discord aguanta 25 opciones. Escribirlo tiene una ventaja: ya sabes a
    quien quieres, no estas mirando una lista.
    """

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra, master: Master) -> None:
        super().__init__(title=t("tienda.buscar_titulo", guerra.idioma))
        self.cog = cog
        self.guerra = guerra
        self.master = master
        self.campo = discord.ui.TextInput(
            label=t("tienda.buscar_campo", guerra.idioma),
            placeholder=t("tienda.buscar_ayuda", guerra.idioma),
            max_length=60,
        )
        self.add_item(self.campo)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            self.cog.comprar_catalizador_de_servant(
                self.guerra, self.master, str(self.campo.value)
            ),
            ephemeral=True,
        )


class VistaTienda(discord.ui.View):
    """La tienda: un desplegable por moneda y un boton para el formulario.

    Tres filas porque son tres compras distintas y mezclarlas seria pedir un
    error caro: el oro se gasta en esta guerra y los griales son de la cuenta,
    y pagar 5 griales por error no se deshace.
    """

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra, master: Master) -> None:
        super().__init__(timeout=SEGUNDOS_MENU)
        self.cog = cog
        self.guerra = guerra
        self.master = master
        idioma = guerra.idioma

        self.selector_oro = discord.ui.Select(
            placeholder=t("tienda.placeholder_oro", idioma),
            options=[
                discord.SelectOption(
                    label=o.nombre_para(idioma),
                    value=o.clave,
                    description=t(
                        "tienda.opcion_oro",
                        idioma,
                        precio=tienda.precio_de(o)[0],
                    )
                    + f" - {o.descripcion(idioma)}"[:100],
                )
                for o in tienda.a_la_venta()
            ],
            row=0,
        )
        self.selector_oro.callback = self._elegido_oro
        self.add_item(self.selector_oro)

        self.selector_clase = discord.ui.Select(
            placeholder=t(
                "tienda.placeholder_clase",
                idioma,
                precio=tienda.PRECIO_CATALIZADOR_CLASE,
            ),
            options=[
                discord.SelectOption(
                    label=objetos.catalizador_de_clase(c).nombre_para(idioma),
                    value=c.value,
                )
                for c in Clase
                if objetos.catalizador_de_clase(c) is not None
            ],
            row=1,
        )
        self.selector_clase.callback = self._elegida_clase
        self.add_item(self.selector_clase)

        self.boton_servant.label = t(
            "tienda.boton_servant", idioma, precio=tienda.PRECIO_CATALIZADOR_SERVANT
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) == self.master.id:
            return True
        await interaction.response.send_message(
            t("menu.no_estas", self.guerra.idioma), ephemeral=True
        )
        return False

    async def _elegido_oro(self, interaction: discord.Interaction) -> None:
        await self.comprar_oro(interaction, self.selector_oro.values[0])

    async def _elegida_clase(self, interaction: discord.Interaction) -> None:
        await self.comprar_clase(interaction, self.selector_clase.values[0])

    async def comprar_oro(self, interaction: discord.Interaction, clave: str) -> None:
        """Lo que pasa al elegir, aparte de como se eligio. Privado siempre:
        lo que compras es con lo que vas a ir a la batalla."""
        await interaction.response.send_message(
            self.cog.comprar_con_oro(self.guerra, self.master, clave), ephemeral=True
        )

    async def comprar_clase(self, interaction: discord.Interaction, clase: str) -> None:
        await interaction.response.send_message(
            self.cog.comprar_catalizador_de_clase(self.guerra, self.master, clase),
            ephemeral=True,
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.primary, row=2)
    async def boton_servant(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        await interaction.response.send_modal(
            ModalServant(self.cog, self.guerra, self.master)
        )


class VistaConocidos(discord.ui.View):
    """El desplegable de los Servants rivales que ya has visto pelear.

    Otro mensaje efimero, por lo mismo que `VistaPlanear`: un desplegable
    ocupa una fila y el menu ya va lleno. Y efimero tambien por la regla del
    secreto: lo que tu sabes de los demas es tuyo, y publicarlo en el canal se
    lo regalaria a quien no ha peleado con nadie.

    Las opciones las arma el Cog (`servants_conocidos`), que es donde vive la
    regla de quien ve que.
    """

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra, master: Master) -> None:
        super().__init__(timeout=SEGUNDOS_MENU)
        self.cog = cog
        self.guerra = guerra
        self.master = master
        self.selector = discord.ui.Select(
            placeholder=t("conocidos.placeholder", guerra.idioma),
            options=[
                discord.SelectOption(label=servant, value=id_, description=nombre)
                for id_, nombre, servant in cog.servants_conocidos(guerra, master)
            ],
        )
        self.selector.callback = self._elegido
        self.add_item(self.selector)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) == self.master.id:
            return True
        await interaction.response.send_message(
            t("menu.no_estas", self.guerra.idioma), ephemeral=True
        )
        return False

    async def _elegido(self, interaction: discord.Interaction) -> None:
        await self.mostrar(interaction, self.selector.values[0])

    async def mostrar(self, interaction: discord.Interaction, id_: str) -> None:
        """Lo que pasa al elegir, aparte de como se eligio.

        Separado del callback para poder probarlo sin falsear por dentro el
        desplegable de discord.py, igual que en `VistaPlanear`.
        """
        texto, arte = self.cog.ficha_del_conocido(self.guerra, self.master, id_)
        await interaction.response.send_message(
            texto, embed=arte, ephemeral=True
        )


class ConfirmarTerminar(discord.ui.View):
    """Pregunta en privado antes de cerrar la guerra a mano.

    Terminar una guerra no se deshace: se acaba la partida de siete personas
    y nadie gana. Un comando suelto se escribe sin querer, asi que entre el
    comando y el final hay un boton rojo. Caduca, y caducar es no hacer nada.
    """

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra) -> None:
        super().__init__(timeout=SEGUNDOS_MENU)
        self.cog = cog
        self.guerra = guerra
        self.boton_terminar.label = t("terminar.confirmar", guerra.idioma)
        self.boton_cancelar.label = t("terminar.mejor_no", guerra.idioma)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) == self.guerra.creador_id:
            return True
        await interaction.response.send_message(
            t("bot.solo_el_creador_termina", self.guerra.idioma), ephemeral=True
        )
        return False

    @discord.ui.button(label="...", style=discord.ButtonStyle.danger)
    async def boton_terminar(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        # El mensaje privado se apaga y el final se cuenta en el canal: la
        # guerra es de todos, asi que todos tienen que enterarse.
        for hijo in self.children:
            hijo.disabled = True
        self.stop()
        aviso = self.cog.terminar_guerra(self.guerra)
        if aviso is not None:
            await interaction.response.edit_message(content=aviso, view=None)
            return
        await interaction.response.edit_message(
            content=t("terminar.hecho", self.guerra.idioma), view=None
        )
        await interaction.followup.send(
            self.cog.aviso_del_final(self.guerra), ephemeral=False
        )

    @discord.ui.button(label="...", style=discord.ButtonStyle.secondary)
    async def boton_cancelar(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.edit_message(
            content=t("terminar.sigue", self.guerra.idioma), view=None
        )


class AbrirMenu(discord.ui.View):
    """El boton publico del canal. Cada quien abre el suyo, en privado."""

    def __init__(self, cog: "ComandosGuerra", guerra: Guerra) -> None:
        super().__init__(timeout=None)
        self.cog = cog
        self.guerra = guerra
        self.boton.label = t("menu.abrir", guerra.idioma)

    @discord.ui.button(label="...", style=discord.ButtonStyle.primary)
    async def boton(
        self, interaction: discord.Interaction, boton: discord.ui.Button
    ) -> None:
        # Aqui no se exige Servant: el menu es justo por donde se invoca.
        master = self.guerra.masters.get(str(interaction.user.id))
        if master is None:
            await interaction.response.send_message(
                t("menu.no_estas", self.guerra.idioma), ephemeral=True
            )
            return
        await interaction.response.send_message(
            self.cog.cabecera_menu(self.guerra, master),
            view=MenuAccion(self.cog, self.guerra, master),
            ephemeral=True,
        )


class ComandosGuerra(commands.Cog):
    def __init__(
        self, bot: commands.Bot, conexion: sqlite3.Connection | None = None
    ) -> None:
        self.bot = bot
        self.guerras: dict[int, Guerra] = {}  # canal_id -> Guerra
        # Las batallas en curso, por guerra. **Viven en memoria y solo
        # mientras se juegan**, al contrario que los plazos: una batalla dura
        # minutos y una guerra dias, y si el bot se reinicia a media batalla
        # el vigilante la acaba con la IA, que es lo mismo que hacia antes de
        # que existiera este menu. Ver docs/decisiones.md.
        self.combates: dict[str, dia.CombatesDelDia] = {}  # guerra.id -> estado
        # Las cuentas de griales, por usuario. **No son de ninguna guerra**:
        # se leen de la tabla `cuentas` la primera vez que alguien abre la
        # tienda y se quedan aqui. Ver `cuenta_de`.
        self.cuentas: dict[str, tienda.Cuenta] = {}
        # Por donde hablarle a cada persona que esta peleando ahora mismo:
        # (guerra.id, master.id) -> (su ultima interaccion, su menu). Es lo que
        # permite contarle el turno a quien no lo cerro. Vive en memoria y dura
        # lo que la batalla, igual que `self.combates`. Ver `apuntar_mesa`.
        self.mesas: dict[tuple[str, str], tuple[object, object]] = {}
        # El turno que se acaba de resolver y todavia no se ha repartido, por
        # guerra. Lo deja `_cola_del_turno` y lo recoge `repartir_el_turno`.
        self.turnos_por_repartir: dict[str, list[str]] = {}
        self.rng = random.Random()
        self.vigilante = Vigilante(self)
        # Sin conexion el Cog funciona igual pero no guarda nada. Es lo que
        # usan las pruebas que no van de persistencia.
        self.conexion = conexion

    async def cog_load(self) -> None:
        if self.conexion is not None:
            self.guerras = repositorio.cargar_todas(self.conexion, CATALOGO)
            if self.guerras:
                registro.info(
                    "guerras retomadas: %s",
                    ", ".join(str(c) for c in self.guerras),
                )
        self.vigilante.arrancar()

    async def cog_unload(self) -> None:
        self.vigilante.parar()

    def guardar(self, guerra: Guerra) -> None:
        """Guarda la guerra, si hay donde.

        Se llama al final de **cada** accion que cambia algo: invocar,
        entrenar, marcar listo, cerrar el dia. Si anades una accion nueva,
        acuerdate de llamarla, porque nada te va a avisar.
        """
        if self.conexion is None:
            return
        try:
            repositorio.guardar(self.conexion, guerra)
        except sqlite3.Error:
            # Que no se pueda guardar no puede romperle la partida a nadie:
            # la guerra sigue viva en memoria y el jugador ve su resultado.
            registro.exception("no pude guardar la guerra %s", guerra.id)

    # --- lo que hace cada accion, compartido por comandos y botones ---

    def _guerra(self, canal_id: int) -> Guerra | None:
        return self.guerras.get(canal_id)

    def _idioma(
        self, interaction: discord.Interaction, guerra: Guerra | None = None
    ) -> str:
        """El idioma de la guerra del canal; sin guerra, el de quien escribe."""
        if guerra is not None:
            return guerra.idioma
        return idioma_de_discord(interaction) or IDIOMA_POR_DEFECTO

    def cabecera_menu(self, guerra: Guerra, master: Master) -> str:
        if master.servant is None:
            return t("menu.cabecera_sin_invocar", guerra.idioma, dia=guerra.dia)
        return t(
            "menu.cabecera",
            guerra.idioma,
            servant=master.servant.nombre,
            clase=master.servant.clase.value,
            nivel=master.servant.nivel,
            dia=guerra.dia,
        )

    def texto_listo(self, guerra: Guerra, master: Master) -> tuple[str, str | None]:
        """Marca que ese Master acabo su dia. Devuelve (lo suyo, lo del canal).

        Es lo que deja al creador cerrar el dia: mientras falte alguien, el
        boton de las batallas no hace nada. Que sea publico es a proposito,
        para que se vea por quien se espera.
        """
        idioma = guerra.idioma
        if master.listo:
            return t("bot.listo_ya_estabas", idioma), None
        master.listo = True
        faltan = guerra.faltan_por_estar_listos
        publico = t(
            "bot.listo_publico" if faltan else "bot.listo_todos",
            idioma,
            master=master.nombre,
            faltan=", ".join(m.nombre for m in faltan),
        )
        self.guardar(guerra)
        return t("bot.listo_hecho", idioma), publico

    def texto_invocacion(self, guerra: Guerra, master: Master) -> tuple[str, str | None]:
        """Invoca el Servant de un Master y devuelve (lo suyo, lo del canal).

        Lo segundo es `None` cuando no hay nada que anunciar, o sea cuando no
        se invoco nada.
        """
        idioma = guerra.idioma
        if master.servant is not None:
            return (
                t("bot.ya_invocaste", idioma, servant=master.servant.nombre),
                None,
            )
        try:
            servant = guerra.invocar_para(master.id, self.rng)
        except RuntimeError as e:
            return str(e), None
        faltan = len(guerra.sin_invocar)
        # Se anuncia que invoco, no a quien: el canal lo lee cualquiera.
        publico = t(
            "bot.invocacion_publica" if faltan else "bot.invocacion_ultima",
            idioma,
            master=master.nombre,
            faltan=faltan,
        )
        privado = t(
            "bot.invocacion_hecha",
            idioma,
            servant=servant.nombre,
            clase=servant.clase.value,
            sellos=master.sellos,
        )
        self.guardar(guerra)
        return privado, publico

    def texto_noble_fantasma(self, guerra: Guerra, master: Master) -> str:
        """El Noble Fantasma y lo que hace.

        El rango y el tipo salen de los datos; lo que hace sale de nuestras
        reglas, no de FGO, porque aqui todos pegan igual: x3 a un objetivo,
        tantas veces como junte el mana que cueste segun su rasgo.
        """
        idioma = guerra.idioma
        np = master.servant.noble_fantasma
        if not np:
            return t("ficha.sin_noble_fantasma", idioma)
        efecto = t(
            "ficha.np_efecto",
            idioma,
            multiplicador=f"{MULTIPLICADOR_NOBLE_FANTASMA:g}",
            costo=master.servant.rasgo.costo_noble_fantasma,
        )
        # El tipo (Anti-Army, Anti-Fortress) esta en los datos pero no se
        # ensena: fuera de quien conoce la serie no dice nada. Se guarda
        # porque es por donde empezara cada Noble Fantasma a tener su propio
        # efecto, cuando lo tengan.
        # Siete personajes traen el nombre tapado con interrogantes en los
        # datos de Atlas, porque en FGO es un secreto de la historia. Lo
        # tienen y lo lanzan igual; lo que no se ensena es "??? (rango ？)".
        if not np.nombre:
            return t("ficha.noble_fantasma_oculto", idioma, efecto=efecto)
        clave = (
            "ficha.noble_fantasma"
            if np.rango
            else "ficha.noble_fantasma_simple"
        )
        return t(
            clave,
            idioma,
            nombre=np.nombre_para(idioma),
            rango=np.rango,
            efecto=efecto,
        )

    def texto_ficha(self, guerra: Guerra, master: Master) -> str:
        idioma = guerra.idioma
        s = master.servant
        # Las tres, tambien las que no tiene todavia: un Master quiere saber
        # lo que le viene, no solo lo que tiene.
        lineas = [
            t(
                "bot.ficha_habilidad" if abierta else "bot.ficha_habilidad_bloqueada",
                idioma,
                numero=numero,
                nombre=h.nombre_para(idioma),
                descripcion=h.descripcion(idioma),
                nivel=s.nivel_de_habilidad(numero),
            )
            for numero, h, abierta in s.todas_las_habilidades
            if h.nombre
        ]
        habilidades = (
            "\n" + "\n".join(lineas)
            if lineas
            else t("bot.ficha_sin_habilidades", idioma)
        )
        return t(
            "bot.ficha",
            idioma,
            servant=s.nombre,
            clase=s.clase.value,
            nivel=s.nivel,
            vida=s.vida_maxima,
            ataque=s.ataque,
            velocidad=s.velocidad,
            xp=s.xp,
            xp_para_subir=xp_para_subir(s.nivel),
            noble_fantasma=self.texto_noble_fantasma(guerra, master),
            desbloqueadas=s.habilidades_desbloqueadas,
            habilidades=habilidades,
            rasgo=s.rasgo.texto(idioma) or t("bot.ficha_sin_rasgo", idioma),
            intentos=master.intentos_npc,
            por_dia=COMBATES_POR_DIA,
            derrotas_npc=master.derrotas_npc,
        )

    def texto_estado(self, guerra: Guerra, quien: Master | None = None) -> str:
        """Como va la guerra, **para quien lo mira**.

        Lo de `quien` es lo que obliga a que el estado sea privado: de un
        Master solo se ve su Servant si se ha peleado contra el. Sin `quien`
        no se ensena ninguno, que es lo prudente: asi un sitio nuevo que
        llame a esto no filtra nada por descuido.
        """
        idioma = guerra.idioma
        if guerra.fase is Fase.LOBBY:
            return t(
                "bot.lobby_abierto",
                idioma,
                inscritos=len(guerra.masters),
                minimo=MINIMO_MASTERS,
            )
        lineas = [self._linea_de_estado(guerra, m, quien) for m in guerra.masters.values()]
        cabecera = t(
            "bot.estado_cabecera",
            idioma,
            dia=guerra.dia,
            fase=t(f"fase.{guerra.fase.value}", idioma),
        )
        grial = t(
            "bot.grial_en_juego" if guerra.otorga_grial else "bot.sin_grial",
            idioma,
            personas=plural("personas", len(guerra.humanos), idioma),
            minimo_grial=MINIMO_HUMANOS_PARA_GRIAL,
        )
        partes = [cabecera, "\n".join(lineas), grial]
        if guerra.fase is Fase.PREPARACION and not guerra.terminada:
            partes.append(self.texto_plazo(guerra))
        if any(not self._ve_el_servant(guerra, m, quien) for m in guerra.masters.values()):
            partes.append(t("bot.estado_a_ciegas", idioma))
        return "\n".join(partes)

    # --- el inventario ---

    def texto_de_la_suelta(
        self, guerra: Guerra, master: Master, suelto: objetos.Objeto
    ) -> str:
        """Mete en el inventario lo que solto el entrenamiento, y lo cuenta.

        Si no cabe se dice y se pierde. Es la opcion menos mala: guardarlo en
        una cola invisible seria un sistema entero por un caso que solo pasa
        con 25 objetos encima, y reventar le rompe el dia a quien gano.
        """
        idioma = guerra.idioma
        nombre = suelto.nombre_para(idioma)
        if not master.inventario.anadir(suelto.clave):
            return t(
                "inventario.lleno",
                idioma,
                tope=objetos.TOPE_INVENTARIO,
                nombre=nombre,
            )
        return " " + t("inventario.suelta", idioma, nombre=nombre)

    def texto_inventario(self, guerra: Guerra, master: Master) -> str:
        """Lo que lleva encima, agrupado por cuando se usa.

        Agrupado por momento y no en una lista plana porque lo que el Master
        necesita saber de un objeto es **cuando le sirve**: un elixir en la
        preparacion no hace nada y una venda en la batalla tampoco.
        """
        idioma = guerra.idioma
        inv = master.inventario
        if inv.vacio:
            return t("inventario.vacio", idioma)
        partes = [
            t(
                "inventario.cabecera",
                idioma,
                total=inv.total,
                tope=objetos.TOPE_INVENTARIO,
            )
        ]
        for momento in objetos.Momento:
            fichas = inv.lista(momento)
            if not fichas:
                continue
            partes.append(t(f"inventario.grupo_{momento.value}", idioma))
            partes += [
                t(
                    "inventario.linea",
                    idioma,
                    nombre=o.nombre_para(idioma),
                    cuantos=n,
                    descripcion=o.descripcion(idioma),
                )
                for o, n in fichas
            ]
        return "\n".join(partes)

    def objetos_usables_ahora(
        self, guerra: Guerra, master: Master
    ) -> list[tuple[objetos.Objeto, int]]:
        """Lo que puede usar en este momento de la guerra, y nada mas.

        En la preparacion, los de preparacion. En combate no se pasa por aqui:
        eso lo decide el menu de combate, que sabe de que batalla se trata.
        Los catalizadores no entran todavia porque no hacen nada.
        """
        if guerra.fase is not Fase.PREPARACION or master.listo:
            return []
        return master.inventario.lista(objetos.Momento.PREPARACION)

    def objetos_de_combate(
        self, guerra: Guerra, master: Master
    ) -> list[tuple[objetos.Objeto, int]]:
        """Lo que puede usar en la batalla que esta peleando ahora.

        Vacio si no esta en una batalla o si ya gasto el objeto de esta. No
        mira si le toca decidir: usar un objeto no es la accion del turno.
        """
        if self.combate_de(guerra, master) is None:
            return []
        if not master.inventario.puede_usar_en_la_batalla:
            return []
        return master.inventario.lista(objetos.Momento.COMBATE)

    # --- los Sellos de Comando ---

    def usos_de_sello(self, guerra: Guerra, master: Master) -> list[sellos.Sello]:
        """Los tres usos, si puede gastar un Sello ahora; vacio si no.

        Es el gemelo de `objetos_de_combate`, y tampoco mira si le toca
        decidir: gastar un Sello no es la accion del turno. Lo que lo apaga es
        no estar en una batalla, no quedarle ninguno o haber gastado el de
        esta batalla (`Master.puede_usar_sello`, que junta los dos topes).
        """
        if self.combate_de(guerra, master) is None:
            return []
        if not master.puede_usar_sello:
            return []
        return sellos.lista()

    def usar_sello_en_combate(
        self, guerra: Guerra, master: Master, clave: str
    ) -> str:
        """Gasta un Sello dentro de la batalla. Devuelve lo que se le cuenta.

        El mismo orden que una compra y que un objeto: **comprobar, cobrar,
        entregar**, salvo que aqui se entrega antes de cobrar por la misma
        razon que en `usar_objeto_en_combate`: un Sello que se gasta sin efecto
        no vuelve, y no volver es todo lo que un Sello tiene.
        """
        idioma = guerra.idioma
        s = sellos.sello(clave)
        if s is None:
            return t("sello.no_es_uno", idioma)
        if master.sellos <= 0:
            return t("sello.sin_sellos", idioma)
        if not master.puede_usar_sello:
            return t("sello.ya_en_esta_batalla", idioma)
        combate = self.combate_de(guerra, master)
        if combate is None:
            return t("combate.sin_combate", idioma)
        try:
            eventos = combate.usar_sello(master.id, s)
        except RuntimeError as e:
            return str(e)
        master.gastar_sello()
        # El registro se le guarda a quien estuvo delante, igual que con un
        # objeto: nombra lo que paso en la batalla.
        master.ultimo_registro = list(combate.batalla.registro)
        master.ultimo_registro_dia = guerra.dia
        self.guardar(guerra)
        cola = "\n".join(eventos)
        cabeza = t("sello.gastado", idioma, sellos=master.sellos)
        return f"{cabeza}\n```\n{cola}\n```"

    def usar_objeto_en_combate(
        self, guerra: Guerra, master: Master, clave: str
    ) -> str:
        """Usa un objeto dentro de la batalla. Devuelve lo que se le cuenta.

        El orden importa: primero se comprueba todo, luego se aplica, y solo
        si se aplico se gasta. Asi no hay forma de perder un objeto sin
        efecto, que es el error que mas duele de un consumible.
        """
        idioma = guerra.idioma
        o = objetos.objeto(clave)
        if o is None or not master.inventario.tiene(clave):
            return t("inventario.no_lo_tienes", idioma)
        if o.momento is not objetos.Momento.COMBATE:
            return t("inventario.no_en_combate", idioma, nombre=o.nombre_para(idioma))
        if not master.inventario.puede_usar_en_la_batalla:
            return t("inventario.ya_usaste", idioma)
        combate = self.combate_de(guerra, master)
        if combate is None:
            return t("combate.sin_combate", idioma)
        try:
            eventos = combate.usar_objeto(master.id, o)
        except RuntimeError as e:
            return str(e)
        master.inventario.quitar(clave)
        master.inventario.usados_en_la_batalla += 1
        # El registro se le guarda a quien estuvo delante, como el de la
        # batalla: nombra el objeto, y eso es informacion de la pelea.
        master.ultimo_registro = list(combate.batalla.registro)
        master.ultimo_registro_dia = guerra.dia
        self.guardar(guerra)
        cola = "\n".join(eventos)
        return f"{t('inventario.usado', idioma, nombre=o.nombre_para(idioma))}\n```\n{cola}\n```"

    def usar_objeto_en_preparacion(
        self, guerra: Guerra, master: Master, clave: str
    ) -> str:
        """Usa un objeto de preparacion. Devuelve lo que se le cuenta.

        El objeto se quita **antes** de aplicarlo y solo si se aplica: asi no
        hay forma de gastarlo sin efecto ni de aplicarlo sin gastarlo.
        """
        idioma = guerra.idioma
        o = objetos.objeto(clave)
        if o is None or not master.inventario.tiene(clave):
            return t("inventario.no_lo_tienes", idioma)
        if o.momento is objetos.Momento.INVOCACION:
            return t("inventario.catalizador_pendiente", idioma)
        if o.momento is not objetos.Momento.PREPARACION:
            return t(
                "inventario.no_en_preparacion", idioma, nombre=o.nombre_para(idioma)
            )
        aviso = self.motivo_para_no_planear(guerra, master)
        if aviso:
            return aviso
        master.inventario.quitar(clave)
        texto = self._aplicar_fuera(guerra, master, o)
        self.guardar(guerra)
        return texto

    def _aplicar_fuera(
        self, guerra: Guerra, master: Master, o: objetos.Objeto
    ) -> str:
        """Lo que hace cada efecto de preparacion. Lista cerrada.

        Las tres cosas las sabia hacer ya el dia: dar XP, borrar las derrotas
        contra NPC (que es lo que te quita vida) y dar un intento mas.
        """
        idioma = guerra.idioma
        nombre = o.nombre_para(idioma)
        if o.efecto_fuera is objetos.EfectoFuera.XP:
            master.servant.ganar_xp(int(o.valor))
            return t("inventario.xp_ganada", idioma, nombre=nombre, valor=int(o.valor))
        if o.efecto_fuera is objetos.EfectoFuera.CURAR_ANTES:
            master.derrotas_npc = 0
            return t("inventario.curado_antes", idioma, nombre=nombre)
        if o.efecto_fuera is objetos.EfectoFuera.COMBATE_EXTRA:
            # Se baja el contador de intentos en vez de subir el tope: asi el
            # tope sigue siendo uno y el boton de entrenar se vuelve a
            # encender sin saber nada de objetos.
            master.intentos_npc = max(0, master.intentos_npc - int(o.valor))
            return t("inventario.combate_extra", idioma, nombre=nombre)
        return t("inventario.usado", idioma, nombre=nombre)

    # --- la tienda ---

    def cuenta_de(self, usuario_id: str) -> tienda.Cuenta:
        """La cuenta de griales de alguien, leida una vez y guardada en memoria.

        Las cuentas **no** son de la guerra: viven en su propia tabla y
        sobreviven a todas. Se guardan aqui en un diccionario para no ir a la
        base de datos cada vez que alguien abre la tienda, y la fila se escribe
        solo cuando cambia (`apuntar_cuenta`).

        Sin conexion devuelve una cuenta en memoria, igual que el resto del Cog
        funciona sin base de datos: asi las pruebas no necesitan una.
        """
        id_ = str(usuario_id)
        if id_ not in self.cuentas:
            if self.conexion is None:
                self.cuentas[id_] = tienda.Cuenta(usuario_id=id_)
            else:
                try:
                    self.cuentas[id_] = repositorio.cargar_cuenta(self.conexion, id_)
                except sqlite3.Error:
                    registro.exception("no pude leer la cuenta de %s", id_)
                    self.cuentas[id_] = tienda.Cuenta(usuario_id=id_)
        return self.cuentas[id_]

    def apuntar_cuenta(self, cuenta: tienda.Cuenta) -> None:
        """Guarda la cuenta. Lo que no se guarde aqui se pierde de verdad.

        Al contrario que el oro, que esta dentro de la guerra y se guarda con
        ella, los griales no los salva `guardar(guerra)`: hay que acordarse de
        llamar a esto despues de cada cambio. Son dos sitios: comprar un
        catalizador y ganar una guerra.
        """
        self.cuentas[cuenta.usuario_id] = cuenta
        if self.conexion is None:
            return
        try:
            repositorio.guardar_cuenta(self.conexion, cuenta)
        except sqlite3.Error:
            registro.exception("no pude guardar la cuenta de %s", cuenta.usuario_id)

    def texto_monedas(self, guerra: Guerra, master: Master) -> str:
        return t(
            "moneda.resumen",
            guerra.idioma,
            oro=master.oro,
            griales=self.cuenta_de(master.id).griales,
        )

    def motivo_para_no_comprar(self, guerra: Guerra, master: Master) -> str | None:
        """Por que no puede comprar ahora, o `None` si puede.

        La tienda abre **solo en la preparacion**, y eso es una regla de juego
        y no una comodidad: si se pudiera comprar dentro de la batalla, el
        objeto dejaria de ser algo que decides llevar y seria algo que saca de
        la nada el que vaya perdiendo.

        Y no se compra despues de decirse listo, por lo mismo que no se
        entrena ni se cambia de objetivo: cerrar el dia lo cierra para ti.
        """
        idioma = guerra.idioma
        if guerra.fase is not Fase.PREPARACION or guerra.terminada or master.eliminado:
            return t("tienda.solo_preparacion", idioma)
        if master.listo:
            return t("tienda.listo_no_compras", idioma)
        return None

    def texto_tienda(self, guerra: Guerra, master: Master) -> str:
        """El escaparate: lo que hay, a cuanto y con que moneda."""
        idioma = guerra.idioma
        lineas = [
            t("tienda.cabecera", idioma, monedas=self.texto_monedas(guerra, master)),
            t("tienda.grupo_oro", idioma),
        ]
        for o in tienda.a_la_venta():
            cuanto, _ = tienda.precio_de(o)
            lineas.append(
                t(
                    "tienda.linea",
                    idioma,
                    nombre=o.nombre_para(idioma),
                    precio=cuanto,
                    moneda=t("moneda.oro", idioma),
                    descripcion=o.descripcion(idioma),
                )
            )
        lineas.append(t("tienda.grupo_griales", idioma))
        lineas.append(
            t(
                "tienda.linea_catalizador_clase",
                idioma,
                precio=tienda.PRECIO_CATALIZADOR_CLASE,
            )
        )
        lineas.append(
            t(
                "tienda.linea_catalizador_servant",
                idioma,
                precio=tienda.PRECIO_CATALIZADOR_SERVANT,
            )
        )
        lineas.append(t("moneda.oro_explicado", idioma))
        lineas.append(t("moneda.griales_explicado", idioma))
        return "\n".join(lineas)

    def comprar_con_oro(self, guerra: Guerra, master: Master, clave: str) -> str:
        """Compra un objeto con oro. Devuelve lo que se le cuenta."""
        aviso = self.motivo_para_no_comprar(guerra, master)
        if aviso:
            return aviso
        compra = tienda.comprar_con_oro(master, clave)
        if compra.ok:
            self.guardar(guerra)
        return self._texto_de_compra(guerra, master, compra, master.oro)

    def comprar_catalizador_de_clase(
        self, guerra: Guerra, master: Master, clase: str
    ) -> str:
        aviso = self.motivo_para_no_comprar(guerra, master)
        if aviso:
            return aviso
        try:
            ficha = objetos.catalizador_de_clase(Clase(clase))
        except ValueError:
            ficha = None
        return self._comprar_catalizador(guerra, master, ficha)

    def comprar_catalizador_de_servant(
        self, guerra: Guerra, master: Master, busqueda: str
    ) -> str:
        """Compra el catalizador de un Servant, buscandolo por el nombre.

        Se busca por nombre y no se elige de una lista porque **son 348** y un
        desplegable de Discord aguanta 25. Si lo que escribio encaja con
        varios, no se compra ninguno y se le ensenan los que encajan: 5
        griales son tres guerras ganadas y no se gastan en un Servant que no
        era el que queria.
        """
        aviso = self.motivo_para_no_comprar(guerra, master)
        if aviso:
            return aviso
        idioma = guerra.idioma
        encontrados = self.buscar_en_el_plantel(busqueda)
        if not encontrados:
            return t("tienda.servant_no_encontrado", idioma, busqueda=busqueda)
        if len(encontrados) > 1:
            return t(
                "tienda.servant_ambiguo",
                idioma,
                busqueda=busqueda,
                opciones=", ".join(p.nombre for p in encontrados[:10]),
            )
        ficha = objetos.catalizador_de_servant(encontrados[0].collection_no)
        return self._comprar_catalizador(guerra, master, ficha)

    def _comprar_catalizador(
        self, guerra: Guerra, master: Master, ficha
    ) -> str:
        cuenta = self.cuenta_de(master.id)
        compra = tienda.comprar_catalizador(master, cuenta, ficha)
        if compra.ok:
            # Dos sitios distintos: el catalizador va en la guerra y los
            # griales en la cuenta, asi que hay que guardar las dos cosas.
            self.apuntar_cuenta(cuenta)
            self.guardar(guerra)
        return self._texto_de_compra(guerra, master, compra, cuenta.griales)

    def _texto_de_compra(
        self, guerra: Guerra, master: Master, compra: tienda.Compra, resto: int
    ) -> str:
        """La frase de un intento de compra, salga bien o mal.

        Cada fallo tiene la suya: "no te llega" y "no te cabe" son problemas
        distintos y la solucion de cada uno tambien.
        """
        idioma = guerra.idioma
        nombre = (
            compra.objeto.nombre_para(idioma) if compra.objeto is not None else "?"
        )
        if compra.ok:
            return t(
                "tienda.comprado",
                idioma,
                nombre=nombre,
                precio=compra.pagado,
                moneda=t(f"moneda.{compra.moneda.value}", idioma),
                resto=resto,
            )
        if compra.fallo is tienda.Fallo.SIN_ORO:
            return t(
                "tienda.sin_oro",
                idioma,
                nombre=nombre,
                precio=tienda.precio_de(compra.objeto)[0],
                tienes=master.oro,
            )
        if compra.fallo is tienda.Fallo.SIN_GRIALES:
            return t(
                "tienda.sin_griales",
                idioma,
                nombre=nombre,
                precio=tienda.precio_de(compra.objeto)[0],
                tienes=self.cuenta_de(master.id).griales,
            )
        if compra.fallo is tienda.Fallo.INVENTARIO_LLENO:
            return t(
                "inventario.lleno",
                idioma,
                tope=objetos.TOPE_INVENTARIO,
                nombre=nombre,
            )
        return t("tienda.no_se_vende", idioma)

    def buscar_en_el_plantel(self, busqueda: str) -> list:
        """Los personajes cuyo nombre encaja con lo que escribio.

        Primero se prueba el nombre exacto: con "Medusa" hay tres y la exacta
        es una, asi que buscar lo que se llama justo asi no puede ser ambiguo.
        Si no hay exacto, los que lo contienen.
        """
        texto = (busqueda or "").strip().casefold()
        if not texto:
            return []
        exactos = [p for p in CATALOGO if p.nombre.casefold() == texto]
        if exactos:
            return exactos
        return [p for p in CATALOGO if texto in p.nombre.casefold()]

    def pagar_los_griales(self, guerra: Guerra) -> str:
        """Paga los griales al que se llevo el Grial, si alguien se lo llevo.

        Pasa por `guerra.gana_el_grial()` y **no** por `ganador()`, y esa es toda la
        defensa contra lo obvio: una guerra necesita 4 personas de verdad para
        entregar el Grial, asi que abrir una guerra contra 6 bots, ganarla y
        cobrar no se puede. La regla ya existia; lo unico que habia que hacer
        es cobrar por donde se entrega el Grial.

        Lo llaman **dos** sitios, que son los dos que anuncian el Grial:
        `narrar_cierre` (una guerra que se acaba peleando) y
        `rendir_al_master` (una que se acaba porque los demas se retiraron,
        que pide mas de 5 personas). Si alguno anunciara sin pagar, alguien
        leeria que gano un grial que no tiene.

        Devuelve el texto para el canal, o "" si esta guerra no paga nada.
        """
        ganador = guerra.gana_el_grial()
        if ganador is None:
            return ""
        cuenta = self.cuenta_de(ganador.id)
        pagado = cuenta.ganar_guerra()
        self.apuntar_cuenta(cuenta)
        return t(
            "bot.griales_ganados",
            guerra.idioma,
            nombre=ganador.nombre,
            griales=pagado,
        )

    # --- el arte ---

    def arte_del_servant(
        self, servant: Servant | None, titulo: str = ""
    ) -> object | None:
        """Un embed con el arte del Servant, o `None` si no hay que ensenar nada.

        **El embed lleva la URL de Atlas Academy, no el archivo.** El bot
        enlaza el arte y el cliente de quien mira lo pide; subirlo seria
        volver a publicarlo, y eso es lo que la regla no permite (ver la
        decision del arte en docs/decisiones.md).

        Devuelve `None` sin Servant y sin URL, para que quien llame no tenga
        que preguntar ninguna de las dos cosas: un Servant sin arte deja el
        mensaje en texto y no se rompe, y un Master que todavia no invoco
        tampoco. Lo segundo pasa de verdad: la invocacion puede fallar, y
        entonces no hay Servant del que ensenar nada.
        """
        if servant is None or not servant.imagen:
            return None
        embed = discord.Embed(title=titulo or None)
        embed.set_image(url=servant.imagen)
        return embed

    def servants_conocidos(
        self, guerra: Guerra, master: Master
    ) -> list[tuple[str, str, str]]:
        """Los rivales cuyo Servant ya vio: (id, Master, Servant).

        El suyo no entra: para eso esta su ficha. La regla del secreto la
        decide `_ve_el_servant` y nada mas, asi que aqui no hay otra copia.
        """
        return [
            (m.id, m.nombre, m.servant.nombre)
            for m in guerra.masters.values()
            if m.id != master.id and self._ve_el_servant(guerra, m, master)
        ]

    def ficha_del_conocido(
        self, guerra: Guerra, master: Master, id_: str
    ) -> tuple[str, object | None]:
        """El texto y el arte de un Servant rival ya conocido.

        No ensena nivel ni estadisticas a proposito: lo que se dice aqui es lo
        que `/estado-guerra` ya decia de un rival conocido (quien lo lleva, que
        Servant es y de que clase), mas el dibujo. Si esto contara su nivel
        seria informacion nueva, o sea un cambio de balance, y eso se mide
        antes de hacerlo.
        """
        rival = guerra.masters.get(id_)
        if rival is None or not self._ve_el_servant(guerra, rival, master):
            return t("conocidos.no_lo_conoces", guerra.idioma), None
        texto = t(
            "conocidos.ficha",
            guerra.idioma,
            master=rival.nombre,
            servant=rival.servant.nombre,
            clase=rival.servant.clase.value,
        )
        return texto, self.arte_del_servant(rival.servant, rival.servant.nombre)

    def _ve_el_servant(
        self, guerra: Guerra, suyo: Master, quien: Master | None
    ) -> bool:
        return suyo.servant is not None and quien is not None and quien.conoce(suyo.id)

    def _linea_de_estado(
        self, guerra: Guerra, m: Master, quien: Master | None
    ) -> str:
        idioma = guerra.idioma
        if m.servant is None:
            return t("bot.estado_linea_sin_invocar", idioma, master=m.nombre)
        marca = "~~" if m.eliminado else ""
        if not self._ve_el_servant(guerra, m, quien):
            return t(
                "bot.estado_linea_oculto",
                idioma,
                marca=marca,
                master=m.nombre,
                derrotas=m.derrotas,
                para_eliminar=DERROTAS_PARA_ELIMINAR,
            )
        return t(
            "bot.estado_linea",
            idioma,
            marca=marca,
            master=m.nombre,
            servant=m.servant.nombre,
            nivel=m.servant.nivel,
            clase=m.servant.clase.value,
            derrotas=m.derrotas,
            para_eliminar=DERROTAS_PARA_ELIMINAR,
            sellos=m.sellos,
        )

    def texto_plazo(self, guerra: Guerra) -> str:
        """Lo que le queda al dia, redondeado hacia arriba.

        Hacia arriba porque un "0 min" que todavia no ha vencido miente. Y con
        `ceil`, no con `// 60 + 1`: eso convertia 10 minutos justos en 11, y
        hacia que una prueba fallara una vez de cada muchas segun donde
        cayera el reloj.
        """
        quedan = guerra.segundos_para_cerrar
        if quedan < 60:
            return t("bot.estado_plazo_poco", guerra.idioma)
        return t(
            "bot.estado_plazo", guerra.idioma, minutos=math.ceil(quedan / 60)
        )

    def motivo_para_no_planear(self, guerra: Guerra, master: Master) -> str | None:
        """Por que ese Master no puede declarar un ataque, o `None` si puede.

        Lo mismo que `pelear_npc`: estar listo cierra el dia de quien lo dice,
        y eso incluye el ataque. Si se pudiera cambiar de objetivo despues de
        decir que acabaste, decirlo no significaria nada, que es justo el
        agujero que se cerro con el entrenamiento.
        """
        idioma = guerra.idioma
        if master.servant is None:
            return t("bot.planear_invoca_primero", idioma)
        if master.listo:
            return t("bot.planear_listo", idioma)
        if guerra.fase is not Fase.PREPARACION or guerra.terminada or master.eliminado:
            return t("bot.planear_fuera", idioma)
        if not self._rivales(guerra, master):
            return t("bot.planear_sin_rivales", idioma)
        return None

    def _rivales(self, guerra: Guerra, master: Master) -> list[Master]:
        return [m for m in guerra.activos if m.id != master.id]

    def opciones_de_ataque(
        self, guerra: Guerra, master: Master
    ) -> list[tuple[str, str, str, bool]]:
        """Los rivales de hoy: (id, nombre, lo que se sabe de el, si es el actual).

        De quien no has peleado no se dice el Servant, igual que en el estado.
        Es el sitio donde se nota para que sirve el secreto: eliges por el
        nombre y por las derrotas que lleva, no por la clase.
        """
        idioma = guerra.idioma
        opciones = []
        for m in self._rivales(guerra, master):
            if self._ve_el_servant(guerra, m, master):
                descripcion = t(
                    "bot.planear_opcion_conocido",
                    idioma,
                    servant=m.servant.nombre,
                    nivel=m.servant.nivel,
                    clase=m.servant.clase.value,
                )
            else:
                descripcion = t(
                    "bot.planear_opcion_oculto",
                    idioma,
                    derrotas=m.derrotas,
                    para_eliminar=DERROTAS_PARA_ELIMINAR,
                )
            opciones.append((m.id, m.nombre, descripcion, m.id == master.objetivo))
        return opciones

    def texto_planear(self, guerra: Guerra, master: Master, objetivo: str) -> str:
        """Declara el ataque de un Master. Nunca sale al canal.

        Que sea secreto es lo que hace que el secreto del Servant sirva para
        algo: si se anunciara a quien atacas, el rival sabria con quien va a
        pelear y podria deducir por eliminacion.
        """
        aviso = self.motivo_para_no_planear(guerra, master)
        if aviso:
            return aviso
        try:
            guerra.declarar_ataque(master.id, objetivo)
        except (ValueError, RuntimeError) as e:
            return str(e)
        self.guardar(guerra)
        return t(
            "bot.planear_hecho",
            guerra.idioma,
            master=guerra.masters[objetivo].nombre,
        )

    def texto_ultima_batalla(self, guerra: Guerra, master: Master) -> str:
        """El registro de su ultima batalla, que solo ve el que estuvo."""
        if not master.ultimo_registro:
            return t("bot.sin_registro", guerra.idioma)
        return t(
            "bot.registro_de_batalla",
            guerra.idioma,
            dia=master.ultimo_registro_dia,
            registro="\n".join(master.ultimo_registro[-LINEAS_DE_REGISTRO:]),
        )

    # --- el combate por turnos ---

    def combate_de(self, guerra: Guerra, master: Master):
        """El combate en curso de ese Master, si pelea en alguno ahora mismo."""
        estado = self.combates.get(guerra.id)
        return estado.combate_de(master.id) if estado else None

    def motivo_para_no_decidir(self, guerra: Guerra, master: Master) -> str | None:
        """Por que no puede decidir ahora, o `None` si si puede.

        Lo usan el menu para apagar los botones y cada accion para
        explicarse, igual que `motivo_para_no_planear`: si el boton y la
        accion no miran lo mismo, uno de los dos miente.
        """
        idioma = guerra.idioma
        combate = self.combate_de(guerra, master)
        if combate is None:
            return t("combate.sin_combate", idioma)
        if combate.terminado:
            return t("combate.terminada", idioma)
        if not combate.batalla.combatientes[master.id].vivo:
            return t("combate.terminada", idioma)
        if combate.ya_decidio(master.id):
            return t("combate.ya_decidiste", idioma)
        if master.id not in combate.pendientes:
            return t("combate.esperas_el_turno", idioma)
        return None

    def acciones_posibles(self, guerra: Guerra, master: Master) -> list[Accion]:
        combate = self.combate_de(guerra, master)
        if combate is None or combate.terminado:
            return []
        return combate.batalla.acciones_posibles(master.id)

    def texto_combate(self, guerra: Guerra, master: Master) -> str:
        """Como va tu batalla: tu Servant, los rivales y a quien se espera.

        Aqui si salen los Servants de los rivales. No es una filtracion: es la
        regla al derecho, porque estar delante de alguien en una batalla es
        justo lo que destapa su Servant.
        """
        idioma = guerra.idioma
        combate = self.combate_de(guerra, master)
        if combate is None:
            return t("combate.sin_combate", idioma)
        batalla = combate.batalla
        yo = batalla.combatientes[master.id]
        lineas = [
            t(
                "combate.rival",
                idioma,
                master=c.nombre,
                servant=c.servant.nombre,
                clase=c.servant.clase.value,
                vida=c.vida,
                maxima=c.servant.vida_maxima,
            )
            if c.vivo
            else t(
                "combate.rival_caido",
                idioma,
                master=c.nombre,
                servant=c.servant.nombre,
                clase=c.servant.clase.value,
            )
            for c in batalla.combatientes.values()
            if c.id != master.id
        ]
        cabecera = t(
            "combate.cabecera",
            idioma,
            dia=guerra.dia,
            turno=batalla.turno,
            yo=t(
                "combate.yo",
                idioma,
                servant=yo.servant.nombre,
                clase=yo.servant.clase.value,
                vida=yo.vida,
                maxima=yo.servant.vida_maxima,
                mana=yo.mana,
                costo=yo.costo_np,
            ),
            rivales="\n".join(lineas),
        )
        return (
            cabecera
            + "\n"
            + t("sello.restantes", idioma, sellos=master.sellos)
            + "\n"
            + self._pie_del_combate(guerra, master, combate)
        )

    def _pie_del_combate(self, guerra: Guerra, master: Master, combate) -> str:
        """La ultima linea del menu: que se espera de ti, o de quien."""
        idioma = guerra.idioma
        if combate.terminado:
            return t("combate.terminada", idioma)
        if combate.espera is combate_mod.Espera.VOTACION:
            if combate.ya_decidio(master.id):
                return t("combate.ya_decidiste", idioma)
            return t(
                "combate.votacion",
                idioma,
                nombres=", ".join(c.nombre for c in combate.batalla.vivos),
            )
        if combate.ya_decidio(master.id) or master.id not in combate.pendientes:
            faltan = [
                combate.batalla.combatientes[i].nombre for i in combate.pendientes
            ]
            if faltan:
                return t("combate.esperando", idioma, nombres=", ".join(faltan))
            return t("combate.sin_nada_nuevo", idioma)
        return t("combate.te_toca", idioma)

    def opciones_de_objetivo(
        self, guerra: Guerra, master: Master
    ) -> list[tuple[str, str, str]]:
        """Los rivales en pie de tu batalla: (id, etiqueta, descripcion)."""
        combate = self.combate_de(guerra, master)
        if combate is None:
            return []
        return [
            (
                c.id,
                f"{c.nombre} - {c.servant.nombre}",
                t(
                    "combate.rival",
                    guerra.idioma,
                    master=c.nombre,
                    servant=c.servant.nombre,
                    clase=c.servant.clase.value,
                    vida=c.vida,
                    maxima=c.servant.vida_maxima,
                )[:100],
            )
            for c in combate.batalla.rivales_de(master.id)
        ]

    def nombre_de_habilidad(self, guerra: Guerra, master: Master, numero: int) -> str:
        hab = master.servant.habilidad(numero)
        return hab.nombre_para(guerra.idioma) if hab else str(numero)

    def opciones_de_habilidad(
        self, guerra: Guerra, master: Master
    ) -> list[tuple[str, str, str]]:
        """Las habilidades listas: (numero, nombre, lo que hace)."""
        combate = self.combate_de(guerra, master)
        if combate is None:
            return []
        opciones = []
        for numero in combate.batalla.habilidades_disponibles(master.id):
            hab = master.servant.habilidad(numero)
            opciones.append(
                (
                    str(numero),
                    (hab.nombre_para(guerra.idioma) or str(numero))[:100],
                    (hab.descripcion(guerra.idioma) or "")[:100],
                )
            )
        return opciones

    def opciones_de_objetivo_de_habilidad(
        self, guerra: Guerra, master: Master, numero: int
    ) -> list[tuple[str, str, str]]:
        """A quien se le puede dar esa habilidad, uno mismo incluido si vale."""
        combate = self.combate_de(guerra, master)
        if combate is None:
            return []
        opciones = []
        for c in combate.batalla.objetivos_posibles(master.id, numero):
            if c.id == master.id:
                etiqueta_ = t("combate.yo_mismo", guerra.idioma)
            else:
                etiqueta_ = f"{c.nombre} - {c.servant.nombre}"
            opciones.append((c.id, etiqueta_[:100], c.servant.nombre[:100]))
        return opciones

    def decidir_en_combate(
        self, guerra: Guerra, master: Master, decision: Decision
    ) -> str:
        """Apunta tu decision del turno y cuenta lo que se puede contar.

        Mientras falte alguien, lo unico que se dice es que quedo apuntada: si
        se dijera algo mas, el orden de llegada valdria informacion.
        """
        idioma = guerra.idioma
        aviso = self.motivo_para_no_decidir(guerra, master)
        if aviso:
            return aviso
        combate = self.combate_de(guerra, master)
        yo = combate.batalla.combatientes[master.id]

        if decision.accion is Accion.DEFENDER and not yo.puede_defender:
            return t("combate.no_defiende", idioma, servant=yo.servant.nombre)
        if decision.accion is Accion.NOBLE_FANTASMA and not yo.puede_noble_fantasma:
            return t("combate.np_no_listo", idioma, faltan=yo.costo_np - yo.mana)

        if decision.accion is Accion.ATACAR:
            confirma = t(
                "combate.decidido_atacar",
                idioma,
                master=combate.batalla.combatientes[decision.objetivo].nombre,
            )
        elif decision.accion is Accion.DEFENDER:
            confirma = t("combate.decidido_defender", idioma)
        elif decision.accion is Accion.NOBLE_FANTASMA:
            confirma = t(
                "combate.decidido_np",
                idioma,
                master=combate.batalla.combatientes[decision.objetivo].nombre,
            )
        else:
            confirma = t(
                "combate.decidido_habilidad",
                idioma,
                habilidad=master.servant.habilidad(
                    decision.habilidad or 1
                ).nombre_para(idioma),
                objetivo=combate.batalla.combatientes[decision.objetivo].nombre,
            )

        eventos = combate.decidir(master.id, decision)
        return confirma + self._cola_del_turno(guerra, eventos)

    def votar_en_combate(self, guerra: Guerra, master: Master, seguir: bool) -> str:
        idioma = guerra.idioma
        aviso = self.motivo_para_no_decidir(guerra, master)
        if aviso:
            return aviso
        combate = self.combate_de(guerra, master)
        if combate.espera is not combate_mod.Espera.VOTACION:
            return t("combate.no_te_toca", idioma)
        confirma = t(
            "combate.decidido_seguir" if seguir else "combate.decidido_parar", idioma
        )
        eventos = combate.votar(master.id, seguir)
        return confirma + self._cola_del_turno(guerra, eventos)

    def _cola_del_turno(self, guerra: Guerra, eventos: list[str]) -> str:
        """Lo que paso al resolverse el turno, si se resolvio con tu decision.

        Tambien es el sitio donde se anotan las batallas que acabaron: si se
        olvidara, un Servant derrotado seguiria peleando el dia siguiente.

        Y es donde se apunta el turno recien resuelto para los **demas**: la
        decision que cierra el turno solo contesta a quien la tomo, y a los
        otros hay que ir a buscarlos. Ver `repartir_el_turno`.
        """
        estado = self.combates.get(guerra.id)
        if estado is not None:
            dia.recoger(guerra, estado)
        self.guardar(guerra)
        if not eventos:
            return ""
        self.turnos_por_repartir[guerra.id] = list(eventos)
        return "\n" + self.texto_del_turno(guerra, eventos)

    def texto_del_turno(self, guerra: Guerra, eventos: list[str]) -> str:
        return t(
            "combate.turno_resuelto",
            guerra.idioma,
            registro="\n".join(eventos[-LINEAS_DE_REGISTRO:]),
        )

    # --- repartir el turno entre los que estan peleando ---

    def apuntar_mesa(
        self,
        interaction: discord.Interaction,
        guerra: Guerra,
        master: Master,
        vista: "MenuCombate",
    ) -> None:
        """Se queda por donde hablarle a alguien que esta peleando.

        Discord no deja mandarle un mensaje efimero a nadie de la nada, pero si
        deja contestar otra vez a una interaccion que ya existe, durante 15
        minutos. Asi que de cada persona que pelea se guarda su ultima
        interaccion y su menu, y cuando el turno se resuelve se les habla por
        ahi. Vive en memoria y dura lo que la batalla, como `self.combates`.
        """
        self.mesas[(guerra.id, master.id)] = (interaction, vista)

    def olvidar_mesas(self, guerra: Guerra) -> None:
        """Suelta las de esa guerra. Al acabar el dia ya no hay a quien hablar."""
        for clave in [c for c in self.mesas if c[0] == guerra.id]:
            del self.mesas[clave]

    async def repartir_el_turno(
        self, guerra: Guerra, autor_id: str
    ) -> list[str]:
        """Le cuenta el turno resuelto a los demas de la batalla.

        **Esto es el arreglo del fallo que conto Cristopher**: un turno se
        resuelve cuando decide el ultimo, y `Combate.decidir` solo le devuelve
        los eventos a ese. Los demas se quedaban con "queda apuntada" y nada
        mas: no veian el turno y, peor, no tenian forma de saber que habia
        pasado algo, asi que tampoco sabian que tenian que refrescar.

        A cada uno se le hace dos cosas, y las dos importan: se le **reescribe
        el menu** (porque su vida, su mana y lo que puede hacer han cambiado) y
        se le **manda el turno** en un mensaje nuevo, que es lo que de verdad
        le avisa.

        Devuelve los ids a los que les llego, que es lo que se puede probar.
        """
        eventos = self.turnos_por_repartir.pop(guerra.id, None)
        if not eventos:
            return []
        avisados = []
        for master in self.quien_mas_pelea_con(guerra, autor_id):
            if await self._avisar_del_turno(guerra, master, eventos):
                avisados.append(master.id)
        return avisados

    def quien_mas_pelea_con(self, guerra: Guerra, autor_id: str) -> list[Master]:
        """Las personas que pelean en la **misma** batalla que esa, menos ella.

        En la misma batalla y no en toda la guerra: contarle el turno a quien
        pelea en otra mesa seria contarle una batalla en la que no esta, y eso
        es justo lo que la regla del secreto no permite.
        """
        estado = self.combates.get(guerra.id)
        if estado is None:
            return []
        combate = estado.combate_de(autor_id)
        if combate is None:
            return []
        return [
            guerra.masters[id_]
            for id_ in sorted(combate.humanos)
            if id_ != autor_id and id_ in guerra.masters
        ]

    async def _avisar_del_turno(
        self, guerra: Guerra, master: Master, eventos: list[str]
    ) -> bool:
        """Le reescribe el menu y le manda el turno. `False` si no se pudo.

        Que no se pueda es normal y no es un error: la interaccion caduca a los
        15 minutos y el mensaje efimero lo puede haber cerrado. Se registra y
        se sigue, porque el turno ya paso y la batalla no puede quedarse
        parada porque alguien cerrara una ventana.
        """
        mesa = self.mesas.get((guerra.id, master.id))
        if mesa is None:
            return False
        interaccion, vista = mesa
        try:
            vista.refrescar()
            await interaccion.edit_original_response(
                content=self.texto_combate(guerra, master), view=vista
            )
            await interaccion.followup.send(
                self.texto_del_turno(guerra, eventos), ephemeral=True
            )
        except discord.HTTPException as e:
            registro.info(
                "no pude avisar del turno a %s en la guerra %s: %s",
                master.id,
                guerra.id,
                e,
            )
            return False
        return True

    async def despues_de_decidir(
        self, interaction: discord.Interaction, guerra: Guerra, master: Master
    ) -> None:
        """Lo que hay que hacer **siempre** despues de una decision de combate.

        Son dos cosas y las dos se olvidan solas, asi que viven juntas y en un
        solo sitio: contarle el turno a los demas de la batalla, y cerrar el
        dia si esa fue la ultima decision. Cada camino del menu de combate
        llama a esto y a nada mas.
        """
        await self.repartir_el_turno(guerra, master.id)
        await self.cerrar_si_acabaron_los_combates(interaction, guerra)

    def texto_registro_del_combate(self, guerra: Guerra, master: Master) -> str:
        combate = self.combate_de(guerra, master)
        if combate is None:
            return self.texto_ultima_batalla(guerra, master)
        if not combate.batalla.registro:
            return t("combate.sin_nada_nuevo", guerra.idioma)
        return t(
            "combate.registro",
            guerra.idioma,
            registro="\n".join(combate.batalla.registro[-LINEAS_DE_REGISTRO:]),
        )

    def pelear_npc(self, guerra: Guerra, master: Master) -> str:
        """Pelea el siguiente combate de entrenamiento y lo cuenta."""
        idioma = guerra.idioma
        if master.servant is None:
            return t("bot.invoca_primero", idioma)
        # Si pudieras entrenar despues de decir que acabaste, decirlo no
        # significaria nada y el agujero seguiria abierto.
        if master.listo:
            return t("bot.listo_no_entrenas", idioma)
        if guerra.fase is not Fase.PREPARACION:
            return t("bot.npc_solo_preparacion", idioma)
        if master.intentos_npc_restantes <= 0:
            return t("bot.npc_agotados", idioma, por_dia=COMBATES_POR_DIA)

        resultado = npc.pelear(
            master.servant, master.intentos_npc, guerra.dia, self.rng, idioma=idioma
        )
        master.intentos_npc += 1
        if resultado.gano:
            subidas = master.servant.ganar_xp(resultado.xp)
            texto = t(
                "bot.npc_victoria", idioma, rival=resultado.rival, xp=resultado.xp
            )
            # El oro, en la misma frase que la XP: es lo mismo, lo que paga
            # haber ganado. Lo cobra el Cog y no `npc.pelear`, igual que la XP,
            # porque el resultado de un combate no sabe de quien es.
            if resultado.oro:
                master.oro += resultado.oro
                texto += t("bot.npc_oro", idioma, oro=resultado.oro)
            if resultado.objeto:
                texto += self.texto_de_la_suelta(guerra, master, resultado.objeto)
            if subidas:
                texto += t("bot.npc_subida", idioma, nivel=subidas[-1])
        else:
            master.derrotas_npc += 1
            texto = t(
                "bot.npc_derrota",
                idioma,
                rival=resultado.rival,
                vida=master.vida_para_la_batalla(),
            )
        self.guardar(guerra)
        cola = "\n".join(resultado.registro[-6:])
        return f"{texto}\n```\n{cola}\n```"

    def arrancar(self, guerra: Guerra) -> str:
        """Invoca los Servants, arranca el dia 1 y cuenta como queda la mesa.

        Lo usan los dos caminos: el lobby que se llena de gente y
        `/empezar-guerra`, que llena lo que falte con la IA.
        """
        guerra.empezar(invocacion.invocar(CATALOGO, self.rng))
        # Aqui se listaban los Servants invocados. Ya no: los de los demas no
        # se dicen, se descubren peleando. Era la filtracion mas gorda de
        # todas, porque salian los seis de los bots de una vez.
        texto = t(
            "bot.guerra_comienza",
            guerra.idioma,
            minutos=TIEMPOS_PREPARACION[guerra.preparacion] // 60,
        )
        self.guardar(guerra)
        return texto + "\n" + t(
            "bot.empezada_con_grial" if guerra.otorga_grial else "bot.empezada_con_bots",
            guerra.idioma,
            personas=plural("personas", len(guerra.humanos), guerra.idioma),
            bots=plural("bots", len(guerra.bots), guerra.idioma),
            minimo_grial=MINIMO_HUMANOS_PARA_GRIAL,
        )

    def textos_del_cierre(
        self, guerra: Guerra, por_plazo: bool = False
    ) -> list[str]:
        """Cierra la preparacion del dia y narra lo que toque.

        Hay dos finales posibles y los dos pasan por aqui:

        - si en alguna batalla hay personas, las batallas quedan **en curso**
          y lo que se narra es que empiezan. El dia lo cierra la ultima
          decision, en `cerrar_si_acabaron_los_combates`.
        - si no hay ninguna persona peleando (una guerra de bots, o todas las
          batallas del dia son entre bots), se resuelven solas y se narra el
          cierre entero de una vez, como antes de que existiera el menu de
          combate.

        `por_plazo` solo cambia la primera linea: conviene que se vea si el
        dia lo cerro el creador o se le acabo el tiempo.
        """
        estado = dia.abrir_combates(guerra, self.rng)
        if estado.acabaron_todos:
            # Nadie a quien esperar: el dia se acaba aqui mismo.
            cierre = dia.cerrar_combates(guerra, estado)
            self.guardar(guerra)
            return self.narrar_cierre(guerra, cierre, por_plazo)
        self.combates[guerra.id] = estado
        self.guardar(guerra)
        return self._narrar_apertura(guerra, estado, por_plazo)

    def _narrar_apertura(
        self, guerra: Guerra, estado: dia.CombatesDelDia, por_plazo: bool
    ) -> list[str]:
        """Que las batallas empiezan. Sin nombrar un Servant ni una habilidad."""
        idioma = guerra.idioma
        nombre = lambda id_: guerra.masters[id_].nombre  # noqa: E731
        lineas = [
            t(
                "bot.cierre_por_plazo" if por_plazo else "bot.cierre_cabecera",
                idioma,
                dia=estado.dia,
            )
        ]
        if estado.invocados:
            lineas.append(
                t(
                    "bot.cierre_invocados",
                    idioma,
                    nombres=", ".join(nombre(i) for i in estado.invocados),
                )
            )
        lineas.append(
            t(
                "bot.combates_abiertos",
                idioma,
                dia=estado.dia,
                cuantas=", ".join(
                    " vs ".join(nombre(i) for i in sorted(c.batalla.combatientes))
                    for c in estado.pendientes
                ),
            )
        )
        if estado.resueltos:
            lineas.append(t("bot.combates_resueltos_solos", idioma))
        if estado.descansan:
            lineas.append(
                t(
                    "bot.cierre_descansan",
                    idioma,
                    nombres=", ".join(nombre(i) for i in estado.descansan),
                )
            )
        return ["\n".join(lineas)]

    def narrar_cierre(
        self,
        guerra: Guerra,
        c: dia.CierreDelDia,
        por_plazo: bool = False,
        por_ia: bool = True,
    ) -> list[str]:
        """Narra un dia ya cerrado: una lista de mensajes para el canal.

        Son varios y no uno solo porque el registro de cada batalla ocupa
        bastante, y Discord corta un mensaje a los 2000 caracteres.

        `por_ia` es si las batallas las resolvio la IA. Cuando las pelearon
        personas no se dice, porque ya lo saben: estuvieron ahi.
        """
        idioma = guerra.idioma
        nombre = lambda id_: guerra.masters[id_].nombre  # noqa: E731

        cabecera = [
            t(
                "bot.cierre_por_plazo" if por_plazo else "bot.cierre_cabecera",
                idioma,
                dia=c.dia,
            )
        ]
        if c.invocados:
            cabecera.append(
                t(
                    "bot.cierre_invocados",
                    idioma,
                    nombres=", ".join(nombre(i) for i in c.invocados),
                )
            )
        if not c.batallas:
            cabecera.append(t("bot.cierre_sin_batallas", idioma))
        else:
            if por_ia:
                cabecera.append(t("bot.cierre_aviso_ia", idioma))
            cabecera.append(t("bot.cierre_registro_privado", idioma))
        mensajes = ["\n".join(cabecera)]

        for b in c.batallas:
            # Aqui va quien peleo y como acabo, nada mas. El registro lo ve
            # cada uno en su menu: sus frases nombran las habilidades, y el
            # nombre de una habilidad delata al Servant.
            texto = t(
                "bot.cierre_batalla",
                idioma,
                grupo=" vs ".join(nombre(i) for i in b.grupo),
            )
            if not b.caidos:
                texto += "\n" + t("bot.cierre_empate", idioma)
            # Una linea por cada uno que cayo, no solo por el primero: si la
            # batalla siguio despues de la votacion puede haber varios.
            for id_ in b.caidos:
                texto += "\n" + t(
                    "bot.cierre_eliminado"
                    if id_ in b.eliminados
                    else "bot.cierre_caido",
                    idioma,
                    master=nombre(id_),
                    derrotas=guerra.masters[id_].derrotas,
                    para_eliminar=DERROTAS_PARA_ELIMINAR,
                )
            mensajes.append(texto)

        final = []
        if c.descansan:
            final.append(
                t(
                    "bot.cierre_descansan",
                    idioma,
                    nombres=", ".join(nombre(i) for i in c.descansan),
                )
            )
        if c.terminada:
            final.append(t("bot.cierre_terminada", idioma))
            if c.grial:
                final.append(
                    t("bot.cierre_gana_el_grial", idioma, master=nombre(c.grial))
                )
                # Los griales se pagan aqui y solo aqui, que es el unico sitio
                # donde se anuncia el Grial, y por el que pasan los tres
                # caminos que cierran un dia. Es lo mismo que `anotar_batalla`
                # con las derrotas: si se pagara en una puerta y no en otra,
                # habria guerras ganadas que no pagan.
                pago = self.pagar_los_griales(guerra)
                if pago:
                    final.append(pago)
            elif c.ganador:
                final.append(
                    t(
                        "bot.cierre_gana_sin_grial",
                        idioma,
                        master=nombre(c.ganador),
                        minimo_grial=MINIMO_HUMANOS_PARA_GRIAL,
                    )
                )
        else:
            final.append(
                t(
                    "bot.cierre_dia_nuevo",
                    idioma,
                    dia=guerra.dia,
                    minutos=TIEMPOS_PREPARACION[guerra.preparacion] // 60,
                )
            )
        mensajes.append("\n".join(final))
        self.guardar(guerra)
        return mensajes

    def aviso_del_menu(self, guerra: Guerra) -> str:
        """El ping a los jugadores, que acompana al boton del canal."""
        menciones = " ".join(f"<@{m.id}>" for m in guerra.humanos)
        return t("bot.aviso_menu", guerra.idioma, menciones=menciones)

    def _menciones(self, guerra: Guerra) -> str:
        return " ".join(f"<@{m.id}>" for m in guerra.humanos)

    def aviso_y_vista_de_despues(
        self, guerra: Guerra
    ) -> tuple[str, discord.ui.View] | tuple[None, None]:
        """El boton que toca dejar en el canal despues de cerrar la preparacion.

        Tres respuestas posibles y una sola puerta, porque las tres formas de
        cerrar el dia tienen que dejar la misma mesa:

        - hay batallas en curso: el boton para abrir la tuya,
        - no hay y la guerra sigue: el menu del dia nuevo,
        - la guerra acabo: nada.
        """
        if self.combates.get(guerra.id) is not None:
            return (
                t(
                    "combate.aviso",
                    guerra.idioma,
                    menciones=self._menciones(guerra),
                    dia=guerra.dia,
                ),
                AbrirCombate(self, guerra),
            )
        if guerra.terminada:
            return None, None
        return self.aviso_del_menu(guerra), self.vista_del_menu(guerra)

    # --- cerrar el dia: una sola puerta para las cuatro formas ---

    def enviar_por(self, interaction: discord.Interaction):
        """Un `enviar` que contesta la primera vez y manda followups despues.

        Hace falta porque las puertas que cierran el dia llegan en dos
        estados: un comando todavia no ha contestado a su interaccion y un
        boton ya lo ha hecho (reescribio el menu). Sin esto, cada puerta tenia
        que acordarse de cual era su caso, y ahi es donde se acaban colando
        las diferencias entre unas y otras.
        """

        async def enviar(texto: str, vista: discord.ui.View | None = None) -> None:
            # `view=None` no es lo mismo que no pasar `view`, asi que se arma
            # el diccionario en vez de pasar siempre el parametro.
            extra = {"view": vista} if vista is not None else {}
            if interaction.response.is_done():
                await interaction.followup.send(texto, **extra)
            else:
                await interaction.response.send_message(texto, **extra)

        return enviar

    def enviar_por_el_canal(self, canal):
        """Lo mismo, hablando por el canal. Es lo que usa el vigilante."""

        async def enviar(texto: str, vista: discord.ui.View | None = None) -> None:
            extra = {"view": vista} if vista is not None else {}
            await canal.send(texto, **extra)

        return enviar

    async def cerrar_el_dia(
        self, guerra: Guerra, enviar, por_plazo: bool = False
    ) -> None:
        """Cierra la preparacion, la narra y **deja la mesa como toca**.

        Las cuatro formas de cerrar un dia pasan por aqui, y es a proposito:
        cerrar la preparacion es solo la mitad del trabajo, y la otra mitad
        —dejar en el canal el boton que toque— se olvida sola. Las cuatro son
        `/empezar-batallas`, el boton rojo del menu, decirse listo el ultimo y
        el vigilante de plazos.

        `enviar` es por donde se habla: `enviar_por` detras de una interaccion,
        `enviar_por_el_canal` cuando no hay ninguna.
        """
        for mensaje in self.textos_del_cierre(guerra, por_plazo=por_plazo):
            await enviar(mensaje)
        aviso, vista = self.aviso_y_vista_de_despues(guerra)
        if vista is not None:
            await enviar(aviso, vista)

    def cierre_de_los_combates(self, guerra: Guerra) -> list[str] | None:
        """Cierra el dia si ya acabaron todas las batallas, y lo narra.

        Devuelve `None` si todavia queda alguna. Es el unico sitio donde se
        pasa de las batallas al dia siguiente, y lo llaman las dos puertas que
        pueden acabar la ultima batalla: una decision de alguien y el plazo
        del turno.
        """
        estado = self.combates.get(guerra.id)
        if estado is None:
            return None
        dia.recoger(guerra, estado)
        if not estado.acabaron_todos:
            return None
        cierre = dia.cerrar_combates(guerra, estado)
        del self.combates[guerra.id]
        # Las batallas se acabaron, asi que las mesas ya no apuntan a nada: el
        # menu de combate que tenian delante es de un dia que ya paso. Se
        # sueltan aqui, en el mismo sitio que `self.combates`, para que las dos
        # cosas que viven en memoria mueran juntas.
        self.olvidar_mesas(guerra)
        self.guardar(guerra)
        # `por_ia=False`: no hace falta avisar de quien peleo las batallas
        # cuando las pelearon ellos. El registro sigue siendo de cada uno.
        return self.narrar_cierre(guerra, cierre, por_ia=False)

    async def cerrar_si_acabaron_los_combates(
        self, interaction: discord.Interaction, guerra: Guerra
    ) -> None:
        """Lo anterior, contado en el canal detras de una interaccion.

        Lo llama **cada** decision de combate, porque la ultima de ellas es la
        que cierra el dia y no se sabe cual va a ser. Es barato cuando no toca
        y olvidarlo dejaria la guerra parada para siempre.
        """
        mensajes = self.cierre_de_los_combates(guerra)
        if mensajes is None:
            return
        for mensaje in mensajes:
            await interaction.followup.send(mensaje, ephemeral=False)
        aviso, vista = self.aviso_y_vista_de_despues(guerra)
        if vista is not None:
            await interaction.followup.send(aviso, view=vista, ephemeral=False)

    async def cerrar_combates_en_el_canal(self, guerra: Guerra) -> None:
        """Lo mismo, hablando por el canal. Lo usa el vigilante de plazos."""
        mensajes = self.cierre_de_los_combates(guerra)
        if mensajes is None:
            return
        canal = self.bot.get_channel(int(guerra.canal_id))
        if canal is None:
            registro.warning("no veo el canal de la guerra %s", guerra.id)
            return
        for mensaje in mensajes:
            await canal.send(mensaje)
        aviso, vista = self.aviso_y_vista_de_despues(guerra)
        if vista is not None:
            await canal.send(aviso, view=vista)

    # --- comandos ---

    # Las etiquetas salen del catalogo, como todo lo que lee el jugador. Se
    # eligen al definir el comando, antes de que exista ninguna guerra, asi
    # que son las mismas para todos: por eso las de idioma se escriben igual
    # en los dos, "ES (español)" y "EN (english)".
    @app_commands.command(
        name=etiqueta("cmd.crear.nombre"), description=etiqueta("cmd.crear.ayuda")
    )
    @app_commands.rename(
        preparacion=etiqueta("cmd.opcion.preparacion"),
        idioma=etiqueta("cmd.opcion.idioma"),
    )
    @app_commands.describe(
        preparacion=etiqueta("cmd.opcion.preparacion.ayuda"),
        idioma=etiqueta("cmd.opcion.idioma.ayuda"),
    )
    @app_commands.choices(
        preparacion=[
            app_commands.Choice(name=etiqueta("preparacion.30m"), value="30m"),
            app_commands.Choice(name=etiqueta("preparacion.1h"), value="1h"),
            app_commands.Choice(name=etiqueta("preparacion.24h"), value="24h"),
        ],
        idioma=[
            app_commands.Choice(name=t("idioma.es"), value="es"),
            app_commands.Choice(name=t("idioma.en"), value="en"),
        ],
    )
    async def crear_guerra(
        self,
        interaction: discord.Interaction,
        preparacion: app_commands.Choice[str],
        idioma: app_commands.Choice[str] | None = None,
    ) -> None:
        canal = interaction.channel_id
        # Una guerra terminada no estorba: se queda en memoria para que
        # `/estado-guerra` siga contando como acabo, pero el canal esta libre.
        # Antes bloqueaba el canal hasta reiniciar el bot, porque al cargarlas
        # de la base de datos las terminadas no vuelven y en memoria si.
        anterior = self.guerras.get(canal)
        if anterior is not None and not anterior.terminada:
            await interaction.response.send_message(
                t("bot.ya_hay_guerra", anterior.idioma), ephemeral=True
            )
            return
        guerra = Guerra(
            id=str(canal),
            canal_id=str(canal),
            preparacion=preparacion.value,
            idioma=idioma.value if idioma else self._idioma(interaction),
        )
        # El creador es el primero que se inscribe, y el unico que puede
        # empezar la guerra con bots.
        guerra.inscribir(str(interaction.user.id), interaction.user.display_name)
        self.guerras[canal] = guerra
        self.guardar(guerra)
        await interaction.response.send_message(
            t(
                "bot.guerra_abierta",
                guerra.idioma,
                preparacion=t(f"preparacion.{guerra.preparacion}", guerra.idioma),
                minimo=MINIMO_MASTERS,
                minimo_grial=MINIMO_HUMANOS_PARA_GRIAL,
            )
        )

    @app_commands.command(
        name=etiqueta("cmd.unirse.nombre"), description=etiqueta("cmd.unirse.ayuda")
    )
    async def unirse_a_guerra(self, interaction: discord.Interaction) -> None:
        guerra = self._guerra(interaction.channel_id)
        if guerra is None:
            await interaction.response.send_message(
                t("bot.no_hay_guerra_abierta", self._idioma(interaction)),
                ephemeral=True,
            )
            return
        try:
            guerra.inscribir(str(interaction.user.id), interaction.user.display_name)
        except (ValueError, RuntimeError) as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return

        self.guardar(guerra)
        texto = t(
            "bot.se_inscribe",
            guerra.idioma,
            nombre=interaction.user.display_name,
            inscritos=len(guerra.masters),
            minimo=MINIMO_MASTERS,
        )
        if not guerra.puede_empezar:
            await interaction.response.send_message(texto)
            return
        await interaction.response.send_message(texto + self.arrancar(guerra))
        await self._abrir_menus(interaction, guerra)

    @app_commands.command(
        name=etiqueta("cmd.empezar.nombre"),
        description=etiqueta("cmd.empezar.ayuda"),
    )
    async def empezar_guerra(self, interaction: discord.Interaction) -> None:
        guerra = self._guerra(interaction.channel_id)
        if guerra is None:
            await interaction.response.send_message(
                t("bot.no_hay_guerra_abierta", self._idioma(interaction)),
                ephemeral=True,
            )
            return
        if str(interaction.user.id) != guerra.creador_id:
            await interaction.response.send_message(
                t("bot.solo_el_creador", guerra.idioma), ephemeral=True
            )
            return
        try:
            guerra.rellenar_con_bots()
        except (ValueError, RuntimeError) as e:
            await interaction.response.send_message(str(e), ephemeral=True)
            return
        await interaction.response.send_message(self.arrancar(guerra).lstrip())
        await self._abrir_menus(interaction, guerra)

    def vista_del_menu(self, guerra: Guerra) -> AbrirMenu:
        """El boton publico del canal. Lo usan los comandos y el vigilante."""
        return AbrirMenu(self, guerra)

    async def _abrir_menus(
        self, interaction: discord.Interaction, guerra: Guerra
    ) -> None:
        """Menciona a los jugadores y les deja el boton para abrir su menu."""
        await interaction.followup.send(
            self.aviso_del_menu(guerra), view=self.vista_del_menu(guerra)
        )

    @app_commands.command(
        name=etiqueta("cmd.estado.nombre"), description=etiqueta("cmd.estado.ayuda")
    )
    async def estado_guerra(self, interaction: discord.Interaction) -> None:
        guerra = self._guerra(interaction.channel_id)
        if guerra is None:
            await interaction.response.send_message(
                t("bot.no_hay_guerra", self._idioma(interaction)), ephemeral=True
            )
            return
        # En privado, y no por timidez: lo que se ve depende de quien mira, y
        # un mensaje publico lo leeria todo el canal.
        master = guerra.masters.get(str(interaction.user.id))
        await interaction.response.send_message(
            self.texto_estado(guerra, master), ephemeral=True
        )

    @app_commands.command(
        name=etiqueta("cmd.batallas.nombre"),
        description=etiqueta("cmd.batallas.ayuda"),
    )
    async def empezar_batallas(self, interaction: discord.Interaction) -> None:
        guerra = self._guerra(interaction.channel_id)
        if guerra is None:
            await interaction.response.send_message(
                t("bot.no_hay_guerra", self._idioma(interaction)), ephemeral=True
            )
            return
        if str(interaction.user.id) != guerra.creador_id:
            await interaction.response.send_message(
                t("bot.solo_el_creador", guerra.idioma), ephemeral=True
            )
            return
        # Pulsarlo es decir que el creador acabo su dia: seria absurdo
        # pedirle que marque listo y despues cierre.
        guerra.masters[guerra.creador_id].listo = True
        aviso = self.aviso_si_no_se_puede_cerrar(guerra)
        if aviso:
            await interaction.response.send_message(aviso, ephemeral=True)
            return
        await self._contar_cierre(interaction, guerra)

    def puede_cerrarse_ya(self, guerra: Guerra) -> bool:
        """Si no queda nadie a quien esperar y el dia se puede cerrar solo.

        Es lo que mira la puerta nueva: al decirse listo el ultimo, las
        batallas empiezan sin que nadie pulse nada. Pregunta exactamente lo
        mismo que el boton rojo (`aviso_si_no_se_puede_cerrar`) y no una
        version parecida, porque si el boton y el cierre automatico mirasen
        cosas distintas habria dias que no cierra ninguno de los dos.
        """
        return (
            guerra.fase is Fase.PREPARACION
            and not guerra.terminada
            and self.aviso_si_no_se_puede_cerrar(guerra) is None
        )

    def aviso_si_no_se_puede_cerrar(self, guerra: Guerra) -> str | None:
        """Por que no se puede cerrar el dia, o `None` si si se puede."""
        faltan = guerra.faltan_por_estar_listos
        if faltan:
            return t(
                "bot.cierre_faltan_listos",
                guerra.idioma,
                nombres=", ".join(m.nombre for m in faltan),
            )
        if not dia.puede_cerrar(guerra, guerra.creador_id):
            return t("bot.no_se_puede_cerrar", guerra.idioma)
        return None

    def terminar_guerra(self, guerra: Guerra) -> str | None:
        """Cierra la guerra a mano, sin ganador. El motivo si no se puede.

        `Guerra.cancelar()` hace lo suyo, pero esta accion tiene que limpiar
        ademas lo que vive **fuera** de la guerra: la batalla en curso esta en
        `self.combates`, no dentro de la `Guerra`, y si no se borra aqui se
        queda colgada y el vigilante sigue intentando avanzarla.

        Guardar al final no es opcional: es lo que pone `terminada_en` en la
        base de datos, y por eso un reinicio no revive la guerra cerrada.
        """
        if guerra.terminada:
            return t("terminar.ya_acabo", guerra.idioma)
        guerra.cancelar()
        self.combates.pop(guerra.id, None)
        self.olvidar_mesas(guerra)
        self.turnos_por_repartir.pop(guerra.id, None)
        self.guardar(guerra)
        return None

    def rendir_al_master(self, guerra: Guerra, master: Master) -> tuple[str, str]:
        """Saca a alguien de la guerra. Devuelve lo privado y lo publico.

        Lo publico dice **quien** se fue y cuantos quedan, y nada mas: no
        nombra Servants ni habilidades, igual que el resto de lo que sale al
        canal. Si con eso la guerra se acaba, lo publico ya cuenta el final.

        Lo que limpia aqui y no en `Guerra.rendirse` es lo que vive fuera de
        la guerra: la batalla en curso de `self.combates` y las mesas. Es lo
        mismo que hace `terminar_guerra`, y por la misma razon.
        """
        idioma = guerra.idioma
        se_acabo = guerra.rendirse(master.id)
        if se_acabo:
            self.combates.pop(guerra.id, None)
            self.olvidar_mesas(guerra)
            self.turnos_por_repartir.pop(guerra.id, None)
        else:
            combate = self.combates.get(guerra.id)
            if combate is not None:
                # Se rindio con una batalla en curso: la suya se queda sin
                # el, y si era la ultima el dia tiene que poder cerrarse.
                dia.rendir_en_combates(combate, master.id)
        self.guardar(guerra)
        privado = t("rendirse.hecho", idioma)
        publico = t(
            "rendirse.publico", idioma, master=master.nombre, quedan=len(guerra.activos)
        )
        if se_acabo:
            g = guerra.ganador()
            if g is None:
                publico += "\n" + t("rendirse.sin_nadie", idioma)
                return privado, publico
            publico += "\n" + t("rendirse.ultimo_en_pie", idioma, master=g.nombre)
            # **El segundo sitio que anuncia el Grial, y por eso el segundo
            # que lo paga.** El otro es `narrar_cierre`, y hasta hoy era el
            # unico; desde que una guerra se puede acabar por retiradas, una
            # de mas de 5 personas paga por aqui. Si se anunciara sin pagar,
            # el ganador leeria que gano un grial que no tiene.
            pago = self.pagar_los_griales(guerra)
            if pago:
                publico += "\n" + pago
            else:
                publico += "\n" + t(
                    "rendirse.sin_grial",
                    idioma,
                    minimo=MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA,
                )
        return privado, publico

    def aviso_del_final(self, guerra: Guerra) -> str:
        """Lo que se publica en el canal cuando se cierra la guerra a mano.

        Va al canal, asi que no nombra ningun Servant ni ninguna habilidad:
        la guerra se cierra, pero lo que llevaba cada quien sigue siendo
        suyo. Ver la regla del secreto en CLAUDE.md.
        """
        return t(
            "bot.guerra_terminada",
            guerra.idioma,
            dia=guerra.dia,
            en_pie=len(guerra.activos),
        )

    async def _contar_cierre(
        self, interaction: discord.Interaction, guerra: Guerra
    ) -> None:
        """Cierra el dia y lo cuenta en el canal, mensaje a mensaje.

        El primero responde a la interaccion y los demas van detras; si la
        guerra sigue, al final se vuelve a dejar el boton del menu, porque
        empieza un dia nuevo y todos tienen cosas que hacer. De eso se encarga
        `cerrar_el_dia`, que es por donde pasan las cuatro puertas.
        """
        await self.cerrar_el_dia(guerra, self.enviar_por(interaction))

    @app_commands.command(
        name=etiqueta("cmd.terminar.nombre"),
        description=etiqueta("cmd.terminar.ayuda"),
    )
    async def terminar(self, interaction: discord.Interaction) -> None:
        """Cierra la guerra del canal sin ganador, previa confirmacion."""
        guerra = self._guerra(interaction.channel_id)
        if guerra is None:
            await interaction.response.send_message(
                t("bot.no_hay_guerra", self._idioma(interaction)), ephemeral=True
            )
            return
        if str(interaction.user.id) != guerra.creador_id:
            await interaction.response.send_message(
                t("bot.solo_el_creador_termina", guerra.idioma), ephemeral=True
            )
            return
        if guerra.terminada:
            await interaction.response.send_message(
                t("terminar.ya_acabo", guerra.idioma), ephemeral=True
            )
            return
        # En privado: la pregunta es solo para el creador, y si se arrepiente
        # nadie tiene por que haber visto el susto.
        await interaction.response.send_message(
            t("terminar.pregunta", guerra.idioma, en_pie=len(guerra.activos)),
            view=ConfirmarTerminar(self, guerra),
            ephemeral=True,
        )

    @app_commands.command(
        name=etiqueta("cmd.invocar.nombre"),
        description=etiqueta("cmd.invocar.ayuda"),
    )
    async def invocar(self, interaction: discord.Interaction) -> None:
        guerra = self._guerra(interaction.channel_id)
        master = guerra.masters.get(str(interaction.user.id)) if guerra else None
        if guerra is None or master is None:
            await interaction.response.send_message(
                t("bot.no_en_guerra", self._idioma(interaction, guerra)),
                ephemeral=True,
            )
            return
        privado, publico = self.texto_invocacion(guerra, master)
        # Igual que el boton del menu: el arte en lo privado y nunca en el
        # canal. Los dos caminos tienen que dejar lo mismo.
        await interaction.response.send_message(
            privado,
            embed=self.arte_del_servant(master.servant),
            ephemeral=True,
        )
        if publico:
            await interaction.followup.send(publico, ephemeral=False)

    @app_commands.command(
        name=etiqueta("cmd.estadisticas.nombre"),
        description=etiqueta("cmd.estadisticas.ayuda"),
    )
    async def estadisticas(self, interaction: discord.Interaction) -> None:
        guerra = self._guerra(interaction.channel_id)
        master = guerra.masters.get(str(interaction.user.id)) if guerra else None
        if master is None:
            await interaction.response.send_message(
                t("bot.sin_servant", self._idioma(interaction, guerra)),
                ephemeral=True,
            )
            return
        if master.servant is None:
            # Esta en la guerra pero no ha invocado: el menu le sirve para eso.
            await interaction.response.send_message(
                t("bot.invoca_primero", guerra.idioma),
                view=MenuAccion(self, guerra, master),
                ephemeral=True,
            )
            return
        # El mismo orden y la misma pantalla que el boton del menu: texto,
        # arte y menu. Si los dos caminos no dejaran lo mismo, se notaria.
        await interaction.response.send_message(
            self.texto_ficha(guerra, master),
            embed=self.arte_del_servant(master.servant),
            view=MenuAccion(self, guerra, master),
            ephemeral=True,
        )

    @app_commands.command(
        name=etiqueta("cmd.cuenta.nombre"),
        description=etiqueta("cmd.cuenta.ayuda"),
    )
    async def mi_cuenta(self, interaction: discord.Interaction) -> None:
        """Los griales y las guerras ganadas, que no son de ninguna guerra.

        Es el unico comando que **no necesita una guerra en el canal**, y por
        eso existe: la cuenta vive en su propia tabla y sobrevive a todas, asi
        que hasta ahora no habia donde mirarla fuera de la tienda. El idioma
        sale de Discord cuando no hay guerra, porque no hay guerra que lo
        diga.
        """
        guerra = self._guerra(interaction.channel_id)
        idioma = self._idioma(interaction, guerra)
        cuenta = self.cuenta_de(str(interaction.user.id))
        explicado = t(
            "cuenta.sin_nada" if not cuenta.guerras_ganadas else "moneda.griales_explicado",
            idioma,
        )
        await interaction.response.send_message(
            t(
                "cuenta.resumen",
                idioma,
                griales=cuenta.griales,
                ganadas=cuenta.guerras_ganadas,
                explicado=explicado,
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name=etiqueta("cmd.entrenar.nombre"),
        description=etiqueta("cmd.entrenar.ayuda"),
    )
    async def entrenar(self, interaction: discord.Interaction) -> None:
        guerra = self._guerra(interaction.channel_id)
        master = guerra.masters.get(str(interaction.user.id)) if guerra else None
        if master is None:
            await interaction.response.send_message(
                t("bot.no_en_guerra", self._idioma(interaction, guerra)),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            self.pelear_npc(guerra, master), ephemeral=True
        )
