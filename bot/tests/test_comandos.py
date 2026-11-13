"""Pruebas de los comandos y del menu de Discord, sin Discord.

Es la unica parte que no se puede probar con el simulador, y donde se esconden
los errores tontos: un texto al que le falta un dato revienta al responder, no
al arrancar. Aqui se llaman las funciones de verdad con una interaccion de
mentira y se comprueba lo que contestan.

Si `discord` no esta instalado (el entorno de las demas pruebas no lo
necesita), estas se saltan.
"""

from __future__ import annotations

import asyncio
import unittest

from src.game import objetos, tienda
from src.game.battle import Accion, Decision
from src.game.war import DERROTAS_PARA_ELIMINAR, Fase

try:
    import discord  # noqa: F401

    HAY_DISCORD = True
except ImportError:  # pragma: no cover
    HAY_DISCORD = False


class Buzon:
    """Recoge lo que el bot envia, sea respuesta, followup o edicion.

    Guarda tambien los `embed`, que es donde va el arte de un Servant: el
    mensaje lleva la URL, nunca el archivo. Ver `tests/test_arte.py`.
    """

    def __init__(self) -> None:
        self.mensajes: list[tuple[str, bool, object]] = []
        self.embeds: list[object] = []
        # Si ya se contesto a la interaccion. Discord solo deja contestar una
        # vez y despues hay que mandar followups, asi que quien cierra el dia
        # tiene que poder preguntarlo (`cog.enviar_por`).
        self.respondido = False

    def is_done(self) -> bool:
        return self.respondido

    def _apuntar(self, texto: str, privado: bool, vista: object, embed: object) -> None:
        self.mensajes.append((texto, privado, vista))
        self.embeds.append(embed)

    async def send_message(
        self,
        texto: str = "",
        *,
        ephemeral: bool = False,
        view: object = None,
        embed: object = None,
    ) -> None:
        self.respondido = True
        self._apuntar(texto, ephemeral, view, embed)

    async def send(
        self,
        texto: str = "",
        *,
        ephemeral: bool = False,
        view: object = None,
        embed: object = None,
    ) -> None:
        self._apuntar(texto, ephemeral, view, embed)

    async def edit_message(
        self,
        content: str | None = None,
        *,
        view: object = None,
        embed: object = None,
        **_,
    ) -> None:
        # Reescribir el mensaje tambien es contestar: despues de esto solo
        # caben followups.
        self.respondido = True
        self._apuntar(
            content if content is not None else "(menu actualizado)",
            True,
            view,
            embed,
        )


class Ediciones:
    """Las reescrituras del mensaje efimero que ya se habia mandado.

    Es lo que hace `interaction.edit_original_response`, que es como el bot le
    reescribe el menu a alguien **despues** de haberle contestado. Sin esto no
    se puede probar que a quien no cierra el turno se le avisa.
    """

    def __init__(self) -> None:
        self.hechas: list[tuple[str, object]] = []

    @property
    def ultima(self) -> tuple[str, object]:
        return self.hechas[-1]


class Usuario:
    def __init__(self, id_: int, nombre: str) -> None:
        self.id = id_
        self.display_name = nombre


class Interaccion:
    """Lo minimo que un comando mira de una interaccion de Discord."""

    def __init__(
        self, usuario: int = 1, canal: int = 100, locale: str = "es-ES"
    ) -> None:
        self.user = Usuario(usuario, f"Master {usuario}")
        self.channel_id = canal
        self.locale = locale
        self.buzon = Buzon()
        self.response = self.buzon
        self.followup = self.buzon
        self.ediciones = Ediciones()

    async def edit_original_response(
        self, content: str = "", *, view: object = None, **_
    ) -> None:
        """Reescribe el mensaje efimero que ya se mando.

        Discord lo permite durante 15 minutos, y es la unica forma de
        refrescarle el menu a alguien que no ha tocado nada.
        """
        self.ediciones.hechas.append((content, view))

    @property
    def mensajes(self) -> list[str]:
        return [m[0] for m in self.buzon.mensajes]

    @property
    def ultimo(self) -> str:
        return self.buzon.mensajes[-1][0]

    @property
    def todo(self) -> str:
        return "\n".join(self.mensajes)

    def vista(self, indice: int = -1) -> object:
        return self.buzon.mensajes[indice][2]

    def embed(self, indice: int = -1) -> object:
        return self.buzon.embeds[indice]


class Eleccion:
    """Un `app_commands.Choice` de mentira."""

    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value


def correr(corrutina) -> None:
    asyncio.run(corrutina)


def correr_valor(corrutina):
    """Como `correr`, pero devuelve lo que devuelva la corrutina.

    Hace falta para los `interaction_check`, que contestan `True` o `False`.
    """
    return asyncio.run(corrutina)


@unittest.skipUnless(HAY_DISCORD, "discord.py no esta instalado")
class PruebaComandos(unittest.TestCase):
    def setUp(self) -> None:
        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        self.preparacion = Eleccion("1 hora", "1h")

    def _crear(self, idioma: str | None = None, canal: int = 100) -> Interaccion:
        i = Interaccion(usuario=1, canal=canal)
        correr(
            self.cog.crear_guerra.callback(
                self.cog,
                i,
                self.preparacion,
                Eleccion(idioma, idioma) if idioma else None,
            )
        )
        return i

    def _empezar(self, canal: int = 100, invocar: bool = True) -> Interaccion:
        """Empieza la guerra y, salvo que se pida lo contrario, invoca.

        Desde que la invocacion la pide cada Master, empezar la guerra no deja
        a nadie con Servant: casi todas las pruebas quieren el paso siguiente
        ya dado. Las que van de la invocacion pasan `invocar=False`.
        """
        i = Interaccion(usuario=1, canal=canal)
        correr(self.cog.empezar_guerra.callback(self.cog, i))
        if invocar:
            correr(self.cog.invocar.callback(self.cog, Interaccion(1, canal)))
        return i

    def _dia_con_batalla_de_la_persona(self) -> Interaccion:
        """Cierra la preparacion dejando seguro una batalla con persona dentro.

        Declarar un ataque **no** basta: si la cadena del rival ya llega a 4 y
        no queda nadie libre, al que no cupo le toca descansar (es la regla,
        ver `Guerra._redirigir`), y eso pasa el 8% de las veces con seis bots.
        Asi que se prueba con una semilla y otra hasta que entre.
        """
        import random

        from src.commands import ComandosGuerra

        for semilla in range(40):
            self.cog = ComandosGuerra(bot=None)
            self.cog.rng = random.Random(semilla)
            self._crear()
            self._empezar()
            self.cog.guerras[100].declarar_ataque("1", "bot:1")
            i = Interaccion(usuario=1)
            correr(self.cog.empezar_batallas.callback(self.cog, i))
            if self.cog.combates.get(self.cog.guerras[100].id) is not None:
                return i
        self.skipTest("ninguna semilla dejo pelear a la persona")

    def _acabar_el_dia(self, canal: int = 100) -> str:
        """Acaba con la IA las batallas que el dia dejo en curso.

        Desde que hay menu de combate, cerrar la preparacion **no** cierra el
        dia: deja las batallas esperando decisiones. Las pruebas que van del
        menu deciden a mano; a las demas les basta con que el dia pase, y esto
        es lo mismo que hace el plazo del turno cuando nadie contesta.

        Devuelve lo que se habria contado en el canal.
        """
        guerra = self.cog.guerras[canal]
        estado = self.cog.combates.get(guerra.id)
        if estado is None:
            return ""
        for combate in estado.pendientes:
            while not combate.terminado:
                combate.avanzar_con_ia()
        return "\n".join(self.cog.cierre_de_los_combates(guerra) or [])

    def test_las_etiquetas_del_desplegable(self) -> None:
        """Las del idioma son iguales en los dos, porque se eligen antes.

        Y van bien escritas, con ene: solo se ven en Discord, nunca en la
        consola, que es lo que obliga al resto del texto a ir sin acentos.
        """
        parametros = {p.name: p for p in self.cog.crear_guerra.parameters}
        idiomas = [c.name for c in parametros["idioma"].choices]
        self.assertEqual(idiomas, ["ES (español)", "EN (english)"])
        # Lo demas sale en el idioma por defecto, y Discord lo traduce.
        preparacion = [c.name for c in parametros["preparacion"].choices]
        self.assertEqual(preparacion, ["30 minutes", "1 hour", "24 hours"])

    def test_los_nombres_de_los_comandos(self) -> None:
        """Los de por defecto son los ingleses; el espanol es traduccion."""
        nombres = {c.name for c in self.cog.get_app_commands()}
        self.assertEqual(
            nombres,
            {
                "create-war",
                "join-war",
                "start-war",
                "war-status",
                "start-battles",
                "end-war",
                "summon",
                "stats",
                "train",
                # El unico que no necesita una guerra en el canal: la cuenta
                # de griales no es de ninguna guerra.
                "my-account",
            },
        )

    def test_los_comandos_tienen_nombre_en_ingles(self) -> None:
        """Quien tenga Discord en ingles vera /create-war, no /crear-guerra."""
        from discord import Locale
        from discord.app_commands import locale_str

        from src.commands import Traductor

        tr = Traductor()
        etiqueta = locale_str("create-war", clave="cmd.crear.nombre")
        self.assertEqual(
            correr_valor(tr.translate(etiqueta, Locale.american_english, None)),
            "create-war",
        )
        self.assertEqual(
            correr_valor(tr.translate(etiqueta, Locale.spain_spanish, None)),
            "crear-guerra",
        )
        # Un idioma que no tenemos se queda con el nombre por defecto.
        self.assertIsNone(
            correr_valor(tr.translate(etiqueta, Locale.french, None))
        )
        # Y un texto sin clave tampoco se traduce.
        self.assertIsNone(
            correr_valor(
                tr.translate(locale_str("hola"), Locale.american_english, None)
            )
        )

    def test_los_nombres_valen_para_discord(self) -> None:
        """Discord rechaza nombres con mayusculas, espacios o acentos."""
        import re

        from src.game.textos import IDIOMAS, TEXTOS

        permitido = re.compile(r"^[a-z0-9_-]{1,32}$")
        nombres = [
            (clave, idioma, frases[idioma])
            for clave, frases in TEXTOS.items()
            if clave.startswith("cmd.") and ".ayuda" not in clave
            for idioma in IDIOMAS
        ]
        self.assertTrue(nombres)
        for clave, idioma, nombre in nombres:
            self.assertRegex(nombre, permitido, f"{clave} en {idioma}")

    def test_crear_abre_el_lobby(self) -> None:
        i = self._crear()
        self.assertIn("Guerra abierta", i.ultimo)
        self.assertIn("/unirse-a-guerra", i.ultimo)

    def test_no_se_abren_dos_guerras_en_un_canal(self) -> None:
        self._crear()
        i = self._crear()
        self.assertIn("Ya hay una guerra abierta", i.ultimo)

    def test_crear_en_ingles(self) -> None:
        i = self._crear(idioma="en")
        self.assertIn("War open", i.ultimo)
        self.assertIn("Grail", i.ultimo)

    def test_unirse_y_arrancar_con_siete(self) -> None:
        self._crear()
        for n in range(2, 8):
            i = Interaccion(usuario=n)
            correr(self.cog.unirse_a_guerra.callback(self.cog, i))
        self.assertIn("La guerra comienza", i.todo)
        self.assertIn("El Grial esta en juego", i.todo)
        guerra = self.cog.guerras[100]
        self.assertEqual(guerra.dia, 1)
        self.assertEqual(len(guerra.humanos), 7)

    def test_al_empezar_se_menciona_a_todos_con_el_boton(self) -> None:
        from src.commands import AbrirMenu

        self._crear()
        for n in range(2, 8):
            i = Interaccion(usuario=n)
            correr(self.cog.unirse_a_guerra.callback(self.cog, i))
        # El ultimo mensaje es el aviso con el boton, y menciona a los siete.
        for n in range(1, 8):
            self.assertIn(f"<@{n}>", i.ultimo)
        self.assertIsInstance(i.vista(), AbrirMenu)

    def test_empezar_llena_con_bots_y_avisa_que_no_hay_grial(self) -> None:
        self._crear()
        i = self._empezar()
        self.assertIn("La guerra comienza", i.todo)
        self.assertIn("no entrega el Grial", i.todo)
        guerra = self.cog.guerras[100]
        self.assertEqual(len(guerra.bots), 6)
        self.assertEqual(guerra.dia, 1)
        # El aviso menciona solo a la persona, no a los bots.
        self.assertIn("<@1>", i.ultimo)
        self.assertNotIn("bot:", i.ultimo)

    def test_al_empezar_la_persona_no_tiene_servant_y_los_bots_si(self) -> None:
        self._crear()
        i = self._empezar(invocar=False)
        guerra = self.cog.guerras[100]
        self.assertIsNone(guerra.masters["1"].servant)
        self.assertTrue(all(m.servant for m in guerra.bots))
        self.assertIn("cuando quiera", i.todo)

    def test_invocar_da_el_servant_y_lo_cuenta_en_el_canal(self) -> None:
        self._crear()
        self._empezar(invocar=False)
        i = Interaccion(usuario=1)
        correr(self.cog.invocar.callback(self.cog, i))
        guerra = self.cog.guerras[100]
        servant = guerra.masters["1"].servant
        self.assertIsNotNone(servant)
        privado, es_privado, _ = i.buzon.mensajes[0]
        self.assertIn(servant.nombre, privado)
        self.assertIn("Sellos de Comando", privado)
        self.assertTrue(es_privado)
        # Y el canal se entera, porque la invocacion es publica.
        publico, es_privado, _ = i.buzon.mensajes[1]
        self.assertIn("Master 1", publico)
        self.assertIn("Ya estan los siete", publico)
        self.assertFalse(es_privado)

    def test_no_se_invoca_dos_veces(self) -> None:
        self._crear()
        self._empezar()
        i = Interaccion(usuario=1)
        correr(self.cog.invocar.callback(self.cog, i))
        self.assertIn("Ya tienes", i.ultimo)
        self.assertEqual(len(i.buzon.mensajes), 1, "nada en el canal")

    def test_sin_invocar_no_se_entrena(self) -> None:
        self._crear()
        self._empezar(invocar=False)
        i = Interaccion(usuario=1)
        correr(self.cog.entrenar.callback(self.cog, i))
        self.assertIn("Primero invoca", i.ultimo)
        self.assertEqual(self.cog.guerras[100].masters["1"].intentos_npc, 0)

    def test_las_estadisticas_sin_invocar_ofrecen_el_menu(self) -> None:
        from src.commands import MenuAccion

        self._crear()
        self._empezar(invocar=False)
        i = Interaccion(usuario=1)
        correr(self.cog.estadisticas.callback(self.cog, i))
        self.assertIn("Primero invoca", i.ultimo)
        self.assertIsInstance(i.vista(), MenuAccion)

    def test_el_estado_dice_quien_no_ha_invocado(self) -> None:
        self._crear()
        self._empezar(invocar=False)
        i = Interaccion(usuario=1)
        correr(self.cog.estado_guerra.callback(self.cog, i))
        self.assertIn("Master 1 - sin invocar todavia", i.ultimo)

    def test_empezar_batallas_abre_las_batallas_y_no_cierra_el_dia(self) -> None:
        """El comando acaba la preparacion; el dia lo cierra la ultima batalla."""
        from src.commands import AbrirCombate

        i = self._dia_con_batalla_de_la_persona()
        guerra = self.cog.guerras[100]
        self.assertEqual(guerra.dia, 1, "el dia no pasa hasta que se pelee")
        self.assertEqual(guerra.fase, Fase.BATALLA)
        self.assertIn("La preparacion del dia 1 se cierra", i.todo)
        self.assertIn("estan en marcha", i.todo)
        # Y el boton del canal es el de abrir tu batalla, no el del menu.
        self.assertIsInstance(i.vista(), AbrirCombate)

    def test_cuando_se_acaban_las_batallas_el_dia_pasa(self) -> None:
        self._dia_con_batalla_de_la_persona()
        contado = self._acabar_el_dia()
        guerra = self.cog.guerras[100]
        self.assertEqual(guerra.dia, 2)
        self.assertEqual(guerra.fase, Fase.PREPARACION)
        self.assertIn("Batalla:", contado)
        self.assertIn("Empieza el dia 2", contado)

    def test_empezar_batallas_invoca_por_quien_no_lo_hizo(self) -> None:
        self._crear()
        self._empezar(invocar=False)
        i = Interaccion(usuario=1)
        correr(self.cog.empezar_batallas.callback(self.cog, i))
        self.assertIsNotNone(self.cog.guerras[100].masters["1"].servant)
        self.assertIn("El ritual se completa por", i.todo)

    def test_solo_el_creador_empieza_las_batallas(self) -> None:
        self._crear()
        otro = Interaccion(usuario=2)
        correr(self.cog.unirse_a_guerra.callback(self.cog, otro))
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        i = Interaccion(usuario=2)
        correr(self.cog.empezar_batallas.callback(self.cog, i))
        self.assertIn("Solo quien abrio la guerra", i.ultimo)
        self.assertEqual(self.cog.guerras[100].dia, 1, "el dia no se movio")

    def _con_dos_personas(self) -> None:
        """Una guerra con otra persona dentro, para lo de esperarse."""
        self._crear()
        correr(self.cog.unirse_a_guerra.callback(self.cog, Interaccion(usuario=2)))
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))

    def _nombres_de_servants(self, guerra) -> list[str]:
        return [
            m.servant.nombre for m in guerra.masters.values() if m.servant
        ]

    def test_el_arranque_no_dice_que_servant_lleva_nadie(self) -> None:
        self._crear()
        i = self._empezar(invocar=False)
        guerra = self.cog.guerras[100]
        # Los 6 bots ya invocaron: antes salian los seis en el canal.
        self.assertEqual(len(self._nombres_de_servants(guerra)), 6)
        for nombre in self._nombres_de_servants(guerra):
            self.assertNotIn(nombre, i.todo)
        self.assertIn("se descubre peleando", i.todo)

    def test_invocar_no_dice_a_quien_en_el_canal(self) -> None:
        self._crear()
        self._empezar(invocar=False)
        i = Interaccion(usuario=1)
        correr(self.cog.invocar.callback(self.cog, i))
        servant = self.cog.guerras[100].masters["1"].servant
        privado, es_privado, _ = i.buzon.mensajes[0]
        publico, es_publico_privado, _ = i.buzon.mensajes[1]
        # A ti si te lo dicen, en privado.
        self.assertIn(servant.nombre, privado)
        self.assertTrue(es_privado)
        # Al canal no.
        self.assertNotIn(servant.nombre, publico)
        self.assertNotIn(servant.clase.value, publico)
        self.assertFalse(es_publico_privado)

    def test_el_estado_tapa_los_servants_que_no_conoces(self) -> None:
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        mio = guerra.masters["1"].servant
        i = Interaccion(usuario=1)
        correr(self.cog.estado_guerra.callback(self.cog, i))

        self.assertIn(mio.nombre, i.ultimo, "el tuyo si")
        # Se comprueba linea por linea, no buscando el nombre en todo el
        # texto: los nombres **no son unicos** y los repetidos se desambiguan
        # con la clase, asi que el "Martha" de un bot es subcadena del
        # "Martha (Ruler)" del jugador y la prueba fallaba 1 de cada 30 veces.
        # Lo que de verdad hay que exigir es que la linea de cada bot sea la
        # de Servant desconocido, y eso no depende de ningun nombre.
        lineas = {
            l.split(" - ")[0]: l for l in i.ultimo.splitlines() if " - " in l
        }
        for m in guerra.bots:
            self.assertIn(m.nombre, lineas, "a cada bot le toca una linea")
            self.assertIn("Servant desconocido", lineas[m.nombre])
        self.assertIn("Solo ves el Servant de quien hayas peleado", i.ultimo)
        self.assertTrue(i.buzon.mensajes[-1][1], "y va en privado")

    def _pelear_solo_contra(self, guerra, rival: str) -> None:
        """Deja una sola declaracion en pie y cierra el dia.

        Hay que borrar las de los bots: con mas de 4 en una cadena,
        `formar_batallas` sortea quien entra y te puede redirigir a otro, asi
        que declarar un ataque no basta para saber contra quien pelearas.
        """
        for m in guerra.masters.values():
            m.objetivo = None
            m.listo = True
        guerra.orden_declaraciones.clear()
        guerra.declarar_ataque("1", rival)
        correr(self.cog.empezar_batallas.callback(self.cog, Interaccion(usuario=1)))
        self._acabar_el_dia()

    def test_despues_de_pelear_el_estado_si_lo_ensena(self) -> None:
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        self._pelear_solo_contra(guerra, "bot:1")
        self.assertEqual(guerra.masters["1"].conocidos, {"bot:1"})

        i = Interaccion(usuario=1)
        correr(self.cog.estado_guerra.callback(self.cog, i))
        lineas = {
            l.split(" - ")[0]: l for l in i.ultimo.splitlines() if " - " in l
        }
        peleado = guerra.masters["bot:1"]
        self.assertIn(peleado.servant.nombre, lineas[peleado.nombre])
        # Y de los que no peleo sigue sin saber nada. Por linea y no por
        # subcadena, porque los nombres de los Servants se repiten: ver
        # `test_el_estado_tapa_los_servants_que_no_conoces`.
        no_peleados = [
            m for m in guerra.bots if m.id not in guerra.masters["1"].conocidos
        ]
        self.assertTrue(no_peleados)
        for m in no_peleados:
            self.assertIn("Servant desconocido", lineas[m.nombre])

    def test_quien_no_juega_no_ve_ningun_servant(self) -> None:
        """Un mirón del canal no se lleva informacion gratis."""
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        i = Interaccion(usuario=99)
        correr(self.cog.estado_guerra.callback(self.cog, i))
        for nombre in self._nombres_de_servants(guerra):
            self.assertNotIn(nombre, i.ultimo)

    def test_el_canal_no_ve_el_registro_de_las_batallas(self) -> None:
        """El registro nombra las habilidades, y una habilidad delata al Servant.

        "Throne of Quirinus" solo lo tiene Romulus=Quirinus, asi que publicar
        el registro en el canal dejaba sin sentido todo lo demas.
        """
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        nombres = self._nombres_de_servants(guerra)
        i = Interaccion(usuario=1)
        correr(self.cog.empezar_batallas.callback(self.cog, i))
        # Los dos mensajes publicos del dia: el de que las batallas empiezan y
        # el del cierre. Ninguno de los dos puede decir un Servant.
        publico = i.todo + "\n" + self._acabar_el_dia()

        self.assertIn("Batalla:", publico, "quien peleo si se dice")
        self.assertNotIn("```", publico, "pero el registro no")
        for nombre in nombres:
            self.assertNotIn(nombre, publico)
        # Ni los nombres de las habilidades de los que pelearon.
        for m in guerra.masters.values():
            for _, hab, _ in m.servant.todas_las_habilidades:
                if hab.nombre:
                    self.assertNotIn(hab.nombre, publico)

    def test_quien_peleo_ve_su_registro_en_privado(self) -> None:
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        self._pelear_solo_contra(guerra, "bot:1")

        master = guerra.masters["1"]
        self.assertTrue(master.ultimo_registro)
        texto = self.cog.texto_ultima_batalla(guerra, master)
        self.assertIn("Tu batalla del dia 1", texto)
        self.assertIn("```", texto)

    def test_quien_no_peleo_no_tiene_registro(self) -> None:
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        master = guerra.masters["1"]
        self.assertEqual(master.ultimo_registro, [])
        self.assertIn(
            "Todavia no has peleado",
            self.cog.texto_ultima_batalla(guerra, master),
        )

    def test_al_terminar_una_guerra_el_canal_queda_libre(self) -> None:
        """Antes el canal se quedaba bloqueado hasta reiniciar el bot."""
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        for _ in range(40):
            if guerra.terminada:
                break
            correr(
                self.cog.empezar_batallas.callback(self.cog, Interaccion(usuario=1))
            )
            self._acabar_el_dia()
        self.assertTrue(guerra.terminada)

        i = self._crear()
        self.assertIn("Guerra abierta", i.ultimo)
        self.assertIsNot(self.cog.guerras[100], guerra)
        self.assertEqual(self.cog.guerras[100].dia, 0)

    def test_no_se_crea_otra_guerra_si_la_de_antes_sigue_viva(self) -> None:
        self._crear()
        self._empezar()
        i = self._crear()
        self.assertIn("Ya hay una guerra", i.ultimo)

    def test_no_se_cierra_el_dia_si_falta_alguien(self) -> None:
        self._con_dos_personas()
        i = Interaccion(usuario=1)
        correr(self.cog.empezar_batallas.callback(self.cog, i))
        self.assertIn("Faltan por acabar su dia", i.ultimo)
        self.assertIn("Master 2", i.ultimo)
        self.assertEqual(self.cog.guerras[100].dia, 1, "el dia no se movio")

    def test_cuando_todos_acaban_su_dia_el_creador_ya_puede_cerrar(self) -> None:
        self._con_dos_personas()
        guerra = self.cog.guerras[100]
        guerra.masters["2"].listo = True
        i = Interaccion(usuario=1)
        correr(self.cog.empezar_batallas.callback(self.cog, i))
        self.assertIn("se cierra", i.todo)
        self._acabar_el_dia()
        self.assertEqual(guerra.dia, 2)

    def test_no_se_empiezan_batallas_sin_guerra(self) -> None:
        i = Interaccion(usuario=1)
        correr(self.cog.empezar_batallas.callback(self.cog, i))
        self.assertIn("No hay", i.ultimo)

    def test_la_guerra_se_puede_jugar_hasta_el_final_desde_discord(self) -> None:
        """Cerrar dias desde el comando hasta que queda uno: el ciclo entero."""
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        for _ in range(40):
            if guerra.terminada:
                break
            correr(
                self.cog.empezar_batallas.callback(self.cog, Interaccion(usuario=1))
            )
            self._acabar_el_dia()
        self.assertTrue(guerra.terminada)
        i = Interaccion(usuario=1)
        correr(self.cog.estado_guerra.callback(self.cog, i))
        self.assertIn("terminada", i.ultimo)

    def test_solo_el_creador_empieza_con_bots(self) -> None:
        self._crear()
        otro = Interaccion(usuario=2)
        correr(self.cog.unirse_a_guerra.callback(self.cog, otro))
        correr(self.cog.empezar_guerra.callback(self.cog, otro))
        self.assertIn("Solo quien abrio la guerra", otro.ultimo)

    def test_estado_dice_si_el_grial_esta_en_juego(self) -> None:
        self._crear()
        self._empezar()
        i = Interaccion(usuario=1)
        correr(self.cog.estado_guerra.callback(self.cog, i))
        self.assertIn("Dia 1", i.ultimo)
        self.assertIn("Sin Grial", i.ultimo)
        self.assertIn("Master IA 1", i.ultimo)

    def test_el_estado_dice_lo_que_queda_de_preparacion(self) -> None:
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        # Un reloj de mentira anclado al vencimiento, no a "ahora": asi la
        # prueba no depende de cuanto tardo en llegar hasta aqui.
        vence = guerra.vence_preparacion
        guerra.reloj = lambda: vence - 10 * 60
        i = Interaccion(usuario=1)
        correr(self.cog.estado_guerra.callback(self.cog, i))
        self.assertIn("Quedan 10 min de preparacion", i.ultimo)

        guerra.reloj = lambda: vence - 30
        i = Interaccion(usuario=1)
        correr(self.cog.estado_guerra.callback(self.cog, i))
        self.assertIn("menos de un minuto", i.ultimo)

    def test_el_cog_enciende_y_apaga_el_vigilante(self) -> None:
        # Las dos cosas en el mismo bucle de eventos: un `tasks.loop` solo
        # esta en marcha mientras ese bucle vive.
        estados = []

        async def encender_y_apagar() -> None:
            await self.cog.cog_load()
            estados.append(self.cog.vigilante.bucle.is_running())
            await self.cog.cog_unload()
            # Cancelar no es instantaneo: hay que dejar correr el bucle de
            # eventos para que la tarea se entere.
            await asyncio.sleep(0)
            estados.append(self.cog.vigilante.bucle.is_running())

        correr(encender_y_apagar())
        self.assertEqual(estados, [True, False])

    def test_estadisticas_trae_la_ficha_y_el_menu(self) -> None:
        from src.commands import MenuAccion

        self._crear()
        self._empezar()
        self.cog.guerras[100].masters["1"].servant.nivel = 15
        i = Interaccion(usuario=1)
        correr(self.cog.estadisticas.callback(self.cog, i))
        self.assertIn("Habilidades (3/3)", i.ultimo)
        # El enfriamiento solo se ensena de una habilidad que haga algo. Hay
        # personajes cuyas tres habilidades se traducen a NINGUNO —Gilles de
        # Rais (Caster), por ejemplo— y su ficha dice "sin efecto todavia" tres
        # veces, sin enfriamientos. Esto fallaba 1 de cada 20 veces segun a
        # quien invocara el sorteo. Ver docs/puntos-abiertos.md.
        servant = self.cog.guerras[100].masters["1"].servant
        if any(h.hace_algo for h in servant.personaje.habilidades):
            self.assertIn("enfriamiento", i.ultimo)
        else:
            self.assertIn("sin efecto todavia", i.ultimo)
        self.assertIsInstance(i.vista(), MenuAccion)
        self.assertTrue(i.buzon.mensajes[-1][1], "la ficha va en privado")

    def test_la_ficha_ensena_el_noble_fantasma_y_lo_que_hace(self) -> None:
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        master = guerra.masters["1"]
        texto = self.cog.texto_noble_fantasma(guerra, master)
        np = master.servant.noble_fantasma
        self.assertIn(np.nombre, texto)
        self.assertIn(np.rango, texto)
        # El tipo esta en los datos pero no se ensena: fuera de quien conoce
        # la serie, "Anti-Fortress" no le dice nada a nadie.
        #
        # Solo se puede comprobar cuando el tipo se distingue del nombre y del
        # rango. Atlas Academy tapa el Noble Fantasma de 9 personajes y les
        # pone "???" en los tres campos, asi que buscar el tipo en el texto
        # encontraba el nombre y la prueba fallaba 1 de cada 12 veces, segun
        # a quien invocara el sorteo. Ver docs/puntos-abiertos.md.
        self.assertTrue(np.tipo)
        if set(np.tipo) != {"?"}:
            self.assertNotIn(np.tipo, texto)
        # Lo que hace sale de nuestras reglas, con el coste del personaje.
        self.assertIn("x3 de dano a un objetivo", texto)
        self.assertIn(
            str(master.servant.rasgo.costo_noble_fantasma) + " de mana", texto
        )

    def test_la_ficha_ensena_las_tres_habilidades_aunque_falten(self) -> None:
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        master = guerra.masters["1"]
        self.assertEqual(master.servant.nivel, 1)
        texto = self.cog.texto_ficha(guerra, master)
        self.assertIn("Habilidades (0/3)", texto)
        # Las tres aparecen, con el nivel al que se abren.
        for numero, nivel in ((1, 5), (2, 10), (3, 15)):
            self.assertIn(f"  {numero}. 🔒", texto)
            self.assertIn(f"al nivel {nivel}", texto)

        master.servant.nivel = 10
        texto = self.cog.texto_ficha(guerra, master)
        self.assertIn("Habilidades (2/3)", texto)
        self.assertIn("  3. 🔒", texto)
        self.assertNotIn("  1. 🔒", texto)
        self.assertIn("al nivel 15", texto)

    def test_la_ficha_en_ingles_va_en_ingles(self) -> None:
        self._crear(idioma="en")
        self._empezar()
        servant = self.cog.guerras[100].masters["1"].servant
        servant.nivel = 15
        i = Interaccion(usuario=1)
        correr(self.cog.estadisticas.callback(self.cog, i))
        self.assertIn("Skills (3/3)", i.ultimo)
        # El enfriamiento solo sale si alguna habilidad hace algo, y **dos
        # personajes del plantel** (Gilles de Rais (Caster) y Eric Bloodaxe)
        # tienen las tres sin efecto. Ver docs/puntos-abiertos.md.
        if any(h.hace_algo for _, h, _ in servant.todas_las_habilidades):
            self.assertIn("cooldown", i.ultimo)
        self.assertIn("Noble Phantasm", i.ultimo)
        self.assertIn("can be repeated", i.ultimo)

    def test_entrenar_pelea_y_da_xp(self) -> None:
        """La XP que se gana tiene que cuadrar con los combates ganados.

        Antes esto exigia pasar del nivel 1, y era dar por seguro un
        resultado: desde que los NPC se endurecieron, el 1.o se gana el 97% y
        no el 100%, asi que la prueba fallaba el 4% de las veces. Lo que hay
        que exigir no es ganar, es que el premio cuadre con lo que paso.
        """
        from src.game.npc import XP_POR_VICTORIA
        from src.game.servant import xp_acumulada

        self._crear()
        self._empezar()
        master = self.cog.guerras[100].masters["1"]
        ganados = []
        for _ in range(4):
            i = Interaccion(usuario=1)
            correr(self.cog.entrenar.callback(self.cog, i))
            self.assertRegex(i.ultimo, r"Victoria|Derrota")
            self.assertIn("Sombra", i.ultimo)
            ganados.append("Victoria" in i.ultimo)
        self.assertEqual(master.intentos_npc, 4)
        self.assertEqual(master.derrotas_npc, ganados.count(False))
        esperada = sum(x for x, g in zip(XP_POR_VICTORIA, ganados) if g)
        self.assertEqual(
            xp_acumulada(master.servant.nivel) + master.servant.xp, esperada
        )
        # Y ganar los cuatro tiene que dar para subir de nivel, que es para lo
        # que se entrena.
        if all(ganados):
            self.assertGreater(master.servant.nivel, 1)
        i = Interaccion(usuario=1)
        correr(self.cog.entrenar.callback(self.cog, i))
        self.assertIn("Ya gastaste tus 4 combates", i.ultimo)

    def test_los_comandos_avisan_cuando_no_hay_guerra(self) -> None:
        for comando in (
            self.cog.unirse_a_guerra,
            self.cog.empezar_guerra,
            self.cog.estado_guerra,
        ):
            i = Interaccion(usuario=1, canal=999)
            correr(comando.callback(self.cog, i))
            self.assertIn("No hay ninguna guerra", i.ultimo)

    def test_sin_servant_no_hay_estadisticas(self) -> None:
        i = Interaccion(usuario=1, canal=999)
        correr(self.cog.estadisticas.callback(self.cog, i))
        self.assertIn("No tienes un Servant", i.ultimo)


@unittest.skipUnless(HAY_DISCORD, "discord.py no esta instalado")
class PruebaPersistenciaDelCog(unittest.TestCase):
    """El bot se apaga a mitad de una guerra y al volver sigue donde iba."""

    def setUp(self) -> None:
        from src import db, repositorio
        from src.commands import ComandosGuerra

        self.con = db.conectar(":memory:")
        repositorio.migrar(self.con)
        self.Cog = ComandosGuerra
        self.cog = ComandosGuerra(bot=None, conexion=self.con)

    def tearDown(self) -> None:
        self.con.close()

    def _reiniciar(self):
        """Apaga el bot y lo vuelve a encender con la misma base de datos."""
        otro = self.Cog(bot=None, conexion=self.con)
        correr(otro.cog_load())
        correr(otro.cog_unload())
        return otro

    def _jugar_un_poco(self) -> None:
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        correr(self.cog.invocar.callback(self.cog, Interaccion(usuario=1)))
        correr(self.cog.entrenar.callback(self.cog, Interaccion(usuario=1)))

    def test_la_guerra_sobrevive_al_reinicio(self) -> None:
        self._jugar_un_poco()
        antes = self.cog.guerras[100]
        servant = antes.masters["1"].servant

        despues = self._reiniciar()
        self.assertIn(100, despues.guerras)
        vuelta = despues.guerras[100]
        self.assertEqual(vuelta.dia, antes.dia)
        self.assertEqual(vuelta.creador_id, "1")
        self.assertEqual(len(vuelta.bots), 6)
        suyo = vuelta.masters["1"].servant
        self.assertEqual(suyo.nombre, servant.nombre)
        self.assertEqual(suyo.nivel, servant.nivel)
        self.assertEqual(suyo.xp, servant.xp)
        self.assertEqual(
            vuelta.masters["1"].intentos_npc, antes.masters["1"].intentos_npc
        )

    def test_despues_del_reinicio_se_sigue_jugando(self) -> None:
        self._jugar_un_poco()
        despues = self._reiniciar()
        i = Interaccion(usuario=1)
        correr(despues.empezar_batallas.callback(despues, i))
        self.assertIn("se cierra", i.todo)
        # Y las batallas que abrio se pueden acabar, que es lo que hace pasar
        # el dia desde que se juegan a mano. Si a la persona le toco descansar
        # no queda ninguna y el dia ya paso solo.
        guerra = despues.guerras[100]
        estado = despues.combates.get(guerra.id)
        if estado is not None:
            for combate in estado.pendientes:
                while not combate.terminado:
                    combate.avanzar_con_ia()
            despues.cierre_de_los_combates(guerra)
        self.assertEqual(guerra.dia, 2)

    def test_sin_guerras_guardadas_arranca_vacio(self) -> None:
        despues = self._reiniciar()
        self.assertEqual(despues.guerras, {})

    def test_sin_conexion_el_cog_funciona_igual(self) -> None:
        """Las pruebas que no van de esto crean el Cog sin base de datos."""
        suelto = self.Cog(bot=None)
        correr(
            suelto.crear_guerra.callback(
                suelto, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        self.assertIn(100, suelto.guerras)


@unittest.skipUnless(HAY_DISCORD, "discord.py no esta instalado")
class PruebaMenu(unittest.TestCase):
    """El menu privado: los botones hacen lo mismo que sus comandos."""

    def setUp(self) -> None:
        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        self.guerra = self.cog.guerras[100]
        self.master = self.guerra.masters["1"]
        # Empezar ya no invoca: lo pide cada Master. Las pruebas del menu que
        # van de la invocacion la hacen ellas; el resto parte de aqui.
        self.guerra.invocar_para(self.master.id)

    def _menu(self):
        from src.commands import MenuAccion

        return MenuAccion(self.cog, self.guerra, self.master)

    def _cerrar_con_batalla_de_la_persona(self):
        """Pulsa el boton rojo dejando seguro una batalla con persona dentro.

        Declarar un ataque **no** basta: si la cadena del rival ya llega a 4 y
        no queda nadie libre, al que no cupo le toca descansar (es la regla,
        ver `Guerra._redirigir`), y pasa el 8% de las veces. Asi que se monta
        la guerra con una semilla y otra hasta que entre.

        Devuelve el menu y la interaccion, que es lo que miran las pruebas.
        """
        import random

        for semilla in range(40):
            self.setUp()
            self.cog.rng = random.Random(semilla)
            self.guerra.declarar_ataque("1", "bot:1")
            menu = self._menu()
            i = Interaccion(usuario=1)
            correr(menu.boton_batallas.callback(i))
            if self.cog.combates.get(self.guerra.id) is not None:
                return menu, i
        self.skipTest("ninguna semilla dejo pelear a la persona")

    def _deshacer_invocacion(self) -> None:
        """Devuelve el Servant al sorteo, para dejar al Master sin invocar.

        El `setUp` invoca porque casi todo el menu lo necesita; esto deshace
        ese paso sin tener que montar otra guerra.
        """
        self.guerra.sin_repartir.append(self.master.servant)
        self.master.servant = None

    def test_el_boton_del_canal_abre_el_menu_en_privado(self) -> None:
        from src.commands import AbrirMenu, MenuAccion

        vista = AbrirMenu(self.cog, self.guerra)
        i = Interaccion(usuario=1)
        correr(vista.boton.callback(i))
        texto, privado, menu = i.buzon.mensajes[-1]
        self.assertIn("Dia 1", texto)
        self.assertTrue(privado)
        self.assertIsInstance(menu, MenuAccion)

    def test_quien_no_juega_no_abre_menu(self) -> None:
        from src.commands import AbrirMenu

        vista = AbrirMenu(self.cog, self.guerra)
        i = Interaccion(usuario=42)
        correr(vista.boton.callback(i))
        self.assertIn("No estas en esta guerra", i.ultimo)
        self.assertIsNone(i.vista())

    def test_un_menu_es_de_quien_lo_abrio(self) -> None:
        menu = self._menu()
        intruso = Interaccion(usuario=42)
        self.assertFalse(correr_valor(menu.interaction_check(intruso)))
        self.assertIn("No estas en esta guerra", intruso.ultimo)
        self.assertTrue(correr_valor(menu.interaction_check(Interaccion(usuario=1))))

    def test_las_etiquetas_de_los_botones(self) -> None:
        menu = self._menu()
        self.assertEqual(menu.boton_estadisticas.label, "Mis estadisticas")
        self.assertEqual(menu.boton_entrenar.label, "Entrenar (4)")
        self.assertEqual(menu.boton_estado.label, "Estado de la guerra")
        self.assertEqual(menu.boton_inventario.label, "Inventario (0)")
        self.assertTrue(
            menu.boton_inventario.disabled, "vacio no hay nada que ensenar"
        )

    def test_el_boton_de_estadisticas_da_la_ficha(self) -> None:
        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_estadisticas.callback(i))
        self.assertIn("Noble Fantasma", i.ultimo)
        self.assertTrue(i.buzon.mensajes[-1][1])

    def test_el_boton_de_entrenar_pelea_y_descuenta(self) -> None:
        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_entrenar.callback(i))
        self.assertRegex(i.ultimo, r"Victoria|Derrota")
        self.assertEqual(self.master.intentos_npc, 1)
        # El boton se actualiza con los que quedan.
        self.assertEqual(menu.boton_entrenar.label, "Entrenar (3)")

    def test_el_boton_de_entrenar_se_apaga_al_gastarlos(self) -> None:
        menu = self._menu()
        for _ in range(4):
            correr(menu.boton_entrenar.callback(Interaccion(usuario=1)))
        self.assertTrue(menu.boton_entrenar.disabled)
        self.assertEqual(menu.boton_entrenar.label, "Entrenar (0)")

    def test_el_boton_de_invocar_invoca_y_se_apaga(self) -> None:
        self._deshacer_invocacion()
        menu = self._menu()
        self.assertFalse(menu.boton_invocar.disabled)
        self.assertTrue(menu.boton_entrenar.disabled, "sin Servant no se entrena")
        self.assertTrue(menu.boton_estadisticas.disabled)

        i = Interaccion(usuario=1)
        correr(menu.boton_invocar.callback(i))
        self.assertIsNotNone(self.master.servant)
        self.assertTrue(menu.boton_invocar.disabled)
        self.assertFalse(menu.boton_entrenar.disabled)
        self.assertIn(self.master.servant.nombre, i.todo)

    def test_el_boton_de_invocar_nace_apagado_si_ya_invoco(self) -> None:
        menu = self._menu()
        self.assertTrue(menu.boton_invocar.disabled)
        self.assertFalse(menu.boton_entrenar.disabled)

    def test_el_menu_se_abre_sin_haber_invocado(self) -> None:
        from src.commands import AbrirMenu, MenuAccion

        self._deshacer_invocacion()
        vista = AbrirMenu(self.cog, self.guerra)
        i = Interaccion(usuario=1)
        correr(vista.boton.callback(i))
        texto, _, menu = i.buzon.mensajes[-1]
        self.assertIn("no has invocado", texto)
        self.assertIsInstance(menu, MenuAccion)

    def test_el_boton_de_la_ultima_batalla_nace_apagado(self) -> None:
        menu = self._menu()
        self.assertTrue(menu.boton_ultima_batalla.disabled)
        i = Interaccion(usuario=1)
        correr(menu.boton_ultima_batalla.callback(i))
        self.assertIn("Todavia no has peleado", i.ultimo)
        self.assertTrue(i.buzon.mensajes[-1][1], "en privado")

    def test_el_boton_de_la_ultima_batalla_se_enciende_al_pelear(self) -> None:
        self.master.ultimo_registro = ["paso algo", "y luego otra cosa"]
        self.master.ultimo_registro_dia = 2
        menu = self._menu()
        self.assertFalse(menu.boton_ultima_batalla.disabled)
        i = Interaccion(usuario=1)
        correr(menu.boton_ultima_batalla.callback(i))
        self.assertIn("Tu batalla del dia 2", i.ultimo)
        self.assertIn("y luego otra cosa", i.ultimo)

    def test_el_boton_de_listo_lo_marca_y_lo_dice_en_el_canal(self) -> None:
        menu = self._menu()
        i = Interaccion(usuario=1)
        dia_de_antes = self.guerra.dia
        correr(menu.boton_listo.callback(i))
        # Desde que decirse listo cierra el dia, `listo` puede venir ya
        # borrado: si el dia se cerro entero (al humano le toco descansar),
        # `nuevo_dia` lo pone a False, que es lo que toca. Lo que la prueba
        # exige es que se le hiciera caso de una de las dos formas.
        self.assertTrue(
            self.master.listo or self.guerra.dia > dia_de_antes,
            "o quedo marcado, o el dia se cerro con eso",
        )
        self.assertTrue(menu.boton_listo.disabled)
        self.assertEqual(menu.boton_listo.label, "Listo ✓")
        self.assertTrue(menu.boton_entrenar.disabled, "ya no entrena")
        # El canal se entera, y con un solo humano ya no falta nadie.
        self.assertIn("Ya estan todos", i.todo)

    def test_despues_de_listo_no_se_entrena(self) -> None:
        self.master.listo = True
        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_entrenar.callback(i))
        self.assertIn("Ya dijiste que acabaste", i.todo)
        self.assertEqual(self.master.intentos_npc, 0)

    def test_el_boton_de_batallas_nace_apagado_si_falta_alguien(self) -> None:
        # Un cupo que llevaba la IA pasa a ser una persona que no ha acabado.
        otro = self.guerra.masters["bot:1"]
        otro.es_bot = False
        otro.listo = False
        self.assertTrue(self._menu().boton_batallas.disabled)
        otro.listo = True
        # El creador no se espera a si mismo: pulsarlo ya es decir que acabo.
        self.assertFalse(self.master.listo)
        self.assertFalse(self._menu().boton_batallas.disabled)

    def test_el_boton_de_batallas_cierra_la_preparacion(self) -> None:
        menu, i = self._cerrar_con_batalla_de_la_persona()
        self.assertEqual(self.guerra.fase, Fase.BATALLA)
        self.assertIn("se cierra", i.todo)
        self.assertNotIn(menu.boton_batallas, menu.children, "el boton se retira")

    def test_los_demas_no_ven_el_boton_de_batallas(self) -> None:
        from src.commands import MenuAccion

        otro = self.guerra.masters["bot:1"]
        menu = MenuAccion(self.cog, self.guerra, otro)
        self.assertNotIn(menu.boton_batallas, menu.children)
        # Y el del creador si lo tiene.
        suyo = self._menu()
        self.assertIn(suyo.boton_batallas, suyo.children)

    def test_al_cerrar_la_preparacion_el_canal_recibe_el_boton_del_combate(
        self,
    ) -> None:
        """Lo que trae el dia ahora son batallas que pelear, no el menu."""
        from src.commands import AbrirCombate

        _, i = self._cerrar_con_batalla_de_la_persona()
        vistas = [m[2] for m in i.buzon.mensajes]
        self.assertTrue(
            any(isinstance(v, AbrirCombate) for v in vistas),
            "el canal se queda sin boton para pelear",
        )
        self.assertIn("empiezan las batallas", i.todo)

    def test_al_acabar_las_batallas_el_canal_recibe_el_menu_otra_vez(self) -> None:
        """El dia nuevo trae cosas que hacer, y el menu de ayer se fue con ayer."""
        from src.commands import AbrirMenu

        self._cerrar_con_batalla_de_la_persona()
        estado = self.cog.combates[self.guerra.id]
        for combate in estado.pendientes:
            while not combate.terminado:
                combate.avanzar_con_ia()
        i = Interaccion(usuario=1)
        correr(self.cog.cerrar_si_acabaron_los_combates(i, self.guerra))
        self.assertEqual(self.guerra.dia, 2)
        vistas = [m[2] for m in i.buzon.mensajes]
        self.assertTrue(
            any(isinstance(v, AbrirMenu) for v in vistas),
            "el canal se queda sin boton para el dia 2",
        )
        self.assertIn("abrir tu menu", i.todo)

    def test_al_terminar_la_guerra_no_se_manda_otro_menu(self) -> None:
        for otro in self.guerra.activos:
            if otro.id != self.master.id:
                otro.derrotas = 2  # eliminados: la guerra acaba hoy
        from src.commands import AbrirMenu

        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_batallas.callback(i))
        self.assertTrue(self.guerra.terminada)
        self.assertIsNone(self.cog.combates.get(self.guerra.id))
        vistas = [m[2] for m in i.buzon.mensajes]
        self.assertFalse(any(isinstance(v, AbrirMenu) for v in vistas))

    # --- planear el ataque ---

    def test_el_boton_de_planear_abre_el_desplegable_con_los_rivales(self) -> None:
        from src.commands import VistaPlanear

        menu = self._menu()
        self.assertFalse(menu.boton_planear.disabled)
        i = Interaccion(usuario=1)
        correr(menu.boton_planear.callback(i))
        vista = i.vista()
        self.assertIsInstance(vista, VistaPlanear)
        self.assertTrue(i.buzon.mensajes[-1][1], "en privado")
        # Los seis rivales, y ninguno es el mismo.
        valores = [o.value for o in vista.selector.options]
        self.assertEqual(len(valores), 6)
        self.assertNotIn(self.master.id, valores)

    def test_el_desplegable_tapa_el_servant_de_quien_no_conoces(self) -> None:
        opciones = self.cog.opciones_de_ataque(self.guerra, self.master)
        self.assertTrue(
            all("desconocido" in d for _, _, d, _ in opciones), opciones
        )
        # Y en cuanto conoces a uno, ese si dice su Servant.
        # Los bots ya invocaron al abrirse el dia, asi que basta con conocerlo.
        otro = self.guerra.masters["bot:1"]
        self.master.conocidos.add(otro.id)
        por_id = {i_: d for i_, _, d, _ in self.cog.opciones_de_ataque(
            self.guerra, self.master
        )}
        self.assertIn(otro.servant.nombre, por_id[otro.id])
        self.assertIn("desconocido", por_id["bot:2"])

    def test_elegir_en_el_desplegable_declara_el_ataque(self) -> None:
        from src.commands import VistaPlanear

        vista = VistaPlanear(self.cog, self.guerra, self.master)
        i = Interaccion(usuario=1)
        correr(vista.elegir(i, "bot:3"))
        self.assertEqual(self.master.objetivo, "bot:3")
        self.assertIn(self.guerra.masters["bot:3"].nombre, i.ultimo)
        # Y no sale al canal: a quien atacas no lo sabe nadie mas.
        self.assertTrue(all(m[1] for m in i.buzon.mensajes), i.buzon.mensajes)

    def test_el_boton_recuerda_a_quien_ibas_a_atacar(self) -> None:
        self.guerra.declarar_ataque(self.master.id, "bot:4")
        menu = self._menu()
        self.assertIn(self.guerra.masters["bot:4"].nombre, menu.boton_planear.label)

    def test_sin_invocar_no_se_planea(self) -> None:
        self._deshacer_invocacion()
        menu = self._menu()
        self.assertTrue(menu.boton_planear.disabled)
        i = Interaccion(usuario=1)
        correr(menu.boton_planear.callback(i))
        self.assertIn("invoca primero", i.ultimo.lower())
        self.assertIsNone(self.master.objetivo)

    def test_despues_de_listo_no_se_cambia_de_objetivo(self) -> None:
        """Si se pudiera, decir que acabaste no significaria nada."""
        self.guerra.declarar_ataque(self.master.id, "bot:4")
        self.master.listo = True
        menu = self._menu()
        self.assertTrue(menu.boton_planear.disabled)
        self.assertIn(
            "acabaste", self.cog.texto_planear(self.guerra, self.master, "bot:5")
        )
        self.assertEqual(self.master.objetivo, "bot:4", "el de antes sigue valiendo")

    def test_un_desplegable_es_de_quien_lo_abrio(self) -> None:
        from src.commands import VistaPlanear

        vista = VistaPlanear(self.cog, self.guerra, self.master)
        intruso = Interaccion(usuario=42)
        self.assertFalse(correr_valor(vista.interaction_check(intruso)))

    def test_planear_se_guarda(self) -> None:
        """Una accion que cambia algo y no se guardara es un error silencioso."""
        guardadas = []
        self.cog.guardar = guardadas.append
        self.cog.texto_planear(self.guerra, self.master, "bot:2")
        self.assertEqual(guardadas, [self.guerra])

    def test_el_boton_de_estado_cuenta_la_guerra(self) -> None:
        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_estado.callback(i))
        self.assertIn("Dia 1", i.ultimo)
        self.assertIn("Sin Grial", i.ultimo)

    def test_el_menu_en_ingles(self) -> None:
        from src.commands import ComandosGuerra, MenuAccion

        cog = ComandosGuerra(bot=None)
        correr(
            cog.crear_guerra.callback(
                cog,
                Interaccion(usuario=1, canal=200),
                Eleccion("1 hour", "1h"),
                Eleccion("en", "en"),
            )
        )
        correr(cog.empezar_guerra.callback(cog, Interaccion(usuario=1, canal=200)))
        guerra = cog.guerras[200]
        menu = MenuAccion(cog, guerra, guerra.masters["1"])
        self.assertEqual(menu.boton_estadisticas.label, "My stats")
        self.assertEqual(menu.boton_entrenar.label, "Train (4)")
        self.assertEqual(menu.boton_inventario.label, "Inventory (0)")
        self.assertEqual(menu.boton_planear.label, "Plan attack")


def correr_valor(corrutina):
    return asyncio.run(corrutina)


@unittest.skipUnless(HAY_DISCORD, "discord.py no esta instalado")
class PruebaRendirse(unittest.TestCase):
    """El boton de rendirse: dos clics, y te saca de la guerra."""

    def setUp(self) -> None:
        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        self.guerra = self.cog.guerras[100]
        self.master = self.guerra.masters["1"]
        self.guerra.invocar_para(self.master.id)

    def _menu(self):
        from src.commands import MenuAccion

        return MenuAccion(self.cog, self.guerra, self.master)

    def test_un_clic_solo_pregunta(self) -> None:
        menu = self._menu()
        correr(menu.boton_rendirse.callback(Interaccion(usuario=1)))
        self.assertTrue(menu.confirmando_rendirse)
        self.assertFalse(self.master.retirado, "todavia no")
        self.assertIn("?", menu.boton_rendirse.label)

    def test_el_segundo_clic_lo_hace(self) -> None:
        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_rendirse.callback(i))
        correr(menu.boton_rendirse.callback(i))
        self.assertTrue(self.master.retirado)
        self.assertNotIn(self.master, self.guerra.activos)
        # Lo privado y el aviso al canal, en ese orden.
        self.assertTrue(any(not privado for _, privado, _ in i.buzon.mensajes))

    def test_lo_que_reescribe_el_menu_deshace_la_pregunta(self) -> None:
        """Entrenar redibuja el menu, asi que la pregunta se va con el.

        Lo que solo manda un mensaje aparte (el estado) no la deshace, y eso
        es a proposito: el boton de la pantalla sigue diciendo "pulsa otra
        vez", asi que lo que se ve y lo que pasa coinciden.
        """
        menu = self._menu()
        correr(menu.boton_rendirse.callback(Interaccion(usuario=1)))
        correr(menu.boton_entrenar.callback(Interaccion(usuario=1)))
        self.assertFalse(menu.confirmando_rendirse)
        self.assertFalse(self.master.retirado)
        self.assertNotIn("?", menu.boton_rendirse.label)

    def test_al_canal_no_va_ningun_Servant(self) -> None:
        nombre = self.master.servant.nombre
        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_rendirse.callback(i))
        correr(menu.boton_rendirse.callback(i))
        publico = [
            texto for texto, privado, _ in i.buzon.mensajes if not privado
        ]
        self.assertTrue(publico)
        for texto in publico:
            self.assertNotIn(nombre, texto)

    def _guerra_de(self, humanos: int):
        """Monta de cero una guerra con `humanos` personas y el resto bots.

        Hay que inscribirlas **antes** de empezar, asi que esto no reusa la
        guerra del `setUp`: la cambia por otra.
        """
        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        guerra = self.cog.guerras[100]
        for i in range(2, humanos + 1):
            guerra.inscribir(str(i), f"Master {i}")
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        guerra.invocar_a_los_que_falten()
        self.guerra = guerra
        self.master = guerra.masters["1"]
        return guerra

    def _se_van_todos_menos_el_primero(self) -> None:
        for m in list(self.guerra.masters.values()):
            if m.id == "1":
                continue
            self.cog.rendir_al_master(self.guerra, m)

    def test_el_grial_se_paga_cuando_se_van_seis(self) -> None:
        """El segundo sitio que anuncia el Grial tiene que pagarlo.

        El otro es `narrar_cierre`. Si este lo anunciara sin pagar, el
        ganador leeria que gano un grial que no tiene.
        """
        from src.game.war import MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA

        self._guerra_de(MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA)
        self._se_van_todos_menos_el_primero()
        self.assertEqual(self.guerra.gana_el_grial().id, "1")
        self.assertEqual(self.cog.cuenta_de("1").guerras_ganadas, 1)
        self.assertGreater(self.cog.cuenta_de("1").griales, 0)

    def test_con_cuatro_no_se_paga_nada(self) -> None:
        from src.game.war import MINIMO_HUMANOS_PARA_GRIAL

        self._guerra_de(MINIMO_HUMANOS_PARA_GRIAL)
        self._se_van_todos_menos_el_primero()
        self.assertTrue(self.guerra.terminada)
        self.assertEqual(self.cog.cuenta_de("1").griales, 0)

    def test_el_grial_no_se_paga_dos_veces(self) -> None:
        """Rendirse otra vez despues del final no vuelve a cobrar."""
        from src.game.war import MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA

        self._guerra_de(MINIMO_HUMANOS_PARA_GRIAL_POR_RETIRADA)
        self._se_van_todos_menos_el_primero()
        griales = self.cog.cuenta_de("1").griales
        self.cog.rendir_al_master(self.guerra, self.guerra.masters["2"])
        self.assertEqual(self.cog.cuenta_de("1").griales, griales)

    def test_el_que_se_rindio_no_puede_volver_a_rendirse(self) -> None:
        self.guerra.rendirse(self.master.id)
        menu = self._menu()
        self.assertTrue(menu.boton_rendirse.disabled)


class PruebaMiCuenta(unittest.TestCase):
    """El unico comando que funciona sin guerra en el canal."""

    def setUp(self) -> None:
        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)

    def test_contesta_sin_ninguna_guerra(self) -> None:
        i = Interaccion(usuario=1)
        correr(self.cog.mi_cuenta.callback(self.cog, i))
        texto, privado, _ = i.buzon.mensajes[0]
        self.assertTrue(privado, "la cuenta es privada")
        self.assertIn("0", texto)

    def test_ensena_los_griales_que_tiene(self) -> None:
        from src.game import tienda

        self.cog.apuntar_cuenta(
            tienda.Cuenta(usuario_id="1", griales=5, guerras_ganadas=3)
        )
        i = Interaccion(usuario=1)
        correr(self.cog.mi_cuenta.callback(self.cog, i))
        texto = i.buzon.mensajes[0][0]
        self.assertIn("5", texto)
        self.assertIn("3", texto)


class PruebaMenuDeCombate(unittest.TestCase):
    """El menu con el que se pelea: lo que se puede elegir y lo que se ve.

    La guerra es de una persona y seis bots, asi que la persona es la unica a
    la que se espera: su decision cierra el turno y la prueba no depende de
    que otra conteste.
    """

    def setUp(self) -> None:
        # Declarar un ataque **no** garantiza pelear: si la cadena del rival
        # ya llega a 4 y no queda nadie libre, al que no cupo le toca
        # descansar (es la regla, ver `Guerra._redirigir`), y eso pasa el 8%
        # de las veces con seis bots. Asi que se monta con una semilla y otra
        # hasta que la persona entre en una batalla, en vez de dar por hecho
        # que entra.
        self._montar_hasta(2)

    def _montar_hasta(self, en_pie: int) -> None:
        """Monta una guerra hasta que la persona pelee contra `en_pie`-1 o mas."""
        for semilla in range(60):
            self._montar(semilla)
            if self.combate is not None and len(self.combate.batalla.vivos) >= en_pie:
                return
        self.skipTest(f"ninguna semilla dejo una batalla de {en_pie} con la persona")

    def _montar(self, semilla: int) -> None:
        import random

        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        self.cog.rng = random.Random(semilla)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        self.guerra = self.cog.guerras[100]
        self.master = self.guerra.masters["1"]
        self.guerra.invocar_para(self.master.id)
        self.guerra.declarar_ataque("1", "bot:1")
        correr(self.cog.empezar_batallas.callback(self.cog, Interaccion(usuario=1)))
        self.combate = self.cog.combate_de(self.guerra, self.master)

    def _menu(self):
        from src.commands import MenuCombate

        return MenuCombate(self.cog, self.guerra, self.master)

    def _rival(self) -> str:
        return self.combate.batalla.rivales_de("1")[0].id

    # --- entrar ---

    def test_el_boton_del_canal_abre_tu_combate(self) -> None:
        from src.commands import AbrirCombate, MenuCombate

        vista = AbrirCombate(self.cog, self.guerra)
        i = Interaccion(usuario=1)
        correr(vista.boton.callback(i))
        self.assertIsInstance(i.vista(), MenuCombate)
        self.assertTrue(i.buzon.mensajes[-1][1], "en privado")

    def test_quien_no_pelea_no_abre_nada(self) -> None:
        from src.commands import AbrirCombate

        # Un bot de los que descansan: esta en la guerra pero no en batalla.
        sin_batalla = [
            m
            for m in self.guerra.masters.values()
            if self.cog.combate_de(self.guerra, m) is None
        ]
        self.assertTrue(sin_batalla, "alguien descansa o ya acabo su batalla")
        vista = AbrirCombate(self.cog, self.guerra)
        i = Interaccion(usuario=int(999))
        correr(vista.boton.callback(i))
        self.assertIn("No estas", i.ultimo)

    # --- lo que se ve ---

    def test_dentro_de_la_batalla_si_se_ven_los_servants(self) -> None:
        """Estar delante de alguien es justo lo que destapa su Servant."""
        texto = self.cog.texto_combate(self.guerra, self.master)
        self.assertIn(self.master.servant.nombre, texto)
        for c in self.combate.batalla.rivales_de("1"):
            self.assertIn(c.servant.nombre, texto)
        self.assertIn("de mana", texto)

    def test_el_menu_dice_a_quien_se_espera(self) -> None:
        texto = self.cog.texto_combate(self.guerra, self.master)
        self.assertIn("Te toca elegir", texto)
        self.cog.decidir_en_combate(
            self.guerra, self.master, Decision(accion=Accion.DEFENDER)
        )
        # Sola en la batalla: su decision cierra el turno, asi que lo que ve
        # despues es el turno nuevo, no una espera.
        self.assertGreaterEqual(self.combate.batalla.turno, 1)

    def test_sin_combate_el_menu_lo_dice(self) -> None:
        del self.cog.combates[self.guerra.id]
        self.assertIn(
            "No estas peleando",
            self.cog.texto_combate(self.guerra, self.master),
        )

    # --- elegir ---

    def test_atacar_resuelve_el_turno_y_cuenta_lo_que_paso(self) -> None:
        texto = self.cog.decidir_en_combate(
            self.guerra,
            self.master,
            Decision(accion=Accion.ATACAR, objetivo=self._rival()),
        )
        self.assertIn("Atacaras a", texto)
        self.assertIn("Turno resuelto", texto)
        self.assertIn("```", texto, "el registro va en privado, pero va")

    def test_el_desplegable_de_objetivos_trae_los_rivales_en_pie(self) -> None:
        opciones = self.cog.opciones_de_objetivo(self.guerra, self.master)
        vivos = self.combate.batalla.rivales_de("1")
        self.assertEqual(len(opciones), len(vivos))
        self.assertNotIn("1", [v for v, _, _ in opciones])

    def test_el_boton_de_atacar_abre_el_desplegable_y_elegir_decide(self) -> None:
        from src.commands import VistaObjetivo

        # Con tres, porque en un duelo el desplegable no sale: no hay nada que
        # elegir (`test_en_un_duelo_atacar_no_pregunta_a_quien`).
        self._montar_hasta(3)
        menu = self._menu()
        self.assertFalse(menu.boton_atacar.disabled)
        i = Interaccion(usuario=1)
        correr(menu.boton_atacar.callback(i))
        vista = i.vista()
        self.assertIsInstance(vista, VistaObjetivo)
        rival = self._rival()
        j = Interaccion(usuario=1)
        correr(vista.elegir(j, rival))
        self.assertIn(self.guerra.masters[rival].nombre, j.todo)
        self.assertGreaterEqual(self.combate.batalla.turno, 1)

    def test_en_un_duelo_atacar_no_pregunta_a_quien(self) -> None:
        """Con un solo rival en pie, elegirlo no es decidir, es un clic de mas."""
        from src.commands import VistaObjetivo

        # Se tumba a todos menos a uno, que es como acaba cualquier batalla de
        # mas de dos: antes o despues queda un duelo.
        rivales = self.combate.batalla.rivales_de("1")
        for c in rivales[1:]:
            c.vida = 0
        self.assertEqual(len(self.cog.opciones_de_objetivo(self.guerra, self.master)), 1)

        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_atacar.callback(i))
        self.assertFalse(
            any(isinstance(m[2], VistaObjetivo) for m in i.buzon.mensajes),
            "no hay nada que elegir, asi que no sale desplegable",
        )
        self.assertIn(rivales[0].nombre, i.todo)
        self.assertGreaterEqual(self.combate.batalla.turno, 1, "el turno se jugo")

    def test_con_dos_rivales_en_pie_si_pregunta(self) -> None:
        from src.commands import VistaObjetivo

        self._montar_hasta(3)
        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_atacar.callback(i))
        self.assertIsInstance(i.vista(), VistaObjetivo)
        self.assertEqual(self.combate.batalla.turno, 0, "todavia no decidio nada")

    def test_una_habilidad_con_un_solo_destino_no_pregunta(self) -> None:
        self.master.servant.nivel = 15
        listas = self.combate.batalla.habilidades_disponibles("1")
        # Una que solo pueda ir a un sitio: a uno mismo, o al unico rival.
        for c in self.combate.batalla.rivales_de("1")[1:]:
            c.vida = 0
        candidatas = [
            n
            for n in listas
            if len(self.cog.opciones_de_objetivo_de_habilidad(
                self.guerra, self.master, n
            )) == 1
        ]
        if not candidatas:
            self.skipTest("este Servant no tiene ninguna habilidad de un solo destino")
        from src.commands import VistaObjetivo

        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_habilidad.callback(i))
        vista = i.vista()
        self.assertIsInstance(vista, VistaObjetivo, "cual se usa si se pregunta")
        j = Interaccion(usuario=1)
        correr(vista.elegir(j, str(candidatas[0])))
        self.assertIn("Usaras", j.todo)
        self.assertGreaterEqual(self.combate.batalla.turno, 1)

    def test_no_se_decide_dos_veces_en_el_mismo_turno(self) -> None:
        """Con dos personas el turno no se cierra con una, asi que se nota."""
        otra = self.guerra.masters[self._rival()]
        otra.es_bot = False
        self.combate.humanos.add(otra.id)
        self.cog.decidir_en_combate(
            self.guerra, self.master, Decision(accion=Accion.DEFENDER)
        )
        self.assertEqual(self.combate.batalla.turno, 0, "falta la otra persona")
        texto = self.cog.decidir_en_combate(
            self.guerra, self.master, Decision(accion=Accion.DEFENDER)
        )
        self.assertIn("Ya elegiste", texto)
        self.assertTrue(self._menu().boton_atacar.disabled)
        self.assertIn("Esperando a", self.cog.texto_combate(self.guerra, self.master))

    def test_el_noble_fantasma_sin_mana_no_se_libera(self) -> None:
        yo = self.combate.batalla.combatientes["1"]
        yo.mana = 0
        self.assertTrue(self._menu().boton_np.disabled)
        texto = self.cog.decidir_en_combate(
            self.guerra,
            self.master,
            Decision(accion=Accion.NOBLE_FANTASMA, objetivo=self._rival()),
        )
        self.assertIn("Te faltan", texto)
        self.assertEqual(self.combate.batalla.turno, 0, "no gasto el turno")

    def test_con_el_mana_lleno_el_noble_fantasma_se_enciende(self) -> None:
        yo = self.combate.batalla.combatientes["1"]
        yo.mana = yo.costo_np
        from src.game.battle import Accion as A

        self.assertIn(A.NOBLE_FANTASMA, self.cog.acciones_posibles(
            self.guerra, self.master
        ))
        self.assertFalse(self._menu().boton_np.disabled)

    def test_quien_no_sabe_defenderse_no_se_defiende(self) -> None:
        yo = self.combate.batalla.combatientes["1"]
        # El rasgo vive en los datos del personaje y es inmutable, asi que se
        # tapa la propiedad mientras dura la prueba: lo que se comprueba es la
        # puerta del menu, no que haya un personaje que no sepa defenderse.
        from unittest import mock

        with mock.patch.object(
            type(yo), "puede_defender", property(lambda _: False)
        ):
            self.assertTrue(self._menu().boton_defender.disabled)
            texto = self.cog.decidir_en_combate(
                self.guerra, self.master, Decision(accion=Accion.DEFENDER)
            )
        self.assertIn("no sabe defenderse", texto)
        self.assertEqual(self.combate.batalla.turno, 0, "no gasto el turno")

    # --- habilidades ---

    def test_el_desplegable_de_habilidades_trae_las_que_estan_listas(self) -> None:
        listas = self.combate.batalla.habilidades_disponibles("1")
        opciones = self.cog.opciones_de_habilidad(self.guerra, self.master)
        self.assertEqual([int(v) for v, _, _ in opciones], listas)
        for _, etiqueta, _ in opciones:
            self.assertTrue(etiqueta.strip())

    def test_al_nivel_1_no_hay_habilidades_y_el_boton_se_apaga(self) -> None:
        """Las habilidades se desbloquean por nivel; el dia 1 nadie tiene."""
        self.assertEqual(self.master.servant.nivel, 1)
        self.assertEqual(self.cog.opciones_de_habilidad(self.guerra, self.master), [])
        menu = self._menu()
        self.assertTrue(menu.boton_habilidad.disabled)
        i = Interaccion(usuario=1)
        correr(menu.boton_habilidad.callback(i))
        self.assertIn("ninguna habilidad lista", i.ultimo)

    def test_usar_una_habilidad_gasta_el_turno(self) -> None:
        servant = self.master.servant
        servant.nivel = 15  # con el nivel se desbloquean las tres
        listas = self.combate.batalla.habilidades_disponibles("1")
        if not listas:
            self.skipTest("este Servant no tiene ninguna habilidad con nombre")
        numero = listas[0]
        objetivos = self.cog.opciones_de_objetivo_de_habilidad(
            self.guerra, self.master, numero
        )
        self.assertTrue(objetivos)
        texto = self.cog.decidir_en_combate(
            self.guerra,
            self.master,
            Decision(
                accion=Accion.HABILIDAD,
                objetivo=objetivos[0][0],
                habilidad=numero,
            ),
        )
        self.assertIn("Usaras", texto)
        self.assertGreaterEqual(self.combate.batalla.turno, 1)

    # --- votacion ---

    def test_cuando_cae_alguien_se_vota_y_los_botones_cambian(self) -> None:
        from src.game.combate import Espera

        # La votacion solo se abre si cae alguien y quedan 2 o mas en pie, asi
        # que esta prueba necesita una batalla de tres, no un duelo.
        self._montar_hasta(3)
        # Se tumba a uno a mano para no depender de 20 turnos de suerte.
        for c in self.combate.batalla.rivales_de("1")[:1]:
            c.vida = 1
        for _ in range(60):
            if self.combate.espera is Espera.VOTACION or self.combate.terminado:
                break
            self.combate.avanzar_con_ia()
        if self.combate.espera is not Espera.VOTACION:
            self.skipTest("la batalla acabo sin abrir votacion")

        menu = self._menu()
        self.assertIn(menu.boton_seguir, menu.children)
        self.assertNotIn(menu.boton_atacar, menu.children)
        self.assertIn("La batalla solo sigue", self.cog.texto_combate(
            self.guerra, self.master
        ))
        texto = self.cog.votar_en_combate(self.guerra, self.master, True)
        self.assertIn("Sigues peleando", texto)

    # --- el dia se cierra cuando acaban todas ---

    def test_la_ultima_batalla_cierra_el_dia(self) -> None:
        from src.commands import AbrirMenu

        estado = self.cog.combates[self.guerra.id]
        for c in estado.pendientes:
            while not c.terminado:
                c.avanzar_con_ia()
        i = Interaccion(usuario=1)
        correr(self.cog.cerrar_si_acabaron_los_combates(i, self.guerra))
        self.assertNotIn(self.guerra.id, self.cog.combates)
        self.assertEqual(self.guerra.fase, Fase.PREPARACION)
        self.assertEqual(self.guerra.dia, 2)
        self.assertIn("Empieza el dia 2", i.todo)
        self.assertTrue(
            any(isinstance(m[2], AbrirMenu) for m in i.buzon.mensajes),
            "el canal se queda sin boton para el dia nuevo",
        )

    def test_mientras_quede_una_batalla_el_dia_no_pasa(self) -> None:
        i = Interaccion(usuario=1)
        correr(self.cog.cerrar_si_acabaron_los_combates(i, self.guerra))
        self.assertEqual(self.guerra.dia, 1)
        self.assertEqual(i.buzon.mensajes, [])

    def test_el_canal_no_se_entera_de_lo_que_pasa_en_la_batalla(self) -> None:
        """Lo del turno es privado: nombra habilidades, y eso delata Servants."""
        menu = self._menu()
        i = Interaccion(usuario=1)
        correr(menu.boton_defender.callback(i))
        for texto, privado, _ in i.buzon.mensajes:
            if "```" in texto:
                self.assertTrue(privado, texto)

    def test_un_combate_es_de_quien_lo_abrio(self) -> None:
        menu = self._menu()
        i = Interaccion(usuario=2)
        self.assertFalse(correr_valor(menu.interaction_check(i)))
        self.assertIn("No estas", i.ultimo)


@unittest.skipUnless(HAY_DISCORD, "discord.py no esta instalado")
class PruebaElArteEnLaFicha(unittest.TestCase):
    """La ficha ensena el arte, y el de los rivales solo si peleaste con el."""

    def setUp(self) -> None:
        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        self.guerra = self.cog.guerras[100]
        self.master = self.guerra.masters["1"]
        self.guerra.invocar_para(self.master.id)

    def _menu(self):
        from src.commands import MenuAccion

        return MenuAccion(self.cog, self.guerra, self.master)

    def _conocer(self, id_: str = "bot:1") -> str:
        """Hace que el Master haya visto el Servant de ese rival."""
        self.guerra.invocar_a_los_que_falten()
        self.master.conocidos.add(id_)
        return id_

    # --- la ficha propia ---

    def test_la_ficha_trae_texto_arte_y_menu(self) -> None:
        from src.commands import MenuAccion

        i = Interaccion(usuario=1)
        correr(self.cog.estadisticas.callback(self.cog, i))
        texto, privado, vista = i.buzon.mensajes[-1]
        self.assertIn(self.master.servant.nombre, texto)
        self.assertIn(self.master.servant.clase.value, texto)
        self.assertIsInstance(vista, MenuAccion)
        self.assertTrue(privado, "la ficha es privada: delata tu Servant")
        self.assertIsNotNone(i.embed(), "falta el arte")

    def test_el_boton_deja_la_misma_pantalla_que_el_comando(self) -> None:
        """Dos caminos a la ficha: si no dejaran lo mismo, se notaria."""
        from src.commands import MenuAccion

        por_comando = Interaccion(usuario=1)
        correr(self.cog.estadisticas.callback(self.cog, por_comando))
        por_boton = Interaccion(usuario=1)
        correr(self._menu().boton_estadisticas.callback(por_boton))
        self.assertEqual(por_comando.ultimo, por_boton.ultimo)
        self.assertIsInstance(por_boton.vista(), MenuAccion)
        self.assertEqual(
            por_comando.embed().image.url, por_boton.embed().image.url
        )

    def test_el_arte_es_el_de_la_ascension_que_toca(self) -> None:
        for nivel in (1, 5, 10, 15):
            self.master.servant.nivel = nivel
            embed = self.cog.arte_del_servant(self.master.servant)
            self.assertEqual(embed.image.url, self.master.servant.imagen)

    def test_un_servant_sin_arte_no_rompe_la_ficha(self) -> None:
        """El arte es adorno; las estadisticas no. Sin URL, ficha en texto."""
        import dataclasses

        s = self.master.servant
        s.personaje = dataclasses.replace(s.personaje, imagenes=())
        self.assertIsNone(self.cog.arte_del_servant(s))
        i = Interaccion(usuario=1)
        correr(self.cog.estadisticas.callback(self.cog, i))
        self.assertIn(s.nombre, i.ultimo)
        self.assertIsNone(i.embed())

    # --- la invocacion ---

    def test_al_invocar_se_ensena_el_arte_en_privado(self) -> None:
        from src.commands import ComandosGuerra

        # Sin invocar: este Master pide su Servant ahora.
        self.cog = ComandosGuerra(bot=None)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        guerra = self.cog.guerras[100]
        i = Interaccion(usuario=1)
        correr(self.cog.invocar.callback(self.cog, i))
        servant = guerra.masters["1"].servant
        self.assertIsNotNone(servant)
        privados = [
            (n, m) for n, m in enumerate(i.buzon.mensajes) if m[1]
        ]
        self.assertTrue(privados)
        indice, (texto, _, _) = privados[0]
        self.assertIn(servant.nombre, texto)
        self.assertEqual(i.buzon.embeds[indice].image.url, servant.imagen)

    def test_el_canal_no_ve_el_arte_de_la_invocacion(self) -> None:
        """Ensenarlo en publico seria regalarle el Servant a los otros seis."""
        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        guerra = self.cog.guerras[100]
        i = Interaccion(usuario=1)
        correr(self.cog.invocar.callback(self.cog, i))
        servant = guerra.masters["1"].servant
        for n, (texto, privado, _) in enumerate(i.buzon.mensajes):
            if privado:
                continue
            self.assertNotIn(servant.nombre, texto)
            self.assertIsNone(i.buzon.embeds[n], "el arte no va al canal")

    def test_el_boton_de_invocar_tambien_ensena_el_arte(self) -> None:
        from src.commands import ComandosGuerra, MenuAccion

        self.cog = ComandosGuerra(bot=None)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        guerra = self.cog.guerras[100]
        master = guerra.masters["1"]
        menu = MenuAccion(self.cog, guerra, master)
        i = Interaccion(usuario=1)
        correr(menu.boton_invocar.callback(i))
        urls = [e.image.url for e in i.buzon.embeds if e is not None]
        self.assertEqual(urls, [master.servant.imagen])

    def test_si_la_invocacion_falla_no_se_busca_arte(self) -> None:
        """No hay Servant del que ensenar nada, y eso no puede reventar."""
        i = Interaccion(usuario=1, canal=777)
        correr(self.cog.invocar.callback(self.cog, i))
        self.assertIsNone(i.embed())
        self.assertIsNone(self.cog.arte_del_servant(None))

    # --- los Servants de los demas ---

    def test_al_principio_el_boton_de_conocidos_esta_apagado(self) -> None:
        """Es lo que te dice de un vistazo que todavia atacas a ciegas."""
        self.assertEqual(self.cog.servants_conocidos(self.guerra, self.master), [])
        self.assertTrue(self._menu().boton_conocidos.disabled)

    def test_tras_pelear_aparece_solo_ese(self) -> None:
        id_ = self._conocer()
        conocidos = self.cog.servants_conocidos(self.guerra, self.master)
        self.assertEqual([c[0] for c in conocidos], [id_])
        self.assertFalse(self._menu().boton_conocidos.disabled)

    def test_el_propio_no_sale_en_la_lista(self) -> None:
        """Para el suyo esta la ficha."""
        self._conocer()
        ids = [c[0] for c in self.cog.servants_conocidos(self.guerra, self.master)]
        self.assertNotIn(self.master.id, ids)

    def test_elegir_un_conocido_da_su_nombre_y_su_arte(self) -> None:
        from src.commands import VistaConocidos

        id_ = self._conocer()
        rival = self.guerra.masters[id_]
        vista = VistaConocidos(self.cog, self.guerra, self.master)
        i = Interaccion(usuario=1)
        correr(vista.mostrar(i, id_))
        texto, privado, _ = i.buzon.mensajes[-1]
        self.assertIn(rival.servant.nombre, texto)
        self.assertIn(rival.servant.clase.value, texto)
        self.assertTrue(privado, "lo que tu sabes de los demas es tuyo")
        self.assertEqual(i.embed().image.url, rival.servant.imagen)

    def test_no_se_puede_mirar_a_quien_no_has_peleado(self) -> None:
        """La regla del secreto: pedirlo a mano no la salta."""
        from src.commands import VistaConocidos

        self.guerra.invocar_a_los_que_falten()
        vista = VistaConocidos(self.cog, self.guerra, self.master)
        i = Interaccion(usuario=1)
        correr(vista.mostrar(i, "bot:2"))
        rival = self.guerra.masters["bot:2"]
        self.assertNotIn(rival.servant.nombre, i.ultimo)
        self.assertIsNone(i.embed())

    def test_la_ficha_de_un_conocido_no_cuenta_su_nivel(self) -> None:
        """Ensenar su nivel seria informacion nueva, o sea balance. Se mide."""
        id_ = self._conocer()
        rival = self.guerra.masters[id_]
        rival.servant.nivel = 11
        texto, _ = self.cog.ficha_del_conocido(self.guerra, self.master, id_)
        self.assertNotIn("11", texto)
        self.assertNotIn(str(rival.servant.vida_maxima), texto)

    def test_el_desplegable_es_de_quien_lo_abrio(self) -> None:
        from src.commands import VistaConocidos

        self._conocer()
        vista = VistaConocidos(self.cog, self.guerra, self.master)
        i = Interaccion(usuario=2)
        self.assertFalse(correr_valor(vista.interaction_check(i)))

    def test_nada_del_arte_llega_al_canal(self) -> None:
        """Ensenar un Servant en publico delataria quien lleva que."""
        from src.commands import VistaConocidos

        id_ = self._conocer()
        i = Interaccion(usuario=1)
        correr(self.cog.estadisticas.callback(self.cog, i))
        correr(self._menu().boton_conocidos.callback(i))
        correr(VistaConocidos(self.cog, self.guerra, self.master).mostrar(i, id_))
        publicos = [m[0] for m in i.buzon.mensajes if not m[1]]
        self.assertEqual(publicos, [])


@unittest.skipUnless(HAY_DISCORD, "discord.py no esta instalado")
@unittest.skipUnless(HAY_DISCORD, "hace falta discord.py")
class PruebaElInventarioEnDiscord(unittest.TestCase):
    """Del boton al efecto: lo que el Cog tiene que no perder ni duplicar.

    La regla que mas duele si se rompe es la del gasto: un objeto que se quita
    sin aplicarse, o que se aplica sin quitarse, no lo nota nadie hasta que
    alguien se queja de que su elixir no hizo nada.
    """

    def setUp(self) -> None:
        import random

        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        self.cog.rng = random.Random(7)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        correr(self.cog.invocar.callback(self.cog, Interaccion(usuario=1)))
        self.guerra = self.cog.guerras[100]
        self.master = self.guerra.masters["1"]

    @property
    def inv(self):
        return self.master.inventario

    # --- lo que lleva encima ---

    def test_el_inventario_vacio_lo_dice(self) -> None:
        texto = self.cog.texto_inventario(self.guerra, self.master)
        self.assertTrue(texto.strip())

    def test_el_inventario_agrupa_por_momento(self) -> None:
        self.inv.anadir("elixir")
        self.inv.anadir("tomo_saber")
        texto = self.cog.texto_inventario(self.guerra, self.master)
        idioma = self.guerra.idioma
        self.assertIn(objetos.objeto("elixir").nombre_para(idioma), texto)
        self.assertIn(objetos.objeto("tomo_saber").nombre_para(idioma), texto)

    def test_en_preparacion_solo_se_ofrecen_los_de_preparacion(self) -> None:
        self.inv.anadir("elixir")
        self.inv.anadir("tomo_saber")
        self.inv.anadir("catalizador_saber")
        claves = [o.clave for o, _ in self.cog.objetos_usables_ahora(self.guerra, self.master)]
        self.assertEqual(claves, ["tomo_saber"])

    def test_la_suelta_entra_en_el_inventario(self) -> None:
        suelto = objetos.objeto("elixir")
        texto = self.cog.texto_de_la_suelta(self.guerra, self.master, suelto)
        self.assertEqual(self.inv.cuantos_de("elixir"), 1)
        self.assertIn(suelto.nombre_para(self.guerra.idioma), texto)

    def test_una_suelta_con_el_inventario_lleno_se_cuenta_y_se_pierde(self) -> None:
        """Reventar aqui le romperia el dia a quien acaba de ganar."""
        for _ in range(objetos.TOPE_INVENTARIO):
            self.inv.anadir("elixir")
        texto = self.cog.texto_de_la_suelta(
            self.guerra, self.master, objetos.objeto("tomo_saber")
        )
        self.assertTrue(texto.strip())
        self.assertEqual(self.inv.total, objetos.TOPE_INVENTARIO)
        self.assertFalse(self.inv.tiene("tomo_saber"))

    # --- usar en preparacion ---

    def test_el_tomo_da_xp_y_se_gasta(self) -> None:
        self.inv.anadir("tomo_saber")
        # El nivel y la XP juntos, porque la XP justa para subir deja el
        # sobrante a cero y mirar solo la XP no veria nada.
        antes = (self.master.servant.nivel, self.master.servant.xp)
        self.cog.usar_objeto_en_preparacion(self.guerra, self.master, "tomo_saber")
        self.assertGreater((self.master.servant.nivel, self.master.servant.xp), antes)
        self.assertFalse(self.inv.tiene("tomo_saber"))

    def test_el_vendaje_borra_las_derrotas_contra_npc(self) -> None:
        self.master.derrotas_npc = 2
        self.inv.anadir("vendaje")
        self.cog.usar_objeto_en_preparacion(self.guerra, self.master, "vendaje")
        self.assertEqual(self.master.derrotas_npc, 0)

    def test_el_reloj_devuelve_un_intento_de_entrenamiento(self) -> None:
        self.master.intentos_npc = 1
        self.inv.anadir("reloj_arena")
        self.cog.usar_objeto_en_preparacion(self.guerra, self.master, "reloj_arena")
        self.assertEqual(self.master.intentos_npc, 0, "el boton se reenciende")

    def test_lo_que_no_se_tiene_no_se_usa(self) -> None:
        texto = self.cog.usar_objeto_en_preparacion(self.guerra, self.master, "tomo_saber")
        self.assertTrue(texto.strip())
        self.assertTrue(self.inv.vacio)

    def test_un_objeto_de_combate_no_se_usa_en_preparacion(self) -> None:
        self.inv.anadir("elixir")
        self.cog.usar_objeto_en_preparacion(self.guerra, self.master, "elixir")
        self.assertTrue(self.inv.tiene("elixir"), "no se gasta por intentarlo")

    def test_un_catalizador_todavia_no_hace_nada_pero_no_se_pierde(self) -> None:
        """La mecanica esta sin cerrar; lo que no puede pasar es gastarlo."""
        self.inv.anadir("catalizador_saber")
        self.cog.usar_objeto_en_preparacion(self.guerra, self.master, "catalizador_saber")
        self.assertTrue(self.inv.tiene("catalizador_saber"))

    def test_estando_listo_no_se_usa_un_objeto_de_preparacion(self) -> None:
        """Mismo motivo que no entrenar: cerrarias el dia y seguirias jugando."""
        self.master.listo = True
        self.inv.anadir("tomo_saber")
        antes = self.master.servant.xp
        self.cog.usar_objeto_en_preparacion(self.guerra, self.master, "tomo_saber")
        self.assertTrue(self.inv.tiene("tomo_saber"))
        self.assertEqual(self.master.servant.xp, antes)

    def test_una_clave_inventada_no_revienta(self) -> None:
        self.cog.usar_objeto_en_preparacion(self.guerra, self.master, "no_existe")

    # --- usar en combate ---

    def test_fuera_de_una_batalla_no_hay_objetos_de_combate(self) -> None:
        self.inv.anadir("elixir")
        self.assertEqual(self.cog.objetos_de_combate(self.guerra, self.master), [])

    def test_un_objeto_de_preparacion_no_se_usa_en_combate(self) -> None:
        self.inv.anadir("tomo_saber")
        antes = self.master.servant.xp
        self.cog.usar_objeto_en_combate(self.guerra, self.master, "tomo_saber")
        self.assertEqual(self.master.servant.xp, antes)
        self.assertTrue(self.inv.tiene("tomo_saber"))

    def test_sin_batalla_no_se_gasta_un_objeto_de_combate(self) -> None:
        self.inv.anadir("elixir")
        texto = self.cog.usar_objeto_en_combate(self.guerra, self.master, "elixir")
        self.assertTrue(texto.strip())
        self.assertTrue(self.inv.tiene("elixir"), "nada de perderlo sin efecto")

    def test_el_dia_nuevo_guarda_los_objetos(self) -> None:
        """Duran la guerra. Lo unico que vuelve a cero es el uso por batalla."""
        self.inv.anadir("elixir")
        self.inv.usados_en_la_batalla = 1
        self.master.nuevo_dia()
        self.assertTrue(self.inv.tiene("elixir"))
        self.assertTrue(self.inv.puede_usar_en_la_batalla)


@unittest.skipUnless(HAY_DISCORD, "hace falta discord.py")
class PruebaElDiaSeCierraSolo(unittest.TestCase):
    """La cuarta puerta: si no falta nadie, las batallas empiezan solas.

    Antes decirse listo solo apuntaba que ya estabas, y el dia lo tenia que
    cerrar el creador con el boton rojo **aunque no quedara nadie a quien
    esperar**. El boton rojo ya exigia que todos estuvieran listos, asi que
    pulsarlo no decidia nada: solo hacia falta.

    Lo que se fija aqui es que la puerta nueva deja **la misma mesa** que las
    otras tres, que es la regla de la casa sobre cerrar un dia.
    """

    def _montar(self, humanos: int = 1, semilla: int = 7):
        import random

        from src.commands import ComandosGuerra

        cog = ComandosGuerra(bot=None)
        cog.rng = random.Random(semilla)
        correr(
            cog.crear_guerra.callback(
                cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        # `crear_guerra` no le pone semilla a la guerra, asi que su `rng` es
        # uno de verdad y dos corridas de la misma prueba salian distintas (y
        # una de cada tres fallaba). Se le pone aqui, antes de `empezar`, que
        # es lo primero que lo usa.
        cog.guerras[100].rng = random.Random(semilla)
        for usuario in range(2, humanos + 1):
            correr(cog.unirse_a_guerra.callback(cog, Interaccion(usuario=usuario)))
        correr(cog.empezar_guerra.callback(cog, Interaccion(usuario=1)))
        guerra = cog.guerras[100]
        for usuario in range(1, humanos + 1):
            guerra.invocar_para(str(usuario))
        return cog, guerra

    def _menu(self, cog, guerra, usuario: int):
        from src.commands import MenuAccion

        return MenuAccion(cog, guerra, guerra.masters[str(usuario)])

    def _acabo_el_dia_1(self, guerra) -> None:
        """Que la preparacion del dia 1 se acabo, sea como sea.

        No se puede exigir `Fase.BATALLA`: si al humano le toco descansar, las
        batallas son todas de bots, salen ya resueltas y el dia se cierra
        entero de corrido, asi que la fase vuelve a ser PREPARACION pero del
        dia 2. Y a quien le toca pelear depende del orden en que se recorren
        los Masters, que cambia de una corrida a otra (`PYTHONHASHSEED`), asi
        que exigir una de las dos salidas hacia que la prueba fallara una de
        cada tres veces sin que nada estuviera roto.
        """
        self.assertTrue(
            guerra.fase is not Fase.PREPARACION or guerra.dia > 1,
            "la preparacion del dia 1 sigue abierta",
        )

    def _decir_listo(self, cog, guerra, usuario: int) -> Interaccion:
        i = Interaccion(usuario=usuario)
        menu = self._menu(cog, guerra, usuario)
        correr(menu.boton_listo.callback(i))
        return i

    # --- lo que pidio Cristopher ---

    def test_el_ultimo_en_decirse_listo_cierra_el_dia(self) -> None:
        """La preparacion del dia 1 se acaba sin que nadie pulse el boton rojo."""
        cog, guerra = self._montar()
        self.assertIs(guerra.fase, Fase.PREPARACION)
        self._decir_listo(cog, guerra, 1)
        self._acabo_el_dia_1(guerra)

    def test_con_dos_personas_el_primero_no_cierra_nada(self) -> None:
        """Decirse listo no puede cerrarle el dia a quien todavia juega."""
        cog, guerra = self._montar(humanos=2)
        self._decir_listo(cog, guerra, 1)
        self.assertIs(guerra.fase, Fase.PREPARACION)
        self.assertEqual(guerra.dia, 1)

    def test_con_dos_personas_el_segundo_si(self) -> None:
        cog, guerra = self._montar(humanos=2)
        self._decir_listo(cog, guerra, 1)
        self._decir_listo(cog, guerra, 2)
        self._acabo_el_dia_1(guerra)

    def test_el_canal_se_entera(self) -> None:
        """Cerrar el dia es la mitad; la otra es dejar el boton que toque."""
        cog, guerra = self._montar()
        i = self._decir_listo(cog, guerra, 1)
        publicos = [m for m in i.buzon.mensajes if not m[1]]
        self.assertTrue(publicos, "algo se cuenta en el canal")
        self.assertTrue(
            any(vista is not None for _, _, vista in publicos),
            "y se queda un boton: el de abrir tu batalla o el del dia nuevo",
        )

    def test_el_boton_rojo_desaparece_del_menu(self) -> None:
        """Ofrecer cerrar lo que ya esta cerrado solo despista."""
        cog, guerra = self._montar()
        menu = self._menu(cog, guerra, 1)
        self.assertIn(menu.boton_batallas, menu.children)
        correr(menu.boton_listo.callback(Interaccion(usuario=1)))
        self.assertNotIn(menu.boton_batallas, menu.children)

    def test_un_menu_de_ayer_no_cierra_el_dia_de_hoy(self) -> None:
        """Lo encontro esta prueba, no una partida.

        Un menu efimero se queda abierto en la pantalla de quien lo abrio. Si
        otro cierra el dia mientras tanto, lo que tiene delante es de ayer, y
        decirse listo ahi le cerraba el dia nuevo **sin haberlo jugado**: sin
        entrenar, sin declarar a nadie.
        """
        from src.commands import MenuAccion

        cog, guerra = self._montar(humanos=2)
        menu_de_ayer = MenuAccion(cog, guerra, guerra.masters["2"])
        # El otro cierra el dia: el menu del segundo se queda viejo.
        self._decir_listo(cog, guerra, 1)
        guerra.masters["2"].listo = True
        correr(cog.empezar_batallas.callback(cog, Interaccion(usuario=1)))
        while guerra.fase is not Fase.PREPARACION and not guerra.terminada:
            estado = cog.combates.get(guerra.id)
            if estado is None:
                break
            for c in list(estado.combates):
                while not c.terminado:
                    c.avanzar_con_ia()
            cog.cierre_de_los_combates(guerra)
        if guerra.terminada or guerra.dia == menu_de_ayer.dia_del_menu:
            self.skipTest("esa guerra no llego a tener un dia nuevo")

        dia_de_hoy, fase = guerra.dia, guerra.fase
        i = Interaccion(usuario=2)
        correr(menu_de_ayer.boton_listo.callback(i))
        self.assertEqual(guerra.dia, dia_de_hoy, "no cerro el dia nuevo")
        self.assertIs(guerra.fase, fase)
        self.assertFalse(
            guerra.masters["2"].listo, "y no le dio por acabado el dia"
        )
        self.assertTrue(i.buzon.mensajes[-1][1], "se le dice en privado")

    def test_a_un_eliminado_no_se_le_espera(self) -> None:
        """Si se le esperara, el dia no cerraria nunca y la guerra se colgaria."""
        cog, guerra = self._montar(humanos=2)
        guerra.masters["2"].derrotas = DERROTAS_PARA_ELIMINAR
        self.assertTrue(guerra.masters["2"].eliminado)
        self._decir_listo(cog, guerra, 1)
        self._acabo_el_dia_1(guerra)

    def test_quien_no_ha_invocado_tambien_puede_cerrar_el_dia(self) -> None:
        """`formar_batallas` invoca por quien falte, asi que no bloquea."""
        import random

        from src.commands import ComandosGuerra

        cog = ComandosGuerra(bot=None)
        cog.rng = random.Random(7)
        correr(
            cog.crear_guerra.callback(
                cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(cog.empezar_guerra.callback(cog, Interaccion(usuario=1)))
        guerra = cog.guerras[100]
        self.assertIsNone(guerra.masters["1"].servant, "no invoco a proposito")
        self._decir_listo(cog, guerra, 1)
        self._acabo_el_dia_1(guerra)
        self.assertIsNotNone(guerra.masters["1"].servant, "le invocaron al cerrar")

    # --- las cuatro puertas dejan la misma mesa ---

    def test_la_puerta_nueva_deja_lo_mismo_que_el_boton_rojo(self) -> None:
        """La regla de la casa, hecha prueba.

        Se cierran dos guerras iguales con la misma semilla, una por cada
        puerta, y se compara la mesa que queda: el dia, la fase, si hay
        batallas en curso y que boton se quedo en el canal. Si una puerta
        dejara algo distinto, aqui se ve.
        """
        from src.commands import MenuAccion

        def por_el_boton_rojo():
            cog, guerra = self._montar()
            menu = MenuAccion(cog, guerra, guerra.masters["1"])
            correr(menu.boton_batallas.callback(Interaccion(usuario=1)))
            return cog, guerra

        def por_decirse_listo():
            cog, guerra = self._montar()
            self._decir_listo(cog, guerra, 1)
            return cog, guerra

        def mesa(cog, guerra):
            aviso, vista = cog.aviso_y_vista_de_despues(guerra)
            return (
                guerra.dia,
                guerra.fase,
                guerra.id in cog.combates,
                aviso,
                type(vista).__name__,
            )

        self.assertEqual(mesa(*por_el_boton_rojo()), mesa(*por_decirse_listo()))

    def test_la_puerta_nueva_deja_lo_mismo_que_el_comando(self) -> None:
        def por_el_comando():
            cog, guerra = self._montar()
            correr(cog.empezar_batallas.callback(cog, Interaccion(usuario=1)))
            return cog, guerra

        def por_decirse_listo():
            cog, guerra = self._montar()
            self._decir_listo(cog, guerra, 1)
            return cog, guerra

        def mesa(cog, guerra):
            aviso, vista = cog.aviso_y_vista_de_despues(guerra)
            return (guerra.dia, guerra.fase, guerra.id in cog.combates, aviso)

        self.assertEqual(mesa(*por_el_comando()), mesa(*por_decirse_listo()))

    def test_el_boton_rojo_sigue_sirviendo(self) -> None:
        """No se quita: hace falta si alguien se dijo listo antes de un reinicio."""
        from src.commands import MenuAccion

        cog, guerra = self._montar()
        guerra.masters["1"].listo = True  # como si viniera de la base de datos
        menu = MenuAccion(cog, guerra, guerra.masters["1"])
        correr(menu.boton_batallas.callback(Interaccion(usuario=1)))
        self._acabo_el_dia_1(guerra)

    def test_puede_cerrarse_ya_dice_lo_mismo_que_el_boton(self) -> None:
        """Si miraran cosas distintas, habria dias que no cierra ninguno."""
        cog, guerra = self._montar(humanos=2)
        self.assertFalse(cog.puede_cerrarse_ya(guerra))
        self.assertIsNotNone(cog.aviso_si_no_se_puede_cerrar(guerra))
        for id_ in ("1", "2"):
            guerra.masters[id_].listo = True
        self.assertTrue(cog.puede_cerrarse_ya(guerra))
        self.assertIsNone(cog.aviso_si_no_se_puede_cerrar(guerra))

    def test_fuera_de_la_preparacion_no_se_cierra_nada(self) -> None:
        cog, guerra = self._montar()
        guerra.fase = Fase.BATALLA
        self.assertFalse(cog.puede_cerrarse_ya(guerra))


@unittest.skipUnless(HAY_DISCORD, "hace falta discord.py")
class PruebaRepartirElTurno(unittest.TestCase):
    """El fallo que conto Cristopher: solo veia el turno uno de los dos.

    Un turno se resuelve cuando decide el **ultimo**, y `Combate.decidir` solo
    le devuelve los eventos a ese. Al otro le quedaba "tu decision queda
    apuntada" y nada mas, asi que no veia el turno y tampoco tenia forma de
    saber que habia pasado algo para ir a refrescar.

    Lo que se fija aqui es que a los demas se les va a buscar, y que no se les
    cuenta una batalla que no es la suya.
    """

    def setUp(self) -> None:
        self._montar_con_dos()

    def _montar_con_dos(self) -> None:
        """Una guerra con dos personas que peleen **la misma** batalla.

        No basta con que las dos declaren: `formar_batallas` puede separarlas.
        Asi que se prueba semilla a semilla hasta que caigan juntas.
        """
        import random

        from src.commands import ComandosGuerra

        for semilla in range(80):
            cog = ComandosGuerra(bot=None)
            cog.rng = random.Random(semilla)
            correr(
                cog.crear_guerra.callback(
                    cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
                )
            )
            correr(cog.unirse_a_guerra.callback(cog, Interaccion(usuario=2)))
            correr(cog.empezar_guerra.callback(cog, Interaccion(usuario=1)))
            guerra = cog.guerras[100]
            for id_ in ("1", "2"):
                guerra.invocar_para(id_)
            guerra.declarar_ataque("1", "2")
            guerra.declarar_ataque("2", "1")
            # El dia no se cierra mientras falte una persona viva por estar
            # lista (`puede_cerrar`), asi que el segundo tiene que decirlo o
            # no hay batalla que pelear. Sin esto la prueba se saltaba siempre.
            guerra.masters["2"].listo = True
            correr(
                cog.empezar_batallas.callback(cog, Interaccion(usuario=1))
            )
            combate = cog.combate_de(guerra, guerra.masters["1"])
            if combate is None or cog.combate_de(
                guerra, guerra.masters["2"]
            ) is not combate:
                continue
            if combate.humanos != {"1", "2"}:
                continue
            self.cog, self.guerra, self.combate = cog, guerra, combate
            self.uno = guerra.masters["1"]
            self.dos = guerra.masters["2"]
            return
        self.skipTest("ninguna semilla puso a las dos personas en la misma batalla")

    def _abrir(self, usuario: int):
        """Abre el combate de alguien desde el boton del canal, como de verdad."""
        from src.commands import AbrirCombate

        i = Interaccion(usuario=usuario)
        correr(AbrirCombate(self.cog, self.guerra).boton.callback(i))
        return i

    def _rival_de(self, id_: str) -> str:
        return self.combate.batalla.rivales_de(id_)[0].id

    # --- el fallo ---

    def test_al_que_no_cierra_el_turno_se_le_avisa(self) -> None:
        """La prueba del fallo. Sin el arreglo, `avisados` sale vacio."""
        self._abrir(1)
        i_dos = self._abrir(2)

        # El primero decide: todavia no pasa nada, y eso esta bien.
        primero = self.cog.decidir_en_combate(
            self.guerra, self.uno, Decision(accion=Accion.ATACAR, objetivo="2")
        )
        self.assertNotIn("```", primero, "con uno solo el turno no se resuelve")

        # El segundo cierra el turno.
        self.cog.decidir_en_combate(
            self.guerra, self.dos, Decision(accion=Accion.ATACAR, objetivo="1")
        )
        avisados = correr_valor(self.cog.repartir_el_turno(self.guerra, "2"))
        self.assertEqual(avisados, ["1"], "al otro hay que ir a buscarlo")

    def test_al_avisado_le_llega_el_turno_y_el_menu_al_dia(self) -> None:
        i_uno = self._abrir(1)
        self._abrir(2)
        mensajes_antes = len(i_uno.buzon.mensajes)

        self.cog.decidir_en_combate(
            self.guerra, self.uno, Decision(accion=Accion.ATACAR, objetivo="2")
        )
        self.cog.decidir_en_combate(
            self.guerra, self.dos, Decision(accion=Accion.ATACAR, objetivo="1")
        )
        correr_valor(self.cog.repartir_el_turno(self.guerra, "2"))

        # Dos cosas, y las dos importan: el menu reescrito (su vida y su mana
        # han cambiado) y un mensaje nuevo, que es lo que de verdad avisa.
        self.assertTrue(i_uno.ediciones.hechas, "le reescribio el menu")
        self.assertGreater(
            len(i_uno.buzon.mensajes), mensajes_antes, "y le mando el turno"
        )
        self.assertIn("```", i_uno.buzon.mensajes[-1][0], "con el registro")
        self.assertTrue(i_uno.buzon.mensajes[-1][1], "en privado, como siempre")

    def test_el_que_cierra_el_turno_no_se_avisa_dos_veces(self) -> None:
        """Ya lo vio en la respuesta a su propia decision."""
        self._abrir(1)
        i_dos = self._abrir(2)
        mensajes_antes = len(i_dos.buzon.mensajes)
        self.cog.decidir_en_combate(
            self.guerra, self.uno, Decision(accion=Accion.ATACAR, objetivo="2")
        )
        self.cog.decidir_en_combate(
            self.guerra, self.dos, Decision(accion=Accion.ATACAR, objetivo="1")
        )
        correr_valor(self.cog.repartir_el_turno(self.guerra, "2"))
        self.assertEqual(len(i_dos.buzon.mensajes), mensajes_antes)
        self.assertEqual(i_dos.ediciones.hechas, [])

    def test_un_turno_sin_resolver_no_reparte_nada(self) -> None:
        self._abrir(1)
        self._abrir(2)
        self.cog.decidir_en_combate(
            self.guerra, self.uno, Decision(accion=Accion.ATACAR, objetivo="2")
        )
        self.assertEqual(correr_valor(self.cog.repartir_el_turno(self.guerra, "1")), [])

    def test_el_mismo_turno_no_se_reparte_dos_veces(self) -> None:
        """Si se repartiera, veria el turno repetido cada vez que alguien toca algo."""
        self._abrir(1)
        self._abrir(2)
        self.cog.decidir_en_combate(
            self.guerra, self.uno, Decision(accion=Accion.ATACAR, objetivo="2")
        )
        self.cog.decidir_en_combate(
            self.guerra, self.dos, Decision(accion=Accion.ATACAR, objetivo="1")
        )
        self.assertEqual(
            correr_valor(self.cog.repartir_el_turno(self.guerra, "2")), ["1"]
        )
        self.assertEqual(
            correr_valor(self.cog.repartir_el_turno(self.guerra, "2")),
            [],
            "el segundo reparto no tiene nada que repartir",
        )

    def test_a_quien_no_abrio_su_combate_no_se_le_puede_avisar(self) -> None:
        """Y no pasa nada: cuando lo abra vera el estado al dia.

        Sin mesa no hay por donde hablarle. Lo que no puede es reventar.
        """
        self._abrir(2)  # solo el segundo abre
        self.cog.decidir_en_combate(
            self.guerra, self.uno, Decision(accion=Accion.ATACAR, objetivo="2")
        )
        self.cog.decidir_en_combate(
            self.guerra, self.dos, Decision(accion=Accion.ATACAR, objetivo="1")
        )
        self.assertEqual(correr_valor(self.cog.repartir_el_turno(self.guerra, "2")), [])

    def _atacar_con_el_boton(self, usuario: int, master) -> None:
        """Ataca desde el menu de verdad, como lo haria una persona.

        Por aqui es por donde paso el fallo: el metodo del Cog se podia probar
        y estar bien, y el boton no avisar a nadie igual. Si hay varios rivales
        el menu pregunta a cual, asi que esta prueba contesta tambien eso.
        """
        from src.commands import MenuCombate, VistaObjetivo

        menu = MenuCombate(self.cog, self.guerra, master)
        i = Interaccion(usuario=usuario)
        correr(menu.boton_atacar.callback(i))
        vista = i.vista() if i.buzon.mensajes else None
        if isinstance(vista, VistaObjetivo):
            rival = self._rival_de(master.id)
            correr(vista.elegir(Interaccion(usuario=usuario), rival))

    def test_el_camino_de_verdad_avisa_al_otro(self) -> None:
        """De punta a punta: dos personas, dos botones, los dos ven el turno."""
        i_uno = self._abrir(1)
        self._abrir(2)
        mensajes_antes = len(i_uno.buzon.mensajes)

        self._atacar_con_el_boton(1, self.uno)
        self.assertEqual(
            len(i_uno.ediciones.hechas),
            0,
            "con uno solo no hay turno, asi que no hay nada que avisar",
        )

        self._atacar_con_el_boton(2, self.dos)
        self.assertTrue(
            i_uno.ediciones.hechas, "el turno se resolvio y al primero se le aviso"
        )
        self.assertGreater(len(i_uno.buzon.mensajes), mensajes_antes)

    # --- el secreto, que no se puede romper por avisar ---

    def test_solo_se_avisa_a_los_de_tu_batalla(self) -> None:
        """Contarle el turno a quien pelea en otra mesa seria regalarselo."""
        a_quien = self.cog.quien_mas_pelea_con(self.guerra, "1")
        self.assertEqual([m.id for m in a_quien], ["2"])
        for master in a_quien:
            self.assertIs(
                self.cog.combate_de(self.guerra, master),
                self.combate,
                "nadie de otra batalla",
            )

    def test_a_los_bots_no_se_les_avisa(self) -> None:
        """No tienen Discord al que hablarle, y `humanos` ya los deja fuera."""
        for master in self.cog.quien_mas_pelea_con(self.guerra, "1"):
            self.assertFalse(master.es_bot)

    def test_el_aviso_va_en_privado_y_no_al_canal(self) -> None:
        """Las frases del turno nombran habilidades, y eso delata al Servant."""
        i_uno = self._abrir(1)
        self._abrir(2)
        self.cog.decidir_en_combate(
            self.guerra, self.uno, Decision(accion=Accion.ATACAR, objetivo="2")
        )
        self.cog.decidir_en_combate(
            self.guerra, self.dos, Decision(accion=Accion.ATACAR, objetivo="1")
        )
        correr_valor(self.cog.repartir_el_turno(self.guerra, "2"))
        for texto, privado, _ in i_uno.buzon.mensajes:
            self.assertTrue(privado, f"esto se fue al canal: {texto[:60]}")

    # --- las mesas, que viven en memoria ---

    def test_abrir_el_combate_apunta_la_mesa(self) -> None:
        self.assertEqual(self.cog.mesas, {})
        self._abrir(1)
        self.assertIn((self.guerra.id, "1"), self.cog.mesas)

    def test_tocar_el_menu_renueva_la_mesa(self) -> None:
        """La interaccion caduca a los 15 minutos; la ultima es la que sirve."""
        from src.commands import MenuCombate

        self._abrir(1)
        primera = self.cog.mesas[(self.guerra.id, "1")]
        menu = MenuCombate(self.cog, self.guerra, self.uno)
        i = Interaccion(usuario=1)
        self.assertTrue(correr_valor(menu.interaction_check(i)))
        self.assertIsNot(self.cog.mesas[(self.guerra.id, "1")], primera)

    def test_el_menu_de_otro_no_apunta_mesa(self) -> None:
        from src.commands import MenuCombate

        menu = MenuCombate(self.cog, self.guerra, self.uno)
        self.assertFalse(correr_valor(menu.interaction_check(Interaccion(usuario=2))))
        self.assertEqual(self.cog.mesas, {})

    def test_al_cerrarse_el_dia_se_sueltan_las_mesas(self) -> None:
        """El menu que tenian delante es de un dia que ya paso."""
        self._abrir(1)
        self._abrir(2)
        while not self.combate.terminado:
            self.combate.avanzar_con_ia()
        self.cog.cierre_de_los_combates(self.guerra)
        self.assertEqual(self.cog.mesas, {})

    def test_terminar_la_guerra_suelta_las_mesas(self) -> None:
        self._abrir(1)
        self.cog.terminar_guerra(self.guerra)
        self.assertEqual(self.cog.mesas, {})
        self.assertEqual(self.cog.turnos_por_repartir, {})


@unittest.skipUnless(HAY_DISCORD, "hace falta discord.py")
class PruebaLaTienda(unittest.TestCase):
    """La tienda desde el Cog: el escaparate, las dos monedas y los avisos.

    Sin conexion el Cog lleva las cuentas en memoria (ver `cuenta_de`), asi que
    estas pruebas no necesitan base de datos.
    """

    def setUp(self) -> None:
        import random

        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        self.cog.rng = random.Random(7)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        correr(self.cog.invocar.callback(self.cog, Interaccion(usuario=1)))
        self.guerra = self.cog.guerras[100]
        self.master = self.guerra.masters["1"]

    @property
    def cuenta(self):
        return self.cog.cuenta_de("1")

    # --- el escaparate ---

    def test_el_escaparate_dice_los_precios_y_las_dos_monedas(self) -> None:
        texto = self.cog.texto_tienda(self.guerra, self.master)
        for clave, precio in tienda.PRECIO_EN_ORO.items():
            nombre = objetos.objeto(clave).nombre_para(self.guerra.idioma)
            self.assertIn(nombre, texto)
            self.assertIn(str(precio), texto)
        self.assertIn(str(tienda.PRECIO_CATALIZADOR_CLASE), texto)
        self.assertIn(str(tienda.PRECIO_CATALIZADOR_SERVANT), texto)

    def test_el_boton_lleva_el_oro_en_la_etiqueta(self) -> None:
        from src.commands import MenuAccion

        self.master.oro = 135
        menu = MenuAccion(self.cog, self.guerra, self.master)
        self.assertIn("135", menu.boton_tienda.label)

    def test_la_cuenta_empieza_a_cero_y_se_puede_preguntar(self) -> None:
        self.assertEqual(self.cuenta.griales, 0)
        self.assertIn("0", self.cog.texto_monedas(self.guerra, self.master))

    # --- comprar con oro ---

    def test_comprar_con_oro(self) -> None:
        self.master.oro = 200
        texto = self.cog.comprar_con_oro(self.guerra, self.master, "elixir")
        self.assertIn(
            objetos.objeto("elixir").nombre_para(self.guerra.idioma), texto
        )
        self.assertTrue(self.master.inventario.tiene("elixir"))
        self.assertEqual(self.master.oro, 200 - tienda.PRECIO_EN_ORO["elixir"])

    def test_sin_oro_se_dice_cuanto_falta(self) -> None:
        self.master.oro = 1
        texto = self.cog.comprar_con_oro(self.guerra, self.master, "elixir")
        self.assertIn(str(tienda.PRECIO_EN_ORO["elixir"]), texto)
        self.assertTrue(self.master.inventario.vacio)
        self.assertEqual(self.master.oro, 1)

    def test_la_tienda_no_abre_estando_listo(self) -> None:
        """Mismo motivo que no entrenar: cerrar el dia lo cierra para ti."""
        self.master.oro = 500
        self.master.listo = True
        self.assertIsNotNone(
            self.cog.motivo_para_no_comprar(self.guerra, self.master)
        )
        self.cog.comprar_con_oro(self.guerra, self.master, "elixir")
        self.assertTrue(self.master.inventario.vacio)
        self.assertEqual(self.master.oro, 500)

    def test_la_tienda_no_abre_fuera_de_la_preparacion(self) -> None:
        """Si abriera en la batalla, el objeto no seria algo que decides llevar."""
        self.master.oro = 500
        self.guerra.fase = Fase.BATALLA
        self.cog.comprar_con_oro(self.guerra, self.master, "elixir")
        self.assertTrue(self.master.inventario.vacio)
        self.assertEqual(self.master.oro, 500)

    def test_entrenar_da_oro(self) -> None:
        antes = self.master.oro
        texto = self.cog.pelear_npc(self.guerra, self.master)
        if "0" in texto and self.master.oro == antes:
            self.skipTest("ese entrenamiento se perdio")
        self.assertGreater(self.master.oro, antes)

    # --- comprar catalizadores ---

    def test_un_catalizador_de_clase_con_griales(self) -> None:
        self.cuenta.ingresar(tienda.PRECIO_CATALIZADOR_CLASE)
        texto = self.cog.comprar_catalizador_de_clase(
            self.guerra, self.master, "Saber"
        )
        self.assertTrue(texto.strip())
        self.assertTrue(self.master.inventario.tiene("catalizador_saber"))
        self.assertEqual(self.cuenta.griales, 0)

    def test_sin_griales_no_hay_catalizador(self) -> None:
        self.cog.comprar_catalizador_de_clase(self.guerra, self.master, "Saber")
        self.assertTrue(self.master.inventario.vacio)

    def test_una_clase_inventada_no_revienta(self) -> None:
        self.cuenta.ingresar(9)
        self.cog.comprar_catalizador_de_clase(
            self.guerra, self.master, "Panadero"
        )
        self.assertTrue(self.master.inventario.vacio)
        self.assertEqual(self.cuenta.griales, 9)

    def test_un_catalizador_de_servant_por_su_nombre(self) -> None:
        self.cuenta.ingresar(tienda.PRECIO_CATALIZADOR_SERVANT)
        self.cog.comprar_catalizador_de_servant(
            self.guerra, self.master, "Ryougi Shiki (Saber)"
        )
        self.assertTrue(self.master.inventario.tiene("catalizador_servant:91"))
        self.assertEqual(self.cuenta.griales, 0)

    def test_un_nombre_que_no_existe_no_cobra(self) -> None:
        self.cuenta.ingresar(9)
        texto = self.cog.comprar_catalizador_de_servant(
            self.guerra, self.master, "Don Pepito"
        )
        self.assertIn("Don Pepito", texto)
        self.assertEqual(self.cuenta.griales, 9)
        self.assertTrue(self.master.inventario.vacio)

    def test_un_nombre_ambiguo_no_cobra_y_ensena_los_que_encajan(self) -> None:
        """Hay tres Medusa. 5 griales son tres guerras: no se adivina.

        Y no hay ninguna que se llame "Medusa" a secas: los repetidos se
        desambiguan con la clase, asi que las tres son "Medusa (algo)". Por eso
        escribir "Medusa" no puede comprar nada.
        """
        self.cuenta.ingresar(9)
        texto = self.cog.comprar_catalizador_de_servant(
            self.guerra, self.master, "Medusa"
        )
        self.assertEqual(self.cuenta.griales, 9)
        self.assertTrue(self.master.inventario.vacio)
        self.assertIn("Medusa (Rider)", texto, "y se le ensenan las que son")

    def test_con_la_clase_ya_no_es_ambiguo(self) -> None:
        """La salida del caso de arriba: la clase es lo que las distingue."""
        encontrados = self.cog.buscar_en_el_plantel("Medusa (Rider)")
        self.assertEqual([p.nombre for p in encontrados], ["Medusa (Rider)"])

    def test_el_nombre_exacto_gana_al_parecido(self) -> None:
        """Hay quien se llama como el principio de otro.

        "Altria Pendragon" es un Servant, y "Altria Pendragon (Alter)" es otro.
        Escribir el primero tiene que comprar el primero, no quedarse en
        ambiguo para siempre.
        """
        encontrados = self.cog.buscar_en_el_plantel("Altria Pendragon")
        self.assertEqual([p.nombre for p in encontrados], ["Altria Pendragon"])

    def test_buscar_no_distingue_mayusculas(self) -> None:
        self.assertEqual(
            [p.nombre for p in self.cog.buscar_en_el_plantel("altria pendragon")],
            ["Altria Pendragon"],
        )

    def test_buscar_en_blanco_no_devuelve_el_plantel_entero(self) -> None:
        self.assertEqual(self.cog.buscar_en_el_plantel("  "), [])

    # --- los griales de ganar una guerra ---

    def test_una_guerra_con_bots_no_paga_griales(self) -> None:
        """El agujero obvio: abrir una guerra solo, ganarla y cobrar.

        No hace falta regla nueva: se paga por `gana_el_grial()`, que ya exige
        4 personas de verdad.
        """
        for m in self.guerra.masters.values():
            if m.id != "1":
                m.derrotas = DERROTAS_PARA_ELIMINAR
        self.assertIsNotNone(self.guerra.ganador())
        self.assertIsNone(self.guerra.gana_el_grial())
        self.assertEqual(self.cog.pagar_los_griales(self.guerra), "")
        self.assertEqual(self.cuenta.griales, 0)

    def test_ganar_una_guerra_de_gente_paga_griales(self) -> None:
        import random

        from src.commands import ComandosGuerra

        cog = ComandosGuerra(bot=None)
        cog.rng = random.Random(7)
        correr(
            cog.crear_guerra.callback(
                cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        for usuario in (2, 3, 4):
            correr(
                cog.unirse_a_guerra.callback(cog, Interaccion(usuario=usuario))
            )
        correr(cog.empezar_guerra.callback(cog, Interaccion(usuario=1)))
        guerra = cog.guerras[100]
        self.assertTrue(guerra.otorga_grial)
        for m in guerra.masters.values():
            if m.id != "1":
                m.derrotas = DERROTAS_PARA_ELIMINAR

        texto = cog.pagar_los_griales(guerra)
        self.assertIn(str(tienda.GRIALES_POR_GUERRA), texto)
        self.assertEqual(cog.cuenta_de("1").griales, tienda.GRIALES_POR_GUERRA)
        self.assertEqual(cog.cuenta_de("1").guerras_ganadas, 1)

    def test_los_griales_no_se_pagan_dos_veces_por_el_mismo_cierre(self) -> None:
        """Se pagan en `narrar_cierre`, que es el unico sitio que anuncia el
        Grial; esta prueba fija que pagar es una llamada y no un efecto de
        mirar la guerra."""
        self.assertEqual(self.cog.pagar_los_griales(self.guerra), "")
        self.assertEqual(self.cuenta.griales, 0)


@unittest.skipUnless(HAY_DISCORD, "hace falta discord.py")
class PruebaLaVistaDeLaTienda(unittest.TestCase):
    """Que el menu de la tienda ofrezca lo que se puede comprar y nada mas."""

    def setUp(self) -> None:
        import random

        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)
        self.cog.rng = random.Random(7)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
            )
        )
        correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
        correr(self.cog.invocar.callback(self.cog, Interaccion(usuario=1)))
        self.guerra = self.cog.guerras[100]
        self.master = self.guerra.masters["1"]

    def _vista(self):
        from src.commands import VistaTienda

        return VistaTienda(self.cog, self.guerra, self.master)

    def test_el_desplegable_de_oro_trae_todo_lo_que_se_vende(self) -> None:
        claves = [o.value for o in self._vista().selector_oro.options]
        self.assertEqual(sorted(claves), sorted(tienda.PRECIO_EN_ORO))

    def test_el_desplegable_de_clases_trae_las_ocho(self) -> None:
        from src.game.clases import Clase

        valores = [o.value for o in self._vista().selector_clase.options]
        self.assertEqual(sorted(valores), sorted(c.value for c in Clase))

    def test_los_desplegables_caben_en_discord(self) -> None:
        """Un desplegable aguanta 25 opciones. Por eso los Servants van aparte."""
        vista = self._vista()
        self.assertLessEqual(len(vista.selector_oro.options), 25)
        self.assertLessEqual(len(vista.selector_clase.options), 25)

    def test_comprar_desde_el_desplegable(self) -> None:
        self.master.oro = 500
        i = Interaccion(usuario=1)
        correr(self._vista().comprar_oro(i, "gema_mana"))
        self.assertTrue(self.master.inventario.tiene("gema_mana"))
        self.assertTrue(i.buzon.mensajes[-1][1], "y en privado")

    def test_comprar_una_clase_desde_el_desplegable(self) -> None:
        self.cog.cuenta_de("1").ingresar(tienda.PRECIO_CATALIZADOR_CLASE)
        i = Interaccion(usuario=1)
        correr(self._vista().comprar_clase(i, "Saber"))
        self.assertTrue(self.master.inventario.tiene("catalizador_saber"))
        self.assertTrue(i.buzon.mensajes[-1][1], "y en privado")

    def test_la_tienda_es_de_quien_la_abrio(self) -> None:
        i = Interaccion(usuario=2)
        self.assertFalse(correr_valor(self._vista().interaction_check(i)))


@unittest.skipUnless(HAY_DISCORD, "hace falta discord.py")
class PruebaUsarUnObjetoEnLaBatalla(unittest.TestCase):
    """El camino completo con una batalla de verdad en curso."""

    def setUp(self) -> None:
        import random

        from src.commands import ComandosGuerra

        for semilla in range(40):
            self.cog = ComandosGuerra(bot=None)
            self.cog.rng = random.Random(semilla)
            correr(
                self.cog.crear_guerra.callback(
                    self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
                )
            )
            correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
            correr(self.cog.invocar.callback(self.cog, Interaccion(usuario=1)))
            self.cog.guerras[100].declarar_ataque("1", "bot:1")
            correr(
                self.cog.empezar_batallas.callback(self.cog, Interaccion(usuario=1))
            )
            self.guerra = self.cog.guerras[100]
            if self.cog.combates.get(self.guerra.id) is not None:
                self.master = self.guerra.masters["1"]
                return
        self.skipTest("ninguna semilla dejo pelear a la persona")

    def test_se_ofrece_lo_de_combate_y_nada_mas(self) -> None:
        self.master.inventario.anadir("elixir")
        self.master.inventario.anadir("tomo_saber")
        claves = [
            o.clave for o, _ in self.cog.objetos_de_combate(self.guerra, self.master)
        ]
        self.assertEqual(claves, ["elixir"])

    def test_usarlo_lo_gasta_y_cuenta_el_tope(self) -> None:
        self.master.inventario.anadir("gema_mana")
        texto = self.cog.usar_objeto_en_combate(self.guerra, self.master, "gema_mana")
        self.assertTrue(texto.strip())
        self.assertFalse(self.master.inventario.tiene("gema_mana"))
        self.assertEqual(self.master.inventario.usados_en_la_batalla, 1)

    def test_el_segundo_de_la_batalla_no_entra(self) -> None:
        """Uno por batalla: con dos, un combate se decide con el inventario."""
        self.master.inventario.anadir("gema_mana")
        self.master.inventario.anadir("gema_mana")
        self.cog.usar_objeto_en_combate(self.guerra, self.master, "gema_mana")
        self.cog.usar_objeto_en_combate(self.guerra, self.master, "gema_mana")
        self.assertEqual(self.master.inventario.cuantos_de("gema_mana"), 1)
        self.assertEqual(self.cog.objetos_de_combate(self.guerra, self.master), [])

    def test_usarlo_no_decide_el_turno(self) -> None:
        self.master.inventario.anadir("gema_mana")
        combate = self.cog.combate_de(self.guerra, self.master)
        self.cog.usar_objeto_en_combate(self.guerra, self.master, "gema_mana")
        self.assertFalse(combate.ya_decidio("1"))
        self.assertIn("1", combate.pendientes)

    def test_el_detalle_queda_en_el_registro_de_quien_peleo(self) -> None:
        """Nombra el objeto, asi que no puede ir al canal."""
        self.master.inventario.anadir("gema_mana")
        self.cog.usar_objeto_en_combate(self.guerra, self.master, "gema_mana")
        nombre = objetos.objeto("gema_mana").nombre_para(self.guerra.idioma)
        self.assertTrue(any(nombre in e for e in self.master.ultimo_registro))

    def test_lo_que_se_le_cuenta_no_sale_del_privado(self) -> None:
        """El texto nombra el objeto, asi que lo devuelve y no lo publica.

        `usar_objeto_en_combate` **devuelve** el texto en vez de mandarlo a
        ningun sitio, y por eso quien lo llama puede mandarlo efimero. Si
        algun dia enviara el mensaje por su cuenta, esta prueba sobra y hay
        que releer la regla del secreto.
        """
        self.master.inventario.anadir("gema_mana")
        texto = self.cog.usar_objeto_en_combate(self.guerra, self.master, "gema_mana")
        self.assertIsInstance(texto, str)
        self.assertIn(
            objetos.objeto("gema_mana").nombre_para(self.guerra.idioma), texto
        )


@unittest.skipUnless(HAY_DISCORD, "hace falta discord.py")
class PruebaGastarUnSelloEnLaBatalla(unittest.TestCase):
    """Los Sellos por el camino de verdad: con una batalla en curso.

    El setUp es el mismo que el de los objetos, y a proposito: lo que se mide
    es que el Sello se comporte como el objeto en lo que comparten (no gasta el
    turno, no sale del privado) y distinto en lo que no (se acaba).
    """

    def setUp(self) -> None:
        import random

        from src.commands import ComandosGuerra

        for semilla in range(40):
            self.cog = ComandosGuerra(bot=None)
            self.cog.rng = random.Random(semilla)
            correr(
                self.cog.crear_guerra.callback(
                    self.cog, Interaccion(usuario=1), Eleccion("1 hora", "1h"), None
                )
            )
            correr(self.cog.empezar_guerra.callback(self.cog, Interaccion(usuario=1)))
            correr(self.cog.invocar.callback(self.cog, Interaccion(usuario=1)))
            self.cog.guerras[100].declarar_ataque("1", "bot:1")
            correr(
                self.cog.empezar_batallas.callback(self.cog, Interaccion(usuario=1))
            )
            self.guerra = self.cog.guerras[100]
            if self.cog.combates.get(self.guerra.id) is not None:
                self.master = self.guerra.masters["1"]
                return
        self.skipTest("ninguna semilla dejo pelear a la persona")

    def test_en_una_batalla_se_ofrecen_los_tres(self) -> None:
        claves = [s.clave for s in self.cog.usos_de_sello(self.guerra, self.master)]
        self.assertEqual(claves, ["mana", "curar", "enfriamientos"])

    def test_gastarlo_baja_los_dos_topes(self) -> None:
        antes = self.master.sellos
        texto = self.cog.usar_sello_en_combate(self.guerra, self.master, "mana")
        self.assertTrue(texto.strip())
        self.assertEqual(self.master.sellos, antes - 1)
        self.assertFalse(self.master.puede_usar_sello)
        self.assertEqual(self.cog.usos_de_sello(self.guerra, self.master), [])

    def test_el_segundo_de_la_batalla_no_entra(self) -> None:
        """Si entrara, los tres de la guerra se gastarian en un turno."""
        self.cog.usar_sello_en_combate(self.guerra, self.master, "mana")
        antes = self.master.sellos
        self.cog.usar_sello_en_combate(self.guerra, self.master, "curar")
        self.assertEqual(self.master.sellos, antes, "no se cobra el que no entra")

    def test_gastarlo_no_decide_el_turno(self) -> None:
        combate = self.cog.combate_de(self.guerra, self.master)
        self.cog.usar_sello_en_combate(self.guerra, self.master, "mana")
        self.assertFalse(combate.ya_decidio("1"))
        self.assertIn("1", combate.pendientes)

    def test_una_clave_inventada_no_gasta_nada(self) -> None:
        antes = self.master.sellos
        texto = self.cog.usar_sello_en_combate(self.guerra, self.master, "volar")
        self.assertTrue(texto.strip())
        self.assertEqual(self.master.sellos, antes)

    def test_sin_sellos_no_se_ofrece_ninguno(self) -> None:
        self.master.sellos = 0
        self.assertEqual(self.cog.usos_de_sello(self.guerra, self.master), [])
        antes = self.master.sellos_en_la_batalla
        self.cog.usar_sello_en_combate(self.guerra, self.master, "mana")
        self.assertEqual(self.master.sellos_en_la_batalla, antes)

    def test_el_detalle_queda_en_privado_y_en_su_registro(self) -> None:
        """Nombra lo que pasa en la batalla, asi que no puede ir al canal."""
        texto = self.cog.usar_sello_en_combate(self.guerra, self.master, "mana")
        self.assertIsInstance(texto, str)
        self.assertTrue(self.master.ultimo_registro)
        self.assertEqual(self.master.ultimo_registro_dia, self.guerra.dia)


class PruebaTerminarLaGuerra(unittest.TestCase):
    """Cerrar la guerra a mano: del comando al boton rojo y al canal."""

    def setUp(self) -> None:
        from src.commands import ComandosGuerra

        self.cog = ComandosGuerra(bot=None)

    def _crear(self, canal: int = 100) -> Interaccion:
        i = Interaccion(usuario=1, canal=canal)
        correr(
            self.cog.crear_guerra.callback(
                self.cog, i, Eleccion("1 hora", "1h"), None
            )
        )
        return i

    def _empezar(self, canal: int = 100) -> None:
        correr(
            self.cog.empezar_guerra.callback(self.cog, Interaccion(1, canal))
        )
        correr(self.cog.invocar.callback(self.cog, Interaccion(1, canal)))

    def _dia_con_batalla_de_la_persona(self) -> None:
        """Deja una batalla en curso con la persona dentro.

        Declarar un ataque **no** basta: si la cadena del rival ya llega a 4 y
        no queda nadie libre, al que no cupo le toca descansar (es la regla,
        ver `Guerra._redirigir`). Asi que se prueba semilla a semilla.
        """
        import random

        from src.commands import ComandosGuerra

        for semilla in range(40):
            self.cog = ComandosGuerra(bot=None)
            self.cog.rng = random.Random(semilla)
            self._crear()
            self._empezar()
            self.cog.guerras[100].declarar_ataque("1", "bot:1")
            correr(
                self.cog.empezar_batallas.callback(self.cog, Interaccion(usuario=1))
            )
            if self.cog.combates.get(self.cog.guerras[100].id) is not None:
                return
        self.skipTest("ninguna semilla dejo pelear a la persona")

    def _preguntar(self, usuario: int = 1) -> Interaccion:
        i = Interaccion(usuario=usuario)
        correr(self.cog.terminar.callback(self.cog, i))
        return i

    def test_sin_guerra_no_hay_nada_que_terminar(self) -> None:
        i = Interaccion(usuario=1, canal=999)
        correr(self.cog.terminar.callback(self.cog, i))
        self.assertIn("No hay ninguna guerra", i.ultimo)

    def test_solo_el_creador_puede_terminarla(self) -> None:
        self._crear()
        self._empezar()
        i = self._preguntar(usuario=2)
        self.assertIn("Solo quien abrio la guerra", i.ultimo)
        self.assertFalse(self.cog.guerras[100].terminada)

    def test_el_comando_pregunta_y_todavia_no_termina(self) -> None:
        """Entre el comando y el final hay un boton: no se cierra sin querer."""
        self._crear()
        self._empezar()
        i = self._preguntar()
        self.assertIn("Seguro?", i.ultimo)
        self.assertTrue(i.buzon.mensajes[-1][1], "la pregunta va en privado")
        self.assertIsNotNone(i.vista())
        self.assertFalse(self.cog.guerras[100].terminada)

    def test_confirmar_la_termina_sin_ganador(self) -> None:
        self._crear()
        self._empezar()
        vista = self._preguntar().vista()
        i = Interaccion(usuario=1)
        correr(vista.boton_terminar.callback(i))
        guerra = self.cog.guerras[100]
        self.assertTrue(guerra.terminada)
        self.assertTrue(guerra.cancelada)
        self.assertIsNone(guerra.ganador())
        self.assertIsNone(guerra.gana_el_grial())

    def test_el_final_se_cuenta_en_el_canal(self) -> None:
        """La guerra es de todos: el creador no la cierra a escondidas."""
        self._crear()
        self._empezar()
        vista = self._preguntar().vista()
        i = Interaccion(usuario=1)
        correr(vista.boton_terminar.callback(i))
        publicos = [m[0] for m in i.buzon.mensajes if not m[1]]
        self.assertTrue(publicos)
        self.assertIn("Nadie se lleva el Grial", publicos[-1])

    def test_el_aviso_del_canal_no_delata_ningun_servant(self) -> None:
        """La regla del secreto sigue valiendo aunque la guerra se acabe."""
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        nombres = [m.servant.nombre for m in guerra.masters.values() if m.servant]
        aviso = self.cog.aviso_del_final(guerra)
        for nombre in nombres:
            self.assertNotIn(nombre, aviso)

    def test_mejor_no_la_deja_viva(self) -> None:
        self._crear()
        self._empezar()
        vista = self._preguntar().vista()
        i = Interaccion(usuario=1)
        correr(vista.boton_cancelar.callback(i))
        self.assertIn("La guerra sigue", i.ultimo)
        self.assertFalse(self.cog.guerras[100].terminada)

    def test_el_boton_es_del_creador(self) -> None:
        self._crear()
        self._empezar()
        vista = self._preguntar().vista()
        i = Interaccion(usuario=2)
        self.assertFalse(correr_valor(vista.interaction_check(i)))
        self.assertIn("Solo quien abrio la guerra", i.ultimo)

    def test_terminar_borra_la_batalla_en_curso(self) -> None:
        """La batalla vive en el Cog, no en la guerra: hay que limpiarla.

        Si se quedara ahi, el vigilante seguiria intentando avanzar una
        batalla de una guerra que ya no existe.
        """
        self._dia_con_batalla_de_la_persona()
        guerra = self.cog.guerras[100]
        self.assertIsNotNone(self.cog.combates.get(guerra.id))
        self.assertIsNone(self.cog.terminar_guerra(guerra))
        self.assertIsNone(self.cog.combates.get(guerra.id))

    def test_una_guerra_ya_acabada_no_se_termina_dos_veces(self) -> None:
        self._crear()
        self._empezar()
        guerra = self.cog.guerras[100]
        self.assertIsNone(self.cog.terminar_guerra(guerra))
        self.assertIn("ya se acabo", self.cog.terminar_guerra(guerra))
        i = self._preguntar()
        self.assertIn("ya se acabo", i.ultimo)

    def test_el_vigilante_deja_en_paz_una_guerra_terminada(self) -> None:
        """Las tres puertas del vigilante tienen que quedar cerradas.

        Una guerra cancelada sigue en memoria, asi que no basta con cortarla:
        si alguna de las tres listas la recogiera, el vigilante le cerraria
        dias o le avanzaria batallas a una guerra que ya no se juega.
        """
        self._dia_con_batalla_de_la_persona()
        guerra = self.cog.guerras[100]
        self.cog.terminar_guerra(guerra)
        v = self.cog.vigilante
        self.assertNotIn(guerra, v.vencidas())
        self.assertNotIn(guerra, v.combates_estancados())
        self.assertNotIn(guerra, v.atascadas())

    def test_despues_de_terminarla_el_canal_queda_libre(self) -> None:
        """Lo que hace util cancelar: poder abrir otra ahi mismo."""
        self._crear()
        self._empezar()
        self.cog.terminar_guerra(self.cog.guerras[100])
        i = self._crear()
        self.assertIn("guerra", i.ultimo.lower())
        self.assertFalse(self.cog.guerras[100].terminada)


if __name__ == "__main__":
    unittest.main()
