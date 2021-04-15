import json
import logging

import discord

import database
import explanation
import promotion
import spigotmc

config = json.load(open("config.json"))

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
client = discord.Client()

promotions = {}
working_queue = []
explanation_message = explanation.Message(client, config["discord"]["promote_channel"])


def start():
    # Check for default setting
    if config["discord"]["token"] == "<your token here>":
        logging.log(logging.ERROR, "You have to configure config.json before starting the discord bot!")
    else:
        client.run(config["discord"]["token"])


@client.event
async def on_ready():
    await explanation_message.on_ready()
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
        roles = message.author.roles
        if find(roles, lambda x: x.id == config["discord"]["premium_role"]):
            await message.delete()
            await promotion.Message(message, has_premium=True).update()
        elif message.author.id in promotions:
            await message.delete()
            await promotions[message.author.id].incoming_message(message)
        else:
            # add to queue anyway to check for currently working processes
            browsing = len(working_queue) > 0
            working_queue.append(message)

            if not browsing:
                await start_promotion(message)


async def start_promotion(message):
    promotions[message.author.id] = promotion.Process(
        client,
        message,
        lambda user, success: after_verification(user, message.channel, success),
        after_browsing,
        config["discord"]["premium_role"],
        forum_credentials,
        database_credentials
    )

    await message.delete()
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


def find(sequence, condition):
    for x in sequence:
        if condition(x):
            return True
    return False


# initialize bot
start()
