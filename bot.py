import json
import logging
import random
import utils

import discord

# Startup
logging.basicConfig(level=logging.INFO)
config = json.load(open("config.json"))
client = discord.Client()
passwords = {}


def start():
    # Check for default setting
    if config["token"] == "<your token here>":
        logging.log(logging.ERROR, "You have to configure config.json before starting the discord bot!")
    else:
        client.run(config["token"])


async def call_promotion(message):
    # build message
    content = "Spigot: " + message.content + "\n" \
                                             "Buyers list: https://www.spigotmc.org/resources/premium-warps-portals-and-more-warp-teleport-system-1-8-1-16.66035/buyers\n" \
                                             "DM: https://www.spigotmc.org/conversations/add?to=" + message.content + "&title=WarpSystem%20-%20Verification"

    embed = discord.Embed(description=content, colour=0x12a498)
    embed.set_author(name=message.author.name, icon_url=message.author.avatar_url)

    # send embed and save it for later deletion
    channel = client.get_channel(config["admin_channel"])
    sent_embed = await channel.send(embed=embed)

    # send the code separately to allow faster message copy
    code = get_code()
    sent = await channel.send(code)

    # save data for later access
    # turn ready into True when the admin has authorized the promotions; avoids brute force for the correct code
    passwords[code] = {"user": message.author, "message_embed": sent_embed, "message_code": sent, "message": message, "ready": False}

    # contacting user
    await sent.add_reaction("📫")
    await message.author.send("Thank you for using my premium resource 🚀\n\n"
                              "**CodingAir** has been informed about your promotion progress and needs to confirm it **manually** on Spigot.\n\n"
                              "I'll get back to you as soon as he created a code for you 👋")


# generates a unique number between incl. 100.000 and incl. 999999.
def get_code():
    code = random.randint(100000, 999999)

    while code in passwords:
        code = random.randint(100000, 999999)

    return code


# Fetches the premium role with the premium_id from the config.json.
async def get_premium_role(guild):
    roles = await guild.fetch_roles()

    for role in roles:
        if role.id == config["premium_role"]:
            return role

    return None


# Clear old reactions, add check reaction and delete old posts in the admin channel.
async def apply_premium(message, data):
    original_message = data["message"]
    await original_message.clear_reactions()

    user = data["user"]
    await message.add_reaction("✅")

    role = await get_premium_role(message.guild)
    await user.add_roles(role)

    await user.send("You've finally promoted your account to premium 🥳")

    await data["message_embed"].delete()
    await data["message_code"].delete()


@client.event
async def on_ready():
    logging.log(logging.INFO, "I'm ready!")


@client.event
async def on_reaction_add(reaction, user):
    if client.user.id == user.id:
        return

    message = reaction.message
    if message.channel.id == config["promote_channel"]:
        await reaction.remove(user)
    elif message.channel.id == config["admin_channel"]:
        # catch wrong emojis
        if reaction.emoji != "📫":
            await reaction.remove(user)
            return

        content = message.content

        # check if password is given
        try:
            code = int(content)
        except TypeError:
            await reaction.remove(user)
            return

        if code not in passwords:
            await reaction.remove(user)
            return

        data = passwords[code]
        data["ready"] = True  # Approve code

        # react with mailbox
        original_message = data["message"]
        await original_message.add_reaction("📫")

        # contact user
        user = data["user"]
        await user.send("**You have got a verification code!**"
                        "\nCheck your Spigot inbox 📫\n\n"
                        "For all the lazy people: https://www.spigotmc.org/conversations/ ^^")


@client.event
async def on_message(message):
    if message.channel.id == config["promote_channel"]:
        roles = message.author.roles

        if utils.find(roles, lambda x: x.id == config["premium_role"]):
            await message.delete()
            await message.author.send("You already have the premium role 👀")
        else:
            content = message.content

            # Check for verification code
            try:
                code = int(content)  # fail here if content is not an integer

                if code in passwords and passwords[code]["user"] == message.author:
                    # check if code is authorized
                    data = passwords[code]

                    if not data["ready"]:
                        await message.delete()
                        await message.author.send("**Whoops, this was lucky** 🤐\n"
                                                  "You've entered the correct code but CodingAir hasn't approved it yet.\n\n"
                                                  "Please be patient 🙂")
                        return

                    # apply premium only if number is the password of that user
                    await apply_premium(message, data)
                else:
                    await message.delete()
                    await message.author.send("This was the **wrong verification code** 😕\n"
                                              "Please read the pinned message in the promote channel.\n\n"
                                              "*Contact CodingAir if you think this is an error.*")
                return
            except ValueError:
                pass

            # check if user already posted a potential Spigot name
            messages = await message.channel.history(limit=100).flatten()
            if utils.count(messages, lambda m: m.author == message.author) > 1:
                await message.delete()
                await message.author.send("You **already posted** a message containing a potential Spigot name 🤔\n\n*Contact CodingAir if you think this is an error.*")
                return

            # Continue promotion
            await call_promotion(message)

start()
