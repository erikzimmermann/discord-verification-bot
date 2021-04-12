import json
import logging
import manager
import discord

# Startup
logging.basicConfig(level=logging.INFO)
config = json.load(open("config.json"))
client = discord.Client()
error_notice = "*Contact CodingAir if you think this is an error.*"
man = manager.Manager(config, client, )


def start():
    # Check for default setting
    if config["token"] == "<your token here>":
        logging.log(logging.ERROR, "You have to configure config.json before starting the discord bot!")
    else:
        client.run(config["token"])


@client.event
async def on_ready():
    print("Bot started")  # Panel indication


@client.event
async def on_reaction_add(reaction, user):
    if client.user.id == user.id:
        return

    message = reaction.message
    if message.channel.id == config["promote_channel"]:
        await reaction.remove(user)
    elif message.channel.id == config["admin_channel"]:
        # catch wrong emojis
        if reaction.emoji == "📫":
            content = message.content

            # check if password is given
            code = man.content_to_code(content)
            if code is None:
                await reaction.remove(user)
                return

            data = man.passwords[code]
            data["ready"] = True  # Approve code

            # react with mailbox
            original_message = data["message"]
            await original_message.add_reaction("📫")

            # contact user
            user = data["user"]
            await user.send("**You've got a verification code!**"
                            "\nCheck your Spigot inbox 📫\n\n"
                            "https://www.spigotmc.org/conversations/")
        elif reaction.emoji == "❌":
            content = message.content

            # check if password is given
            code = man.content_to_code(content)
            if code is None:
                await reaction.remove(user)
                return

            await man.clear_data(code, False)
            await user.send("It seems like you **haven't bought** my resource...\n"
                            "I'm sorry but I can't promote your account 😢\n\n" + error_notice)
        else:
            await reaction.remove(user)
            return


@client.event
async def on_message(message):
    if message.channel.id == config["promote_channel"]:
        roles = message.author.roles

        if manager.find(roles, lambda x: x.id == config["premium_role"]):
            await message.delete()
            await message.author.send("You already have the premium role 👀")
        else:
            content = message.content

            # Check for verification code
            try:
                code = int(content)  # fail here if content is not an integer

                # apply premium only if number is the password of that user
                if code in man.passwords and man.passwords[code]["user"] == message.author:
                    # check if code is authorized
                    data = man.passwords[code]

                    if not data["ready"]:
                        await message.delete()
                        await message.author.send("**Whoops, this was lucky** 🤐\n"
                                                  "You've entered the correct code but CodingAir hasn't approved it yet.\n\n"
                                                  "Please be patient 🙂")
                        return

                    await man.apply_premium(message, data["user"])
                    await man.clear_data(code, True)
                else:
                    await message.delete()
                    await message.author.send("This was the **wrong verification code** 😕\n"
                                              "Please read the pinned message in the promote channel.\n\n" + error_notice)
                return
            except ValueError:
                pass

            # check if user already posted a potential Spigot name
            messages = await message.channel.history(limit=100).flatten()
            if manager.count(messages, lambda m: m.author == message.author) > 1:
                await message.delete()
                await message.author.send("You **already posted** a message containing a potential Spigot name 🤔\n\n" + error_notice)
                return

            # Continue promotion
            await man.call_promotion(message)


start()
