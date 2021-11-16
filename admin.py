import asyncio

import discord

import bot
import database


def cut(s, index):
    s = s[index:]
    while s.startswith(" "):
        s = s[1:]
    return s


class Channel:
    def __init__(self, client: discord.Client, discord_variables: bot.Discord, database_credentials: database.Credentials, config: dict):
        self.client = client
        self.discord_variables = discord_variables
        self.database_credentials = database_credentials
        self.config = config

    async def __react__(self, message: discord.Message, status: int):
        await message.clear_reactions()
        await asyncio.sleep(.1)

        if status == 0:
            await message.add_reaction("✅")
        elif status == 1:
            await message.add_reaction(self.config["discord"]["loading_emoji"])
        else:
            await message.add_reaction("🤔")

        await asyncio.sleep(.5)

    async def incoming_message(self, message: discord.Message):
        command = message.content
        if command.startswith("!v"):
            command = cut(command, 2)

            if command.startswith("help"):
                await self.__react__(message, 0)
                await message.reply("**You can choose from following commands:**\n"
                                    "`!v reset_existing_verifications` > Removes the premium role from every member on this server\n"
                                    "`!v unlink_spigot <spigot_name>` > Unlink a specific SpigotMC user\n"
                                    "`!v cancel <discord_id>` > Remove a specific user from a working list\n"
                                    "`!v promote <spigot_name> <discord_id>` > Promotes a spigot/discord user")
                return
            elif command.startswith("reset_existing_verifications"):
                await self.__react__(message, 1)
                counter = 0
                for member in await self.discord_variables.guild.fetch_members().flatten():
                    if self.discord_variables.premium_role in member.roles:
                        await member.remove_roles(self.discord_variables.premium_role)
                        counter = counter + 1
                await self.__react__(message, 0)
                await message.reply("I've removed the premium role from " + str(counter) + " member(s).")
                return
            elif command.startswith("unlink_spigot"):
                deep = cut(command, 13)

                if len(deep) == 0:
                    await self.__react__(message, -1)
                    await message.reply("Wrong syntax: `!v unlink_spigot <spigot_name>`")
                    return

                await self.__react__(message, 1)
                db = database.Database(self.database_credentials)
                discord_user_id = db.get_linked_discord_user_id(deep)

                if discord_user_id is None:
                    await self.__react__(message, 0)
                    await message.reply("The SpigotMC username `" + deep + "` is not linked.")
                else:
                    db.unlink_spigot_name(deep)
                    user = await self.discord_variables.guild.fetch_member(discord_user_id)
                    await user.remove_roles(self.discord_variables.premium_role)
                    await self.__react__(message, 0)
                    await message.reply("The link between the SpigotMC username `" + deep + "` and the Discord user `" + user.name + "#" + user.discriminator + "` has been removed.")

                db.connection.close()
                return
            elif command.startswith("cancel"):
                deep = cut(command, 6)

                if len(deep) == 0:
                    await self.__react__(message, -1)
                    await message.reply("Wrong syntax: `!v cancel <discord_id>`")
                    return

                try:
                    user_id = int(deep)
                    found_promoting = user_id in self.discord_variables.promotions
                    if found_promoting:
                        self.discord_variables.promotions.pop(user_id)

                    found_working = False
                    index = 0
                    for messages in self.discord_variables.working_queue:
                        if messages.author.id == user_id:
                            found_working = True
                            break
                        index = index + 1

                    if found_working:
                        self.discord_variables.working_queue.pop(index)

                    if found_promoting and found_working:
                        await message.reply("I've removed `" + deep + "` from both lists, promoting and browsing.")
                    elif found_working:
                        await message.reply("I've removed `" + deep + "` from the browsing list.")
                    elif found_promoting:
                        await message.reply("I've removed `" + deep + "` from the promoting list.")
                    else:
                        await message.reply("The user id `" + deep + "` could not be found in a list.")

                    await self.__react__(message, 0)
                except any:
                    await message.reply("Wrong syntax: `!v cancel <discord_id>`")
                    await self.__react__(message, -1)

                return
            elif command.startswith("promote"):
                deep = cut(command, 7)
                args = deep.split()

                if len(args) < 2:
                    await self.__react__(message, -1)
                    await message.reply("Wrong syntax: `!v promote <spigot_name> <discord_name#tag>`")
                    return

                name_spigot = args[0]
                id_discord = args[1]

                if len(name_spigot) == 0 or not id_discord.isdigit():
                    await self.__react__(message, -1)
                    await message.reply("Wrong syntax: `!v promote <spigot_name> <discord_id>`")
                    return

                await self.__react__(message, 1)
                db = database.Database(self.database_credentials)

                target_user = await message.guild.fetch_member(id_discord)

                if target_user is None:
                    await self.__react__(message, -1)
                    await message.reply("The discord user with id '" + id_discord + "' could not be found.")
                    return

                if db.is_spigot_name_linked(name_spigot):
                    await self.__react__(message, -1)
                    await message.reply("The spigot user '" + name_spigot + "' is already linked.")
                    return

                if db.is_discord_user_linked(id_discord):
                    await self.__react__(message, -1)
                    await message.reply("The discord user '" + target_user.name + "#" + target_user.discriminator + "' is already linked.")
                    return

                db.link(name_spigot, target_user)
                await target_user.add_roles(self.discord_variables.premium_role)

                await self.__react__(message, 0)
                await message.reply("The SpigotMC username `" + name_spigot + "` and the Discord user `" + target_user.name + "#" + target_user.discriminator + "` has been linked.")

                db.connection.close()
                return

            await self.__react__(message, -1)
            await message.reply("That's an unknown command. Try `!v help`.")
