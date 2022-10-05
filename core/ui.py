import urllib.parse
from typing import Callable, Coroutine, Any

import nextcord.ui
from nextcord.ui import View, Modal, TextInput


class StartPromotionButton(View):
    def __init__(self):
        super().__init__(timeout=None, auto_defer=False)

    @nextcord.ui.button(label="Start Promotion", style=nextcord.ButtonStyle.gray, custom_id="promotion_start")
    async def enter_promotion_key(self, button: nextcord.Button, interaction: nextcord.Interaction) -> None:
        pass


class SpigotNameInput(Modal):
    def __init__(self, callback: Callable[[nextcord.Interaction, str], Coroutine[Any, Any, None]]):
        super(SpigotNameInput, self).__init__(f"Account Promotion")
        self.nested_callback = callback

        self.input = TextInput(
            label="Please enter your SpigotMC name", required=True, min_length=2, max_length=100,
            style=nextcord.TextInputStyle.short
        )
        self.add_item(self.input)

    async def callback(self, interaction: nextcord.Interaction):
        await self.nested_callback(interaction, self.input.value.strip())


class ConversationStartButtons(View):
    def __init__(self, spigotmc_recipient: str, spigotmc_topic: str):
        super().__init__(timeout=None, auto_defer=False)

        spigotmc_recipient = urllib.parse.quote_plus(spigotmc_recipient)
        spigotmc_topic = urllib.parse.quote_plus(spigotmc_topic)

        url = f"https://www.spigotmc.org/conversations/add?to={spigotmc_recipient}&title={spigotmc_topic}"

        self.add_item(nextcord.ui.Button(
            label="Verify",
            url=url
        ))

        self.add_item(nextcord.ui.Button(
            label="I cannot create a conversation",
            style=nextcord.ButtonStyle.gray,
            custom_id="no_conversation_access"
        ))


class NoAccessToNewConversations(View):
    def __init__(self):
        super().__init__(timeout=None, auto_defer=False)

        self.add_item(nextcord.ui.Button(
            label="Conversations",
            url="https://www.spigotmc.org/conversations/?tab=inbox"
        ))

        self.add_item(nextcord.ui.Button(
            label="I could not find any open conversation",
            style=nextcord.ButtonStyle.gray,
            custom_id="no_open_conversation"
        ))


class ViewConversations(View):
    def __init__(self):
        super().__init__(timeout=None, auto_defer=False)

        self.add_item(nextcord.ui.Button(
            label="Conversations",
            url="https://www.spigotmc.org/conversations/?tab=inbox"
        ))


class CreateConversationForUser(View):
    def __init__(self, spigot_name: str, spigotmc_topic: str, user_id: int):
        super().__init__(timeout=None, auto_defer=False)

        spigotmc_recipient = urllib.parse.quote_plus(spigot_name)
        spigotmc_topic = urllib.parse.quote_plus(spigotmc_topic)

        url = f"https://www.spigotmc.org/conversations/add?to={spigotmc_recipient}&title={spigotmc_topic}"

        self.add_item(nextcord.ui.Button(
            label="Create Conversation",
            url=url
        ))

        self.add_item(nextcord.ui.Button(
            label="Finished",
            style=nextcord.ButtonStyle.success,
            custom_id=f"conversation_created:{user_id}"
        ))
