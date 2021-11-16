import asyncio
from typing import Optional

import discord


class Message:
    def __init__(self, client: discord.Client, promote_channel: str, explanation_config: dict):
        self.client = client
        self.promote_channel = promote_channel
        self.explanation_config = explanation_config
        self.explanation_message = None
        self.updating = False

    async def update_explanation(self, channel: discord.TextChannel) -> None:
        # avoid concurrent multi updates
        if self.updating:
            return
        self.updating = True

        if self.explanation_message is not None:
            await asyncio.sleep(5)
            await self.explanation_message.delete()
            await asyncio.sleep(.5)

        embed = discord.Embed(description=self.explanation_config["content"], colour=0x327fa8)
        embed.set_author(name=self.explanation_config["title"], icon_url=self.explanation_config["title_image_url"])

        self.explanation_message = await channel.send(embed=embed)
        self.updating = False

    async def on_ready(self) -> None:
        channel = await self.__has_old_explanation__()
        if channel is not None:
            await self.update_explanation(channel)

    # Returns a channel if there is no explanation in the last 10 messages.
    async def __has_old_explanation__(self) -> Optional[discord.TextChannel]:
        # assumes that the bot is only connected to one guild
        channel = await self.client.fetch_channel(self.promote_channel)

        if channel is not None:
            for message in await channel.history(limit=10).flatten():
                for embed in message.embeds:
                    if embed.author.name == "How to verify":
                        self.explanation_message = message
                        return None
        return channel
