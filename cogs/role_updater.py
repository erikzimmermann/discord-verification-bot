from nextcord.ext import tasks
from nextcord.ext.commands import Cog, Bot

from core import files
from core.service import services


class Scheduler(Cog):
    def __init__(self, bot: Bot, **kwargs):
        self.bot = bot
        self.config: files.Config = kwargs["config"]
        self.services: services.Holder = kwargs["services"]

        self.paypal = self.services.paypal
        self.discord = self.services.discord

    @Cog.listener()
    async def on_ready(self):
        self.start_role_updater.start()

    @tasks.loop(minutes=5)
    async def start_role_updater(self):
        if not self.services.all_services_ready():
            return

        self.paypal.update_transaction_data(silent=True)
        self.discord.get_all_members(self.discord.update_member)


def setup(bot: Bot, **kwargs):
    bot.add_cog(Scheduler(bot, **kwargs))