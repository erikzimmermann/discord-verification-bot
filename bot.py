import os
from typing import Optional

import nextcord
from nextcord.ext import commands

from core import files, log
from core.service import services

config = files.Config()
config_discord = config.discord()

intents = nextcord.Intents.default()
intents.members = True

bot = commands.Bot(activity=config_discord.get_activity(), intents=intents)
service_holder: Optional[services.Holder] = None


def load_extensions():
    for fn in os.listdir("./cogs"):
        if fn.endswith(".py"):
            log.info(f"Loading extension: {fn}")
            bot.load_extension(f"cogs.{fn[:-3]}", extras={
                "config": config,
                "services": service_holder
            })


def start():
    global service_holder
    log.load_logging_handlers()

    log.info("Loading services...")
    service_holder = services.Holder(bot, config)
    log.info("Loading extensions...")
    load_extensions()

    log.info("Starting bot...")
    bot.run(config_discord.token())


@bot.event
async def on_ready():
    await service_holder.enable_all()
    print("Bot is ready! - @Pterodactyl")


start()
