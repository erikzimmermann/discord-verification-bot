import asyncio
import random
import threading

import discord

import database
import spigotmc

color_error = 0xfa5858
color_processing = 0x12a498
color_success = 0xdaa520


class Message:
    def __init__(self, message, has_premium, loading_emoji, run_later=None):
        self.user = message.author
        self.spigot_user = message.content
        self.channel = message.channel
        self.run_later = run_later
        self.loading_emoji = loading_emoji

        self.response = None
        self.has_premium = has_premium
        self.no_buyer = False
        self.spigot_already_linked = False
        self.code_received = False
        self.done = False
        self.error = False

    async def update(self):
        if self.response is not None:
            await self.response.delete()
            await asyncio.sleep(.5)

        if self.done:
            color = color_success
            title = self.user.name + "'s promotion is completed"
            content = self.user.name + " has been successfully promoted to premium ✅"
            if self.run_later is not None:
                self.run_later(self.user, True)
        elif self.error:
            color = color_error
            title = self.user.name + "'s promotion has been cancelled"
            content = "An error occurred. Please try it again."
        elif self.has_premium:
            color = color_error
            title = self.user.name + "'s promotion has been cancelled"
            content = "You already have the premium role 👀"
        elif self.spigot_already_linked:
            color = color_error
            title = self.user.name + "'s promotion has been cancelled"
            content = self.spigot_user + " is already linked to a discord account 🤨"
        elif self.no_buyer:
            color = color_error
            title = self.user.name + "'s promotion has been cancelled"
            content = self.spigot_user + " hasn't purchased the plugin 😭"
        elif self.code_received:
            color = color_processing
            title = "Verifying " + self.user.name
            content = "The verification code has been sent. Check your SpigotMC inbox 📫\n\n" \
                      "https://www.spigotmc.org/conversations/"
        else:
            color = color_processing
            title = "Verifying " + self.user.name
            content = "Your verification is processing. Please wait " + self.loading_emoji

        embed = discord.Embed(description=content, colour=color)
        embed.set_author(name=title, icon_url=self.user.avatar_url)

        self.response = await self.channel.send(embed=embed)

        if color == color_error:
            asyncio.create_task(self.__delete_response__())

    async def __delete_response__(self):
        await asyncio.sleep(10)
        await self.response.delete()
        if self.run_later is not None:
            self.run_later(self.user, False)


class Process:
    def __init__(self, client, message, run_later, run_after_browsing, premium_role, forum_credentials, database_credentials, loading_emoji, logger, has_premium=False):
        self.client = client
        self.message = Message(message, has_premium, loading_emoji, run_later)
        self.run_after_browsing = run_after_browsing
        self.user = message.author
        self.spigot = message.content
        self.guild = message.guild
        self.premium_role = premium_role
        self.forum_credentials = forum_credentials
        self.code = random.randint(100000, 999999)
        self.database = database.Database(database_credentials)
        self.logger = logger

    async def start(self):
        self.logger.info("Starting " + self.user.name + "'s promotion")
        await self.message.update()

        if self.database.is_discord_user_linked(self.user.id):
            # Skip process, user has already been linked -> re-link
            await self.__apply_premium__()
            self.__stop__()
        elif self.database.is_spigot_name_linked(self.spigot):
            self.message.spigot_already_linked = True
            await self.message.update()
            self.__stop__()
        else:
            # Run check in another thread to avoid blocking the main thread
            threading.Thread(target=asyncio.run, args=(self.__check_premium__(),)).start()

    async def incoming_message(self, message):
        if self.message.code_received:
            if message.content == str(self.code):
                self.database.link(self.spigot, self.user)
                await self.__apply_premium__()

    def __stop__(self):
        self.database.connection.close()
        self.logger.info(self.user.name + "'s promotion has been finished")

    async def __apply_premium__(self):
        await self.user.add_roles(self.premium_role)

        self.message.done = True
        await self.message.update()
        self.__stop__()

    async def __check_premium__(self):
        forum = spigotmc.ForumAPI(self.forum_credentials, self.forum_credentials.google_chrome_location, self.logger)
        forum.debug("start " + self.spigot + "'s verification")

        try:
            # thread-blocking
            if forum.is_user_premium(self.spigot):
                forum.send_message(self.spigot, self.forum_credentials.title, self.forum_credentials.content.format(code=self.code, discord=self.user.name + "#" + self.user.discriminator))
                self.message.code_received = True
            else:
                self.message.no_buyer = True

            # close browser
            forum.close()

            forum.debug("done")
        except Exception as e:
            forum.debug("an error occurred: " + str(e))
            self.message.error = True

        # go back to main thread
        await self.__complete_browsing__()

    async def __complete_browsing__(self):
        self.client.loop.create_task(self.message.update())

        # add bigger delay to avoid SpigotMC's message cooldown
        await asyncio.sleep(20)

        self.client.loop.create_task(self.run_after_browsing())
