import asyncio
import database


def cut(s, index):
    s = s[index:]
    if s.startswith(" "):
        s = s[1:]
    return s


class Channel:
    def __init__(self, client, discord_variables, database_credentials, config):
        self.client = client
        self.discord_variables = discord_variables
        self.database_credentials = database_credentials
        self.config = config

    async def __react__(self, message, status):
        await message.clear_reactions()
        await asyncio.sleep(.1)

        if status == 0:
            await message.add_reaction("✅")
        elif status == 1:
            await message.add_reaction(self.config["discord"]["loading_emoji"])
        else:
            await message.add_reaction("🤔")

        await asyncio.sleep(.5)

    async def incoming_message(self, message):
        command = message.content
        if command.startswith("!verify"):
            command = cut(command, 7)

            if command.startswith("help"):
                await self.__react__(message, 0)
                await message.reply("**You can choose from following commands:**\n"
                                    "`!verify reset_existing_verifications` > Removes the premium role from every member on this server"
                                    "`!verify unlink_spigot <spigot_name>` > Unlink a specific SpigotMC user")
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
                    await message.reply("Wrong syntax: `!verify unlink_spigot <spigot_name>`")
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

            await self.__react__(message, -1)
            await message.reply("That's an unknown command. Try `!verify help`.")
