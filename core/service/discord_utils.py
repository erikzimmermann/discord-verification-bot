from typing import Optional, Tuple, Set

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

        self.roles: Optional[dict[str, nextcord.Role]] = None
        self.premium_role: Optional[nextcord.Role] = None
        self.ready = False

    async def fetch(self) -> None:
        log.info("Fetching Discord instances...")

        if not self.get_guild():
            log.error("Could not fetch guild. Please check the discord section in your config!")
            return

        self.roles, self.premium_role = await self.__fetch_roles__()
        if len(self.roles) == 0:
            log.error("Could not fetch functional roles. Please check the discord section in your config!")
            return

        if not self.premium_role:
            log.error("Could not fetch premium role. Please check the discord section in your config!")
            return

        if not self.all_roles_present():
            log.error("Could not fetch every functional role. "
                      "Please check your discord accordingly to your configurations.")
            return

        self.ready = True

    def get_guild(self) -> nextcord.Guild:
        return self.bot.get_guild(self.config.guild_id())

    def is_ready(self):
        return self.ready and self.all_roles_present()

    def all_roles_present(self) -> bool:
        for rid in self.config.resource_ids():
            if not self.get_role(rid):
                return False
        return True

    async def __fetch_roles__(self) -> Tuple[dict[str, nextcord.Role], nextcord.Role]:
        roles = dict()
        premium_role = None

        guild = self.get_guild()
        fetched = await guild.fetch_roles()

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

    async def fetch_member(self, user_id: int) -> nextcord.Member:
        return await self.get_guild().fetch_member(user_id)

    def get_member(self, user_id: int) -> nextcord.Member:
        return self.get_guild().get_member(user_id)

    async def fetch_bot_member(self) -> nextcord.Member:
        return await self.fetch_member(self.bot.user.id)

    def get_spigot_member(self) -> nextcord.Member:
        return self.get_guild().get_member(self.config.spigot_author_id())

    def get_admin_channel(self) -> nextcord.TextChannel:
        return self.get_guild().get_channel(self.config.admin_channel())

    async def update_members(self) -> int:
        changed = 0

        roles, premium_role = await self.__fetch_roles__()
        members: Set[nextcord.Member] = set()

        for role in roles.values():
            members.update(role.members)
        members.update(premium_role.members)

        for m in members:
            if await self.update_member(m):
                changed += 1

        return changed

    async def update_user(self, user_id: int) -> None:
        await self.update_member(await self.fetch_member(user_id))

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
            if role and role not in member.roles:
                log.info(f"Adding role '{role.name}' to '{member}' ({member.id}) due to a verified purchase ({rid}).")
                await member.add_roles(role, reason=f"Role added by verified purchase ({rid}).")
                updated = True

        return updated
