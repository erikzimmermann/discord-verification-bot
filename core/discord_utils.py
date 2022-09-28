from typing import Optional, Tuple

import nextcord
from nextcord.ext.commands import Bot
from nextcord.iterators import MemberIterator
from core import files, log


def compare_rank(a: nextcord.Member, b: nextcord.Member) -> int:
    if a.top_role > b.top_role:
        return -1
    elif a.top_role == b.top_role:
        return 0
    else:
        return 1


class Discord:
    def __init__(self, bot: Bot, config: files.Discord):
        self.config = config
        self.bot = bot

        self.guild: Optional[nextcord.Guild] = None
        self.roles: Optional[dict[str, nextcord.Role]] = None
        self.premium_role: Optional[nextcord.Role] = None
        self.ready = False

    async def fetch(self) -> None:
        log.info("Fetching Discord instances...")

        self.guild = await self.bot.fetch_guild(self.config.guild_id())
        self.roles, self.premium_role = await self.__fetch_roles__()

        if not self.guild:
            log.error("Could not fetch guild. Please check the discord section in your config!")
            return

        if len(self.roles) == 0:
            log.error("Could not fetch functional roles. Please check the discord section in your config!")
            return

        if not self.premium_role:
            log.error("Could not fetch premium role. Please check the discord section in your config!")
            return

        self.ready = True

    def is_ready(self):
        return self.ready

    async def __fetch_roles__(self) -> Tuple[dict[str, nextcord.Role], nextcord.Role]:
        roles = dict()
        premium_role = None

        fetched = await self.guild.fetch_roles()
        for role in fetched:
            if role.id == self.config.premium_role():
                premium_role = role
            else:
                rid = self.config.rid_by_role(role.id)
                if rid is not None:
                    roles[str(rid)] = role
        return roles, premium_role

    def get_role(self, rid: int) -> Optional[nextcord.Role]:
        return self.roles.get(str(rid))

    async def get_member(self, user_id: int) -> nextcord.Member:
        return await self.guild.fetch_member(user_id)

    async def get_bot_member(self) -> nextcord.Member:
        return await self.get_member(self.bot.user.id)

    def get_all_members(self) -> MemberIterator:
        return self.guild.fetch_members()
