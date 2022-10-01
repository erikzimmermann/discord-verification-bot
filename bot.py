import os

import nextcord
from nextcord.ext import commands

from core import files, log
from core.service import services

config = files.Config()
config_discord = config.discord()

intents = nextcord.Intents.default()
intents.members = True

bot = commands.Bot(activity=config_discord.get_activity(), intents=intents)
services = services.Holder(bot, config)


def load_extensions():
    for fn in os.listdir("./cogs"):
        if fn.endswith(".py"):
            log.info(f"Loading extension: {fn}")
            bot.load_extension(f"cogs.{fn[:-3]}", extras={
                "config": config,
                "services": services
            })


def start():
    log.load_logging_handlers()
    load_extensions()

    log.info("Starting bot...")
    bot.run(config_discord.token())


@bot.event
async def on_ready():
    await services.enable_all()
    print("Bot is ready! - @Pterodactyl")


start()
