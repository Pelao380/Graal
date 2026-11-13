"""Comprueba el bot sin conectarse a Discord.

Uso, desde la carpeta bot/ y con el entorno instalado:

    .\\.venv\\Scripts\\python.exe tools/comprobar_bot.py

Hace tres cosas: revisa el .env, carga el Cog de verdad y registra los
comandos de barra en el arbol, que es donde discord.py valida nombres,
descripciones y opciones. Si esto pasa, el bot arranca. No se conecta a
Discord ni hace falta internet.

Del token solo dice si tiene la forma correcta: no lo imprime nunca.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import discord  # noqa: E402
from discord.ext import commands  # noqa: E402
from dotenv import dotenv_values  # noqa: E402

PLACEHOLDER = "pon_aqui_el_token_de_tu_bot"


def revisar_env() -> bool:
    """Mira el .env y dice que falta, sin ensenar el token."""
    ruta = RAIZ / ".env"
    bien = True

    # La trampa clasica de Windows: el Bloc de notas guarda ".env.txt".
    sobrantes = [p.name for p in RAIZ.glob(".env.*") if p.name != ".env.example"]
    if sobrantes:
        print(f"  ojo: hay {', '.join(sobrantes)}. El bot solo lee '.env'.")
        bien = False

    if not ruta.exists():
        print("  falta bot/.env. Copia .env.example a .env y pon el token.")
        return False

    valores = dotenv_values(ruta)
    token = (valores.get("DISCORD_TOKEN") or "").strip()
    if not token or token == PLACEHOLDER:
        print("  .env esta, pero DISCORD_TOKEN sigue vacio o con el ejemplo.")
        bien = False
    elif token.count(".") != 2 or len(token) < 50:
        print(
            f"  DISCORD_TOKEN no tiene forma de token ({len(token)} caracteres, "
            f"{token.count('.') + 1} partes). Un token son 3 partes separadas "
            f"por puntos. Cuidado con copiar el Application ID o con dejar "
            f"comillas o espacios."
        )
        bien = False
    else:
        print(f"  DISCORD_TOKEN: {len(token)} caracteres, forma correcta.")

    guild = (valores.get("GUILD_ID") or "").strip()
    if not guild:
        print(
            "  GUILD_ID vacio: los comandos se registraran globalmente y "
            "Discord puede tardar hasta una hora en mostrarlos."
        )
    elif not guild.isdigit():
        print(f"  GUILD_ID no es un numero: '{guild}'. Va el ID, sin comillas.")
        bien = False
    else:
        print(f"  GUILD_ID: {guild}")
    return bien


async def main() -> None:
    print("Revisando bot/.env:")
    env_bien = revisar_env()

    from src.commands import CATALOGO, ComandosGuerra
    from src.game.textos import IDIOMAS, TEXTOS

    print(f"personajes cargados: {len(CATALOGO)}")
    print(f"textos: {len(TEXTOS)} claves en {', '.join(IDIOMAS)}")

    bot = commands.Bot(command_prefix="!graal ", intents=discord.Intents.default())
    await bot.add_cog(ComandosGuerra(bot))
    print("Cog cargado. Comandos de barra registrados:")
    for comando in sorted(bot.tree.walk_commands(), key=lambda c: c.qualified_name):
        if isinstance(comando, discord.app_commands.Group):
            continue
        # display_name es el que ve el jugador; name es el de Python.
        opciones = ", ".join(p.display_name for p in comando.parameters)
        print(
            f"  /{comando.qualified_name}"
            + (f" ({opciones})" if opciones else "")
            + f" - {comando.description}"
        )
        for parametro in comando.parameters:
            if parametro.choices:
                etiquetas = " | ".join(c.name for c in parametro.choices)
                print(f"      {parametro.display_name}: {etiquetas}")
    print("Como se ven los comandos en cada idioma de Discord:")
    for clave, frases in TEXTOS.items():
        if clave.startswith("cmd.") and clave.endswith(".nombre"):
            ayuda = TEXTOS.get(clave.replace(".nombre", ".ayuda"), {})
            for idioma in IDIOMAS:
                print(f"  [{idioma}] /{frases[idioma]:<16} {ayuda.get(idioma, '')}")

    if env_bien:
        print("Todo listo: arranca con  python -m src.bot")
    else:
        print("El codigo esta bien; arregla lo del .env de arriba y arranca.")


if __name__ == "__main__":
    asyncio.run(main())
