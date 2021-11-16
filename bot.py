import asyncio
import json
import logging
import threading
from typing import Callable

import discord

from system import explanation, database, promotion, spigotmc, discord_utils, admin

config: dict = json.load(open("config.json"))

forum_credentials = spigotmc.Credentials(config["google_chrome_location"], config=config["spigot_mc"])
database_credentials = database.Credentials(config=config["database"])

logging.basicConfig(filename="log.txt",
                    filemode='a',
                    format='%(asctime)s %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

# Enable caching all members
intents = discord.Intents.default()
intents.members = True

client = discord.Client(intents=intents)
discord_variables = discord_utils.Discord(client, config)
admin_channel = admin.Channel(client, discord_variables, database_credentials, config)

explanation_message = explanation.Message(client, config["discord"]["promote_channel"], config["messages"]["explanation"])


def start() -> None:
    # Check for default setting
    if config["discord"]["token"] == "<your token here>":
        logging.log(logging.ERROR, "You have to configure config.json before starting the discord bot!")
    else:
        if config["expiration"] > 0:
            threading.Thread(target=asyncio.run, args=(schedule_expiration_task(),)).start()

        # thread blocking
        client.run(config["discord"]["token"])


@client.event
async def on_ready() -> None:
    await explanation_message.on_ready()
    await discord_variables.fetch()
    logging.info("Bot started")  # Panel indication


@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User) -> None:
    if client.user.id == user.id:
        return

    # disallow all reactions in the promotion channel
    if reaction.message.channel.id == config["discord"]["promote_channel"]:
        await reaction.remove(user)


@client.event
async def on_message(message: discord.Message) -> None:
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


async def start_promotion(message: discord.Message) -> None:
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
async def after_browsing() -> None:
    discord_variables.working_queue.pop(0)
    if len(discord_variables.working_queue) > 0:
        client.loop.create_task(start_promotion(discord_variables.working_queue[0]))


# Will be fired when a verification is entirely completed (either cancelled or succeeded).
def after_verification(user: discord.User, channel: discord.TextChannel, success: bool) -> None:
    discord_variables.promotions.pop(user.id)

    # Ignore ongoing verifications since cancelled verification won't trigger an explanation update
    if success:
        client.loop.create_task(explanation_message.update_explanation(channel))


async def schedule_expiration_task() -> None:
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


async def call_expirations(expired_users: list) -> None:
    for user_id in expired_users:
        member = await discord_variables.guild.fetch_member(user_id)

        if member is not None:
            await member.remove_roles(discord_variables.premium_role)

            try:
                # some users may disallow private messages
                await member.send(config["messages"]["expiration"])
            except any:
                await discord_variables.admin_channel.send("Could not contact " + member.name + "#" + member.discriminator + " regarding their premium expiration.")
                pass


def find(sequence: list, condition: Callable) -> bool:
    for x in sequence:
        if condition(x):
            return True
    return False


# initialize bot
logging.info("\n\n##############################################################################\n")
start()
discord_variables.stopping = True
