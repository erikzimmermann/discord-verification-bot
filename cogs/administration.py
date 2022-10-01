import nextcord
from nextcord import SlashOption
from nextcord.ext.commands import Cog, Bot

from core import files, log, ui, magic
from core.service import services


class Control(Cog):
    def __init__(self, bot: Bot, **kwargs):
        self.bot = bot
        self.config: files.Config = kwargs["config"]
        self.services: services.Holder = kwargs["services"]

        self.database = self.services.database
        self.discord = self.services.discord

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

        if not self.database.is_user_linked(target.id):
            await it.response.send_message(
                content=f"This Discord user is not linked to a SpigotMC account. 😕",
                ephemeral=True
            )
            return

        log.info(f"The Discord user '{user}' has initiated the link removal of '{target}'.")

        self.database.invalidate_link(target.id)
        await self.discord.update_member(target)

        await it.response.send_message(
            content=f"The verification of '{target}' has been removed. 👀",
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


def setup(bot: Bot, **kwargs):
    bot.add_cog(Control(bot, **kwargs))
