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
        self.admin_channel = None
        self.stopping = False
        self.promotions = {}
        self.working_queue = []

    async def fetch(self):
        self.guild = await client.fetch_guild(config["discord"]["guild_id"])
        self.premium_role = await self.__fetch_role__()
        self.admin_channel = await client.fetch_channel(config["discord"]["admin_channel"])

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

logging.basicConfig(filename="log.txt",
                    filemode='a',
                    format='%(asctime)s %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
discord_variables = Discord()
admin_channel = admin.Channel(client, discord_variables, database_credentials, config)

explanation_message = explanation.Message(client, config["discord"]["promote_channel"], config["messages"]["explanation"])


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
    logging.info("Bot started")  # Panel indication


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
        elif find(discord_variables.working_queue, lambda m: m.author.id == message.author.id):
            await message.delete()
        elif message.author.id in discord_variables.promotions:
            await message.delete()
            await discord_variables.promotions[message.author.id].incoming_message(message)
        else:
            # add to queue anyway to check for currently working processes
            browsing = len(discord_variables.working_queue) > 0
            discord_variables.working_queue.append(message)

            if not browsing:
                await start_promotion(message)
            else:
                await message.add_reaction("👌")
    if message.channel.id == config["discord"]["admin_channel"]:
        await admin_channel.incoming_message(message)


async def start_promotion(message):
    discord_variables.promotions[message.author.id] = promotion.Process(
        client,
        message,
        lambda user, success: after_verification(user, message.channel, success),
        after_browsing,
        discord_variables.premium_role,
        forum_credentials,
        database_credentials,
        config["discord"]["loading_emoji"],
        logging
    )

    await message.delete()
    await asyncio.sleep(.5)
    await discord_variables.promotions[message.author.id].start()


# Will be fired when the browser is ready for the next verification.
def after_browsing():
    discord_variables.working_queue.pop(0)
    if len(discord_variables.working_queue) > 0:
        client.loop.create_task(start_promotion(discord_variables.working_queue[0]))


# Will be fired when a verification is entirely completed (either cancelled or succeeded).
def after_verification(user, channel, success):
    discord_variables.promotions.pop(user.id)

    # Ignore ongoing verifications since cancelled verification won't trigger an explanation update
    if success:
        client.loop.create_task(explanation_message.update_explanation(channel))


async def schedule_expiration_task():
    while not discord_variables.stopping:
        # sleep before run --> Avoid sending messages to expired users
        await asyncio.sleep(60)

        db = database.Database(database_credentials)

        expired = db.fetch_expired_links(config["expiration"])
        if expired is not None:
            db.unlink_discord_ids(expired)
        db.connection.close()

        if expired is not None:
            client.loop.create_task(call_expirations(expired))


async def call_expirations(expired_users):
    for user_id in expired_users:
        member = await discord_variables.guild.fetch_member(user_id)

        if member is not None:
            await member.remove_roles(discord_variables.premium_role)

            try:
                # some users may disallow private messages
                await member.send(config["messages"]["expiration"])
            except:
                await discord_variables.admin_channel.send("Could not contact " + member.name + "#" + member.discriminator + " regarding their premium expiration.")
                pass


def find(sequence, condition):
    for x in sequence:
        if condition(x):
            return True
    return False


# initialize bot
logging.info("\n\n##############################################################################\n")
start()
discord_variables.stopping = True
