import random
from datetime import datetime
from typing import Tuple, Union

import nextcord
from nextcord import SlashOption
from nextcord.ext.commands import Cog, Bot

from core import files, log, ui, magic
from core.service import database, services


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

        target = await self.discord.get_member(int(discord_id))

        if target is None:
            await it.response.send_message(
                content=f"This Discord user does not exist. 😕",
                ephemeral=True
            )
            return

        if self.sent_codes.get(target.id) is None:
            await it.response.send_message(
                content=f"This Discord user has no ongoing promotion process. 😕",
                ephemeral=True
            )
            return

        log.info(f"The Discord user '{user}' has invalidated the ongoing promotion process of '{target}'.")
        self.sent_codes.pop(target.id)

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

            code, _, valid = self.get_cached_promotion_key(interaction.user, False)
            if valid:
                if code is None:
                    await interaction.response.send_message(
                        content=f"You can only request one promotion key **every "
                                f"{self.config.discord().code_expiration_text()}**. 📬",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        content=f"An email was already sent. Please check your inbox. 📬", ephemeral=True)
            else:
                await interaction.response.send_modal(ui.SpigotNameInput(self.send_promotion_key))

    async def send_promotion_key(self, it: nextcord.Interaction, spigot_name: str):
        user: nextcord.Member = it.user

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
        self.paypal.update_transaction_data(fetch_buffer=magic.PAYPAL_UPDATE_DELAY)
        email = self.database.get_email(spigot_name)

        if email is not None:
            log.info(f"Starting promotion process for {user}.")

            promotion_key = self.generate_promotion_key(user, spigot_name)
            self.mail_service.send_formatted_mail(user, email, spigot_name, promotion_key)

            self.sent_messages[user.id] = await it.response.send_message(
                content="We have sent an email to the address that was used to buy one of our plugins. 📬\n\n"
                        "*Use the button below to verify your received promotion key.*",
                view=ui.PromotionKeyInputButton(self.code_validation_check, self.verify_code),
                ephemeral=True
            )
            # -> ui: key input -> code_validation_check -> verify_code
        else:
            log.info(f"Failed email lookup for {user}.")
            await it.response.send_message(
                content=f"We could not find any purchase linked to your account. 😕",
                ephemeral=True
            )

    async def code_validation_check(self, user: nextcord.Member) -> bool:
        key, encoded_spigot_name, valid = self.get_cached_promotion_key(user, invalidate=False)

        if self.database.is_spigot_name_linked(encoded_spigot_name, do_hash=False):
            await self.update_interaction(
                user,
                content=f"Someone else has linked another Discord account to this SpigotMC name in the meantime. 😕"
            )
            return False

        if key is None:
            await self.update_interaction(
                user,
                content="Please click the *Start Promotion* button to start your promotion."
            )
            return False

        if not valid:
            await self.update_interaction(
                user,
                content=f"Your promotion key is **older than {self.config.discord().code_expiration_text()}**. ⏰\n"
                        f"Please restart your promotion."
            )
            return False

        return True

    async def verify_code(self, user: nextcord.Member, code_input: int) -> None:
        key, encoded_spigot_name, valid = self.get_cached_promotion_key(user)

        if self.database.is_spigot_name_linked(encoded_spigot_name, do_hash=False):
            await self.update_interaction(
                user,
                content=f"Someone else has linked another Discord account to this SpigotMC name in the meantime. 😕"
            )
            return

        # check validation before key since the dialogue for giving the bot the 6-digit code is already open
        if encoded_spigot_name is not None and not valid:
            await self.update_interaction(
                user,
                content=f"Your promotion key is **older than {self.config.discord().code_expiration_text()}**. ⏰\n"
                        f"Please restart your promotion."
            )
            return

        # only True if an admin invalidates the process while the user enters the key
        if key is None or encoded_spigot_name is None:
            await self.update_interaction(
                user,
                content="Your promotion has been cancelled. Please try again."
            )
            return

        if key == code_input:
            self.database.link_user(user.id, encoded_spigot_name)
            await self.discord.update_member(user)
            log.info(f"Promotion process for {user} has been completed.")

            await self.update_interaction(
                user,
                content=self.config.discord().promotion_message().format(user=user.mention)
            )
        else:
            log.info(f"Promotion process for {user} failed.")

            await self.update_interaction(
                user,
                content=f"This promotion key is **not correct**. Please restart your promotion."
            )

    async def update_interaction(self, user: nextcord.Member, invalidate: bool = True, content: str = None,
                                 view: nextcord.ui.View = None) -> None:
        plm: nextcord.PartialInteractionMessage = self.sent_messages.get(user.id)
        if plm:
            await plm.edit(content=content, view=view)

        if invalidate:
            self.sent_messages.pop(user.id)

    def generate_promotion_key(self, user: nextcord.Member, spigot_name: str) -> int:
        started_at = int(datetime.now().timestamp())
        key = random.randint(100000, 999999)
        encoded_spigot_name = database.encode(spigot_name)
        self.sent_codes[user.id] = (started_at, key, encoded_spigot_name)
        return key

    def get_cached_promotion_key(
            self,
            user: nextcord.Member,
            invalidate: bool = True
    ) -> Union[Tuple[int, str, bool] | Tuple[None, str, bool] | Tuple[None, None, None]]:
        cache: Tuple[int, int, str] = self.sent_codes.get(user.id)

        if cache is None:
            # no key found
            return None, None, None

        started_at, key, encoded_spigot_name = cache

        time = int(datetime.now().timestamp())
        valid = time - started_at <= self.config.discord().code_expiration()

        if not valid:
            # not valid anymore; invalidate timeout
            self.sent_codes.pop(user.id)
        elif invalidate and key is not None:
            # invalidate key but not timeout
            self.sent_codes[user.id] = (started_at, None, encoded_spigot_name)

        return key, encoded_spigot_name, valid


def setup(bot: Bot, **kwargs):
    bot.add_cog(Promote(bot, **kwargs))
