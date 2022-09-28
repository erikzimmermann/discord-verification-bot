import os

import nextcord
from nextcord.ext import commands

from core import files, log

config = files.Config().discord()
activity = None if config.activity_type() == -1 else nextcord.Activity(type=config.activity_type(),
                                                                       name=config.activity())

intents = nextcord.Intents.default()
intents.members = True

bot = commands.Bot(activity=activity, intents=intents)


def load_extensions():
    for fn in os.listdir("./cogs"):
        if fn.endswith(".py"):
            log.info(f"Loading extension: {fn}")
            bot.load_extension(f"cogs.{fn[:-3]}")


def start():
    log.load_logging_handlers()
    load_extensions()

    log.info("Starting bot...")
    bot.run(config.token())


@bot.event
async def on_ready():
    print("Bot is ready! - @Pterodactyl")


start()
