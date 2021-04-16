import asyncio
import json
import logging
import threading

import discord

import database
import explanation
import promotion
import spigotmc
import admin

config = json.load(open("config.json"))


class Discord:
    def __init__(self):
        self.guild = None
        self.premium_role = None

    async def fetch(self):
        self.guild = await client.fetch_guild(config["discord"]["guild_id"])
        self.premium_role = await self.__fetch_role__()

    # Fetches the premium role with the premium_id from the config.json.
    async def __fetch_role__(self):
        roles = await self.guild.fetch_roles()
        for role in roles:
            if role.id == config["discord"]["premium_role"]:
                return role
        return None


forum_credentials = spigotmc.Credentials(
    config["spigot_mc"]["user_name"],
    config["spigot_mc"]["password"],
    config["spigot_mc"]["two_factor_secret"],
    config["spigot_mc"]["resource"],
    config["spigot_mc"]["conversation"]["title"],
    config["spigot_mc"]["conversation"]["content"],
    config["google_chrome_location"]
)
database_credentials = database.Credentials(
    database=config["database"]["database"],
    user=config["database"]["user"],
    password=config["database"]["password"],
    host=config["database"]["host"],
    port=config["database"]["port"]
)

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
discord_variables = Discord()
admin_channel = admin.Channel(client, discord_variables, database_credentials, config)

promotions = {}
working_queue = []
explanation_message = explanation.Message(client, config["discord"]["promote_channel"])


def start():
    # Check for default setting
    if config["discord"]["token"] == "<your token here>":
        logging.log(logging.ERROR, "You have to configure config.json before starting the discord bot!")
    else:
        if config["expiration"] > 0:
            threading.Thread(target=asyncio.run, args=(schedule_expiration_task(),)).start()

        # thread blocking
        client.run(config["discord"]["token"])


@client.event
async def on_ready():
    await explanation_message.on_ready()
    await discord_variables.fetch()
    print("Bot started")  # Panel indication


@client.event
async def on_reaction_add(reaction, user):
    if client.user.id == user.id:
        return

    # disallow all reactions in the promotion channel
    if reaction.message.channel.id == config["discord"]["promote_channel"]:
        await reaction.remove(user)


@client.event
async def on_message(message):
    if client.user.id == message.author.id:
        return

    if message.channel.id == config["discord"]["promote_channel"]:
        if discord_variables.premium_role in message.author.roles:
            await message.delete()
            await asyncio.sleep(.5)
            await promotion.Message(message, True, config["discord"]["loading_emoji"]).update()
        elif find(working_queue, lambda m: m.author.id == message.author.id):
            await message.delete()
        elif message.author.id in promotions:
            await message.delete()
            await promotions[message.author.id].incoming_message(message)
        else:
            # add to queue anyway to check for currently working processes
            browsing = len(working_queue) > 0
            working_queue.append(message)

            if not browsing:
                await start_promotion(message)
            else:
                await message.add_reaction("👌")
    if message.channel.id == config["discord"]["admin_channel"]:
        await admin_channel.incoming_message(message)


async def start_promotion(message):
    promotions[message.author.id] = promotion.Process(
        client,
        message,
        lambda user, success: after_verification(user, message.channel, success),
        after_browsing,
        discord_variables.premium_role,
        forum_credentials,
        database_credentials,
        config["discord"]["loading_emoji"]
    )

    await message.delete()
    await asyncio.sleep(.5)
    await promotions[message.author.id].start()


# Will be fired when the browser is ready for the next verification.
def after_browsing():
    working_queue.pop(0)
    if len(working_queue) > 0:
        client.loop.create_task(start_promotion(working_queue[0]))


# Will be fired when a verification is entirely completed (either cancelled or succeeded).
def after_verification(user, channel, success):
    promotions.pop(user.id)

    # Ignore ongoing verifications since cancelled verification won't trigger an explanation update
    if success:
        client.loop.create_task(explanation_message.update_explanation(channel))


async def schedule_expiration_task():
    while True:
        db = database.Database(database_credentials)

        expired = db.fetch_expired_links(config["expiration"])
        if expired is not None:
            db.unlink_discord_ids(expired)
        db.connection.close()

        if expired is not None:
            client.loop.create_task(call_expirations(expired))

        await asyncio.sleep(5)


async def call_expirations(expired_users):
    for user_id in expired_users:
        member = await discord_variables.guild.fetch_member(user_id)

        if member is not None:
            await member.remove_roles(discord_variables.premium_role)
            await member.send(config["messages"]["expiration"])


def find(sequence, condition):
    for x in sequence:
        if condition(x):
            return True
    return False


# initialize bot
start()
