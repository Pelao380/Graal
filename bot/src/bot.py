"""Punto de entrada del bot.

Se ejecuta con:  python -m src.bot    (desde la carpeta bot/)

Necesita un archivo .env junto a este proyecto con:
    DISCORD_TOKEN=el_token_de_tu_bot
    GUILD_ID=id_de_tu_servidor_de_pruebas   (opcional, pero muy recomendable)

Sin GUILD_ID los comandos se registran globalmente y Discord puede tardar
hasta una hora en mostrarlos. Con GUILD_ID aparecen al instante en ese
servidor, que es lo que se quiere para probar.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from . import db, repositorio

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("graal")


class Graal(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        # El Message Content Intent solo hace falta si se usan comandos de
        # texto. Con comandos de barra no es necesario.
        super().__init__(command_prefix="!graal ", intents=intents)
        self.conexion = None

    async def setup_hook(self) -> None:
        self.conexion = db.conectar()
        repositorio.migrar(self.conexion)
        log.info("Base de datos lista")

        from .commands import ComandosGuerra, Traductor

        # El traductor tiene que estar puesto antes de sincronizar: es al
        # sincronizar cuando discord.py le pide los nombres y las ayudas en
        # cada idioma.
        await self.tree.set_translator(Traductor())
        # El Cog lee las guerras que quedaron a medias al cargarse, y el
        # vigilante cierra los dias que vencieron mientras el bot estaba
        # apagado en su primera revision.
        await self.add_cog(ComandosGuerra(self, conexion=self.conexion))

        # Con un servidor de pruebas los comandos aparecen al instante. El
        # registro global tarda hasta una hora, que para probar no sirve.
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            servidor = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=servidor)
            await self.tree.sync(guild=servidor)
            log.info("Comandos sincronizados en el servidor %s", guild_id)
        else:
            await self.tree.sync()
            log.info(
                "Comandos sincronizados globalmente: pueden tardar hasta una "
                "hora en aparecer. Pon GUILD_ID en .env para verlos ya."
            )

    async def on_ready(self) -> None:
        log.info("Conectado como %s", self.user)


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit(
            "Falta DISCORD_TOKEN. Copia .env.example a .env y pon el token "
            "de tu bot ahi. El token nunca va en el codigo."
        )
    asyncio.run(Graal().start(token))


if __name__ == "__main__":
    main()
