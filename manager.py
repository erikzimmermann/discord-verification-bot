import random

import discord


def count(sequence, condition):
    i = 0
    for x in sequence:
        if condition(x):
            i = i + 1
    return i


def find(sequence, condition):
    for x in sequence:
        if condition(x):
            return True
    return False


class Manager:
    def __init__(self, config, client):
        self.config = config
        self.client = client

    passwords = {}

    # generates a unique number between incl. 100.000 and incl. 999999.
    def get_code(self):
        code = random.randint(100000, 999999)

        while code in self.passwords:
            code = random.randint(100000, 999999)

        return code

    # Converts the content of a text message into a code (int) if possible.
    def content_to_code(self, content):
        try:
            code = int(content)

            if code not in self.passwords:
                return None
        except TypeError:
            return None
        return code

    # Fetches the premium role with the premium_id from the config.json.
    async def get_premium_role(self, guild):
        roles = await guild.fetch_roles()

        for role in roles:
            if role.id == self.config["premium_role"]:
                return role

        return None

    # Clear old reactions, add check reaction and delete old posts in the admin channel.
    async def clear_data(self, code, success):
        data = self.passwords[code]

        if success:
            await data["message"].clear_reactions()
        else:
            await data["message"].delete()

        await data["message_embed"].delete()
        await data["message_code"].delete()

        self.passwords.pop(code)  # Remove code

    async def apply_premium(self, message, user):
        await message.add_reaction("✅")

        role = await self.get_premium_role(message.guild)
        await user.add_roles(role)

        await user.send("You've finally promoted your account to premium 🥳")

    async def call_promotion(self, message):
        # build message
        content = "Spigot: " + message.content + "\n"
        content = content + "Buyers list: " + self.config["buyers_list"] + "\n"
        content = content + "DM: https://www.spigotmc.org/conversations/add?to=" + message.content + "&title=" + self.config["conversation_title"]

        embed = discord.Embed(description=content, colour=0x12a498)
        embed.set_author(name=message.author.name, icon_url=message.author.avatar_url)

        # send embed and save it for later deletion
        channel = self.client.get_channel(self.config["admin_channel"])
        sent_embed = await channel.send(embed=embed)

        # send the code separately to allow faster message copy
        code = self.get_code()
        sent = await channel.send(code)

        # save data for later access
        # turn ready into True when the admin has authorized the promotions; avoids brute force for the correct code
        self.passwords[code] = {"user": message.author, "message_embed": sent_embed, "message_code": sent, "message": message, "ready": False}

        # contacting user
        await sent.add_reaction("📫")
        await sent.add_reaction("❌")
        await message.author.send("Thank you for using my premium resource 🚀\n\n"
                                  "**CodingAir** has been informed about your promotion progress and needs to confirm it **manually** on Spigot.\n\n"
                                  "I'll get back to you as soon as he created a code for you 👋")
