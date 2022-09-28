import random
from datetime import datetime
from typing import Tuple, Union

import nextcord
from nextcord import SlashOption
from nextcord.ext import tasks
from nextcord.ext.commands import Cog, Bot

from core import database, files, mail, paypalapi, log, discord_utils, ui, magic


class Promote(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.config = files.Config()

        self.db = database.Database(self.config)
        self.mail_service = mail.MailService(self.config.email_service())

        self.paypal = paypalapi.ApiReader(
            self.db,
            self.config.paypal().client_id(),
            self.config.paypal().secret()
        )

        self.sent_codes = {}
        self.sent_messages = {}

        self.discord = discord_utils.Discord(bot, self.config.discord())

        self.email_html = files.read_file("email.html")
        self.email_plain = files.read_file("email.plain")
        if not self.email_html:
            log.error("Cannot find a valid 'email.html' file in the root directory. Please check!")
        if not self.email_plain:
            log.error("Cannot find a valid 'email.plain' file in the root directory. Please check!")

    def all_services_ready(self):
        return self.db.has_valid_con() \
               and self.paypal.access_token is not None \
               and self.mail_service.has_valid_credentials() \
               and self.discord.is_ready() \
               and self.email_html and self.email_plain

    @Cog.listener()
    async def on_ready(self):
        # Start DB connection first
        await self.db.build_connection()
        if not self.db.has_valid_con():
            return

        self.paypal.fetch_access_token()
        # Access DB for last fetch and update transaction data
        self.paypal.update_transaction_data()

        # fetch all necessary roles etc.
        await self.discord.fetch()
        self.start_role_updater.start()

        if self.all_services_ready():
            log.info("All services have been started successfully.")
        else:
            log.warning("Some services are not available. Check your logs.")

    @Cog.listener()
    async def on_interaction(self, interaction: nextcord.Interaction):
        custom_id = interaction.data.get("custom_id")
        if custom_id == "promotion_start":
            if not self.all_services_ready():
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

    @tasks.loop(minutes=5)
    async def start_role_updater(self):
        if not self.all_services_ready():
            return

        self.paypal.update_transaction_data(silent=True)
        async for member in self.discord.get_all_members():
            if member.bot:
                continue

            comparison = discord_utils.compare_rank(member, await self.discord.get_bot_member())
            if comparison > 0:
                await self.update_member(member)

    @nextcord.slash_command(
        name="unlink",
        description="Unlinks a Discord account from a SpigotMC account and removes their premium roles.",
        default_member_permissions=nextcord.Permissions(administrator=True),
        dm_permission=False
    )
    async def unlink(
            self, it: nextcord.interactions.Interaction,
            discord_id: str = SlashOption(
                description="The Discord user ID which should be unlinked.",
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

        if not self.db.is_user_linked(target.id):
            await it.response.send_message(
                content=f"This Discord user is not linked to a SpigotMC account. 😕",
                ephemeral=True
            )
            return

        log.info(f"The Discord user '{user}' has initiated the link removal of '{target}'.")

        self.db.invalidate_link(target.id)
        await self.update_member(target)

        await it.response.send_message(
            content=f"The verification of '{target}' has been removed. 👀",
            ephemeral=True
        )

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

    @nextcord.slash_command(
        name="promotion_message",
        description="Posts the promotion message including 'start' button.",
        default_member_permissions=nextcord.Permissions(administrator=True),
        dm_permission=False
    )
    async def promotion_message(self, it: nextcord.interactions.Interaction):
        if not isinstance(it.channel, nextcord.abc.Messageable):
            await it.send(f"This channel has an invalid type: {type(it.channel)}.", ephemeral=True)
            return

        await it.send(f"Done.", ephemeral=True)

        channel: nextcord.abc.Messageable = it.channel

        embed = nextcord.Embed(
            color=magic.COLOR_PREMIUM,
            title=self.config.discord().promotion_start_title(),
            description=self.config.discord().promotion_start_content()
        )

        await channel.send(embed=embed, view=ui.StartPromotionButton())

    async def send_promotion_key(self, it: nextcord.Interaction, spigot_name: str):
        user: nextcord.Member = it.user

        if self.db.is_user_linked(user.id):
            if await self.update_member(user):
                await it.response.send_message(
                    content=f"Your Discord roles have been updated. 😏", ephemeral=True)
            else:
                await it.response.send_message(
                    content=f"Your Discord account is already linked to a SpigotMC account. 🥸", ephemeral=True)
            return

        if self.db.is_spigot_name_linked(spigot_name):
            await it.response.send_message(
                content=f"This SpigotMC account is already linked to a Discord account. 😕", ephemeral=True)
            return

        self.paypal.update_transaction_data()  # update transactions before trying to find a match
        email = self.db.get_email(spigot_name)

        if email is not None:
            promotion_key = self.generate_promotion_key(user, spigot_name)

            email_content_html, email_content_plain = self.format_email(f"{user.name}#{user.discriminator}",
                                                                        spigot_name,
                                                                        str(promotion_key))
            self.mail_service.send_email(
                self.config.email_service().subject(),
                self.config.email_service().sender_name(),
                email, email,
                email_content_html,
                email_content_plain
            )

            log.info(f"Starting promotion process for {user}.")

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

        if self.db.is_spigot_name_linked(encoded_spigot_name, do_hash=False):
            await self.update_interaction(
                user,
                content=f"Someone else has linked another Discord account to this SpigotMC name in the meantime. 😕"
            )
            return

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

    async def verify_code(self, user: nextcord.Member,
                          code_input: int) -> None:
        key, encoded_spigot_name, valid = self.get_cached_promotion_key(user)

        if self.db.is_spigot_name_linked(encoded_spigot_name, do_hash=False):
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
            self.db.link_user(user.id, encoded_spigot_name)
            await self.update_member(user)
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

    async def update_user(self, user_id: int) -> None:
        await self.update_member(await self.discord.get_member(user_id))

    async def update_member(self, member: nextcord.Member) -> bool:
        rids = self.db.get_bought_rids(member.id)
        updated = False

        if len(rids) > 0:
            if self.discord.premium_role not in member.roles:
                log.info(f"Adding premium role to '{member}' ({member.id}) due to {len(rids)} verified purchase(s).")
                await member.add_roles(
                    self.discord.premium_role,
                    reason=f"Role added by {len(rids)} verified purchase(s)."
                )
                updated = True
        else:
            if self.discord.premium_role in member.roles:
                log.info(f"Removing premium role from '{member}' ({member.id}) due to 0 verified purchases.")
                await member.remove_roles(
                    self.discord.premium_role,
                    reason=f"Role removed due to 0 verified purchases."
                )
                updated = True

        for role in member.roles:
            rid = self.config.discord().rid_by_role(role.id)
            if rid is not None and rid not in rids:
                # illegal role access
                log.info(f"Removing role '{role.name}' from '{member}' ({member.id}) "
                         f"due to insufficient purchase access ({rid}).")
                await member.remove_roles(role, reason=f"Role removed due to insufficient purchase access ({rid}).")
                updated = True

        for rid in rids:
            role = self.discord.get_role(rid)
            if role not in member.roles:
                log.info(f"Adding role '{role.name}' to '{member}' ({member.id}) due to a verified purchase ({rid}).")
                await member.add_roles(role, reason=f"Role added by verified purchase ({rid}).")
                updated = True

        return updated

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

    def format_email(self, discord_user: str, spigot_user: str, promotion_key: str) -> (str, str):
        html = self.email_html.format(
            discord_user=discord_user,
            spigot_user=spigot_user,
            promotion_key=promotion_key
        )
        plain = self.email_plain.format(
            discord_user=discord_user,
            spigot_user=spigot_user,
            promotion_key=promotion_key
        )
        return html, plain


def setup(bot: Bot):
    bot.add_cog(Promote(bot))
