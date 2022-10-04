from datetime import datetime

from nextcord.ext.commands import Bot

from core import files, log
from core.service import paypal, discord_utils, database, mail


class Holder:
    def __init__(self, bot: Bot, config: files.Config):
        self.bot = bot
        self.config = config

        self.database = database.MySQL(config)
        self.discord = discord_utils.Discord(bot, config.discord(), self.database)
        self.mail = mail.MailService(config.email_service())
        self.paypal = paypal.ApiReader(
            self.database,
            config.paypal().client_id(),
            config.paypal().secret()
        )

    def all_services_ready(self):
        return self.database.has_valid_con() \
               and self.paypal.access_token is not None \
               and self.mail.is_ready() \
               and self.discord.is_ready()

    async def enable_all(self):
        log.info("Enabling services...")
        # Start DB connection first
        self.database.build_connection()
        if not self.database.has_valid_con():
            return

        self.paypal.fetch_access_token()
        # Access DB for last fetch and update transaction data
        self.paypal.update_transaction_data()

        # fetch all necessary roles etc.
        await self.discord.fetch()

        if self.all_services_ready():
            log.info("All services have been started successfully.")
        else:
            log.warning("Some services are not available. Check your logs.")
