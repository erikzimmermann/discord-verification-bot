import random
from datetime import datetime
from typing import Tuple, Union

import nextcord
from nextcord import SlashOption
from nextcord.ext import tasks
from nextcord.ext.commands import Cog, Bot

from core import files, log, ui, magic
from core.service import services


class Promote(Cog):
    def __init__(self, bot: Bot, **kwargs):
        self.bot = bot
        self.config: files.Config = kwargs["config"]
        self.services: services.Holder = kwargs["services"]

        self.database = self.services.database
        self.mail_service = self.services.mail
        self.paypal = self.services.paypal
        self.discord = self.services.discord

        self.sent_codes = {}
        self.sent_messages = {}
        self.reserved = []

    @Cog.listener()
    async def on_ready(self):
        self.check_inbox.start()

    @tasks.loop(seconds=5)
    async def check_inbox(self):
        if not self.services.all_services_ready():
            return

        to_be_removed = []
        inbox = self.mail_service.got_received_promotion_keys()
        for user_id in self.sent_codes.keys():
            data = self.sent_codes[user_id]
            started, key, encoded_spigot_name = data

            match = inbox.get(encoded_spigot_name)
            if match is not None:
                message, date = match

                if date <= started:
                    continue

                user = await self.discord.fetch_member(user_id)
                if str(key) in message:
                    log.info(f"Promotion process for {user} has been completed.")
                    await self.promote(user, encoded_spigot_name)
                else:
                    log.info(f"Promotion process for {user} failed.")
                    await self.update_interaction(
                        user,
                        content=f"This promotion key is **not correct**. Please restart your promotion."
                    )

                to_be_removed.append(user_id)
                self.reserved.remove(encoded_spigot_name)

        for remove in to_be_removed:
            self.sent_codes.pop(remove)

    @nextcord.slash_command(
        name="invalidate_ongoing_promotion",
        description="Invalidates the currently ongoing promotion process of a Discord user.",
        default_member_permissions=nextcord.Permissions(administrator=True),
        dm_permission=False
    )
    async def invalidate_ongoing_promotion(
            self, it: nextcord.interactions.Interaction,
            discord_id: str = SlashOption(
                description="The Discord user ID of the ongoing promotions process that should be invalidated.",
                required=True,
                min_length=18,
                max_length=18
            )
    ):
        user: nextcord.Member = it.user

        target = await self.discord.fetch_member(int(discord_id))

        if target is None:
            await it.response.send_message(
                content=f"This Discord user does not exist. 😕",
                ephemeral=True
            )
            return

        log.info(f"The Discord user '{user}' has invalidated the ongoing promotion process of '{target}'.")
        _, encoded_spigot_name = self.get_cached_promotion_key(target)

        if encoded_spigot_name is None:
            await it.response.send_message(
                content=f"This Discord user has no ongoing promotion process. 😕",
                ephemeral=True
            )
            return

        self.reserved.remove(encoded_spigot_name)

        await self.update_interaction(target, content="Your promotion has been cancelled.")
        await it.response.send_message(
            content=f"The promotion process of '{target}' has been invalidated.",
            ephemeral=True
        )

    @Cog.listener()
    async def on_interaction(self, interaction: nextcord.Interaction):
        custom_id = interaction.data.get("custom_id")
        if custom_id == "promotion_start":
            if not self.services.all_services_ready():
                await interaction.response.send_message(
                    embed=nextcord.Embed(
                        color=magic.COLOR_WARNING,
                        title="❌ Account Promotion",
                        description="The promotion process cannot be executed at the moment. Please try again later."
                    ),
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(ui.SpigotNameInput(self.send_promotion_key))

    async def send_promotion_key(self, it: nextcord.Interaction, spigot_name: str):
        user: nextcord.Member = it.user

        old_promotion_key, old_encoded_spigot_name = self.get_cached_promotion_key(user, False)
        if old_encoded_spigot_name is not None and old_encoded_spigot_name in self.reserved:
            self.reserved.remove(old_encoded_spigot_name)
            log.info(f"Promotion process for {user} cancelled.")
            await self.update_interaction(user, content="This verification process has been cancelled.")

        encoded_spigot_name = magic.encode(spigot_name)
        if encoded_spigot_name in self.reserved:
            await it.response.send_message(
                content=f"This SpigotMC account is already linked to a Discord account. 😕", ephemeral=True)
            return

        if self.database.is_user_linked(user.id):
            if await self.discord.update_member(user):
                await it.response.send_message(
                    content=f"Your Discord roles have been updated. 😏", ephemeral=True)
            else:
                await it.response.send_message(
                    content=f"Your Discord account is already linked to a SpigotMC account. 🥸", ephemeral=True)
            return

        if self.database.is_spigot_name_linked(spigot_name):
            await it.response.send_message(
                content=f"This SpigotMC account is already linked to a Discord account. 😕", ephemeral=True)
            return

        # update transactions before trying to find a match
        self.paypal.update_transaction_data()

        if self.database.is_premium_user(spigot_name):
            log.info(f"Starting promotion process for {user}.")

            promotion_key = self.generate_promotion_key(user, spigot_name)
            self.reserved.append(encoded_spigot_name)

            spigot_config = self.config.spigotmc()

            pim: nextcord.PartialInteractionMessage = await it.response.send_message(
                content=f"Please verify the promotion key by sending it to us in a conversation on "
                        f"SpigotMc.\n"
                        f"\n"
                        f"1. Copy the key: `{promotion_key}`\n"
                        f"2. Click the button below to create a conversation\n"
                        f"3. Paste the code in the text area and submit",
                view=ui.PromotionKeyInputButton(spigot_config.recipient(), spigot_config.topic()),
                ephemeral=True
            )
            self.sent_messages[user.id] = pim
        else:
            log.info(f"Failed transaction id lookup for {user}.")
            await it.response.send_message(
                content=f"We could not find any purchase linked to your account. 😕",
                ephemeral=True
            )

    async def promote(self, user: nextcord.Member, encoded_spigot_name: str) -> None:
        self.database.link_user(user.id, encoded_spigot_name)
        await self.discord.update_member(user)
        await self.update_interaction(
            user,
            content=self.config.discord().promotion_message().format(user=user.mention)
        )

    async def update_interaction(self, user: nextcord.Member, invalidate: bool = True, content: str = None,
                                 view: nextcord.ui.View = None) -> None:
        plm: nextcord.PartialInteractionMessage = self.sent_messages.get(user.id)
        if plm:
            await plm.edit(content=content, view=view)

        if invalidate:
            self.sent_messages.pop(user.id)

    def generate_promotion_key(self, user: nextcord.Member, spigot_name: str) -> int:
        started_at = datetime.now()
        key = random.randint(100000, 999999)
        encoded_spigot_name = magic.encode(spigot_name)
        self.sent_codes[user.id] = (started_at, key, encoded_spigot_name)
        return key

    def get_cached_promotion_key(
            self,
            user: nextcord.Member,
            invalidate: bool = True
    ) -> Union[Tuple[int, str] | Tuple[None, None]]:
        cache: Tuple[datetime, int, str] = self.sent_codes.get(user.id)

        if cache is None:
            # no key found
            return None, None

        started_at, key, encoded_spigot_name = cache

        if invalidate:
            self.sent_codes.pop(user.id)

        return key, encoded_spigot_name


def setup(bot: Bot, **kwargs):
    bot.add_cog(Promote(bot, **kwargs))
