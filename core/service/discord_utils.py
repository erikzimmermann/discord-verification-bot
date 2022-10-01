from typing import Optional, Tuple, Callable, Coroutine, Any

import nextcord
from nextcord.ext.commands import Bot

from core import files, log
from core.service import database


def compare_rank(a: nextcord.Member, b: nextcord.Member) -> int:
    if a.top_role > b.top_role:
        return -1
    elif a.top_role == b.top_role:
        return 0
    else:
        return 1


class Discord:
    def __init__(self, bot: Bot, config: files.Discord, db: database.MySQL):
        self.config = config
        self.bot = bot
        self.database = db

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

    async def get_all_members(self, consumer: Callable[[nextcord.Member], Coroutine[Any, Any, None]],
                              only_lower_ranked: bool = True, no_bot: bool = True) -> None:
        bot_member = await self.get_bot_member()

        async for member in self.guild.fetch_members():
            if no_bot and member.bot:
                continue

            if only_lower_ranked:
                comparison = compare_rank(member, bot_member)
                if comparison > 0:
                    await consumer(member)
            else:
                await consumer(member)
    
    async def update_user(self, user_id: int) -> None:
        await self.update_member(await self.get_member(user_id))

    async def update_member(self, member: nextcord.Member) -> bool:
        rids = self.database.get_bought_rids(member.id)
        updated = False

        if len(rids) > 0:
            if self.premium_role not in member.roles:
                log.info(f"Adding premium role to '{member}' ({member.id}) due to {len(rids)} verified purchase(s).")
                await member.add_roles(
                    self.premium_role,
                    reason=f"Role added by {len(rids)} verified purchase(s)."
                )
                updated = True
        else:
            if self.premium_role in member.roles:
                log.info(f"Removing premium role from '{member}' ({member.id}) due to 0 verified purchases.")
                await member.remove_roles(
                    self.premium_role,
                    reason=f"Role removed due to 0 verified purchases."
                )
                updated = True

        for role in member.roles:
            rid = self.config.rid_by_role(role.id)
            if rid is not None and rid not in rids:
                # illegal role access
                log.info(f"Removing role '{role.name}' from '{member}' ({member.id}) "
                         f"due to insufficient purchase access ({rid}).")
                await member.remove_roles(role, reason=f"Role removed due to insufficient purchase access ({rid}).")
                updated = True

        for rid in rids:
            role = self.get_role(rid)
            if role not in member.roles:
                log.info(f"Adding role '{role.name}' to '{member}' ({member.id}) due to a verified purchase ({rid}).")
                await member.add_roles(role, reason=f"Role added by verified purchase ({rid}).")
                updated = True

        return updated
