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
            started, key, spigot_name = data

            match = inbox.get(spigot_name.lower())
            if match is not None:
                message, date = match

                if date <= started:
                    continue

                user = await self.discord.fetch_member(user_id)
                if str(key) in message:
                    log.info(f"Promotion process for {user} has been completed.")
                    await self.promote(user, spigot_name)
                else:
                    log.info(f"Promotion process for {user} failed.")
                    await self.update_interaction(
                        user,
                        content=f"This promotion key is **not correct**. Please restart your promotion."
                    )

                to_be_removed.append(user_id)
                self.reserved.remove(spigot_name)

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
        _, spigot_name = self.get_cached_promotion_key(target)

        if spigot_name is None:
            await it.response.send_message(
                content=f"This Discord user has no ongoing promotion process. 😕",
                ephemeral=True
            )
            return

        self.reserved.remove(spigot_name)

        await self.update_interaction(target, content="Your promotion has been cancelled.")
        await it.response.send_message(
            content=f"The promotion process of '{target}' has been invalidated.",
            ephemeral=True
        )

    @Cog.listener()
    async def on_interaction(self, it: nextcord.Interaction):
        custom_id = str(it.data.get("custom_id"))
        if custom_id is None:
            return

        if custom_id == "promotion_start":
            await self.start_promotion(it)
        elif custom_id == "no_conversation_access":
            await self.no_conversation_access(it)
        elif custom_id == "no_open_conversation":
            await self.no_open_conversation(it)
        elif custom_id.startswith("conversation_created:"):
            await it.response.defer()

            user_id: str = custom_id[21:]

            if user_id.isnumeric():
                await self.conversation_created(it, int(user_id))

    async def start_promotion(self, it: nextcord.Interaction) -> None:
        if not self.services.all_services_ready():
            await it.response.send_message(
                embed=nextcord.Embed(
                    color=magic.COLOR_WARNING,
                    title="❌ Account Promotion",
                    description="The promotion process cannot be executed at the moment. Please try again later."
                ),
                ephemeral=True
            )
            return

        await it.response.send_modal(ui.SpigotNameInput(self.send_promotion_key))

    async def no_conversation_access(self, it: nextcord.Interaction) -> None:
        key, _ = self.get_cached_promotion_key(it.user, invalidate=False)

        await it.response.defer()
        await self.update_interaction(
            it.user,
            invalidate=False,
            content="You can also use an **open conversation** for your verification.\n"
                    "If you don't have one, you can also click on the button below. "
                    "However, this requires to *manually* open the conversation by an admin. This may take a bit.\n"
                    "\n"
                    f"Your verification code: `{key}`",
            view=ui.NoAccessToNewConversations()
        )

    async def no_open_conversation(self, it: nextcord.Interaction) -> None:
        key, spigot_name = self.get_cached_promotion_key(it.user, invalidate=False)

        await self.update_interaction(
            it.user,
            invalidate=False,
            content="Your request has been forwarded. Please wait, until the conversation is created."
        )

        log.info(f"The user {it.user} requested a conversation.")

        admin: nextcord.Member = self.discord.get_spigot_member()
        admin_channel = admin.dm_channel
        if admin_channel is None:
            admin_channel = await admin.create_dm()

        await admin_channel.send(
            content=f"The discord user {it.user} requests a conversation on SpigotMC.\n"
                    f"You can easily copy the text below as a placeholder.",
            view=ui.CreateConversationForUser(spigot_name, self.config.spigotmc().topic(), it.user.id)
        )

        await admin_channel.send(
            content=f"Hi! The discord user {it.user} requested a conversation for the Discord verification for your "
                    f"SpigotMC account.\n"
                    f"\n"
                    f"Please submit your promotion key in this conversation. "
                    f"You can find it in your DMs on Discord in case you forgot it.\n"
                    f"\n"
                    f"Ignore this message if you haven't requested it."
        )

        channel = it.user.dm_channel
        if channel is None:
            channel = await it.user.create_dm()

        await channel.send(content="Hi 👋\n"
                                   "\n"
                                   f"Your verification key `{key}` is still valid and needs to be confirmed by "
                                   f"sending it to us via the conversation that will be manually created soon.\n"
                                   f"We will inform you as soon as you can submit your key.\n"
                                   f"\n"
                                   f"Please be patient. Thank you! ✌")

    async def conversation_created(self, it: nextcord.Interaction, user_id: int) -> None:
        user = self.discord.get_member(user_id)
        if user is None:
            return

        await it.message.edit(content=f"The user {user} has been informed about the conversation. 👍", view=None)

        channel = user.dm_channel
        if channel is None:
            channel = await user.create_dm()

        await channel.send(
            content="Hi again!\n"
                    "Your conversation has been created. 🤩\n"
                    "Please take a look at your inbox and don't forget to copy your key from the message above. 📫",
            view=ui.ViewConversations()
        )

    async def send_promotion_key(self, it: nextcord.Interaction, spigot_name: str):
        user: nextcord.Member = it.user

        old_promotion_key, old_spigot_name = self.get_cached_promotion_key(user, False)
        if old_spigot_name is not None and old_spigot_name in self.reserved:
            self.reserved.remove(old_spigot_name)
            log.info(f"Promotion process for {user} cancelled.")
            await self.update_interaction(user, content="This verification process has been cancelled.")

        if spigot_name in self.reserved:
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
            self.reserved.append(spigot_name)

            spigot_config = self.config.spigotmc()

            pim: nextcord.PartialInteractionMessage = await it.response.send_message(
                content=f"Please verify the promotion key by sending it to us in a conversation on "
                        f"SpigotMc.\n"
                        f"\n"
                        f"1. Copy the key: `{promotion_key}`\n"
                        f"2. Click the button below to create a conversation\n"
                        f"3. Paste the code in the text area and submit",
                view=ui.ConversationStartButtons(spigot_config.recipient(), spigot_config.topic()),
                ephemeral=True
            )
            self.sent_messages[user.id] = pim
        else:
            log.info(f"Failed transaction id lookup for {user}.")
            await it.response.send_message(
                content=f"We could not find any purchase linked to your account. 😕",
                ephemeral=True
            )

    async def promote(self, user: nextcord.Member, spigot_name: str) -> None:
        self.database.link_user(user.id, spigot_name)
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
        self.sent_codes[user.id] = (started_at, key, spigot_name)
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

        started_at, key, spigot_name = cache

        if invalidate:
            self.sent_codes.pop(user.id)

        return key, spigot_name


def setup(bot: Bot, **kwargs):
    bot.add_cog(Promote(bot, **kwargs))
