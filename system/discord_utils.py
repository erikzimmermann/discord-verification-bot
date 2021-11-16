from typing import Optional

import discord


class Discord:
    def __init__(self, client: discord.Client, config: dict):
        self.config = config
        self.client = client

        self.guild = None
        self.premium_role: Optional[discord.Role] = None
        self.admin_channel: Optional[discord.TextChannel] = None
        self.stopping: bool = False
        self.promotions: dict = {}
        self.working_queue: list = []

    async def fetch(self) -> None:
        self.guild = await self.client.fetch_guild(self.client["discord"]["guild_id"])
        self.premium_role = await self.__fetch_role__()
        self.admin_channel = await self.client.fetch_channel(self.client["discord"]["admin_channel"])

    # Fetches the premium role with the premium_id from the config.json.
    async def __fetch_role__(self) -> Optional[discord.Role]:
        roles = await self.guild.fetch_roles()
        for role in roles:
            if role.id == self.client["discord"]["premium_role"]:
                return role
        return None
