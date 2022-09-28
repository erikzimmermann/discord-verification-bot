from typing import Callable, Coroutine, Any, Optional

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


class PromotionKeyInputButton(View):
    def __init__(self, validation_check: Callable[[nextcord.Member], Coroutine[Any, Any, bool]],
                 callback: Callable[[nextcord.Member, int], Coroutine[Any, Any, None]]):
        super().__init__(timeout=None, auto_defer=False)
        self.validation_check = validation_check
        self.callback = callback

    @nextcord.ui.button(label="Verify code", style=nextcord.ButtonStyle.success, custom_id="verify_code")
    async def enter_promotion_key(self, button: nextcord.Button, interaction: nextcord.Interaction) -> None:
        if await self.validation_check(interaction.user):
            await interaction.response.send_modal(PromotionKeyInput(self.callback))


class PromotionKeyInput(Modal):
    def __init__(self, callback: Callable[
                     [nextcord.Member, int], Coroutine[Any, Any, None]]):
        super(PromotionKeyInput, self).__init__(f"Account Promotion")
        self.nested_callback = callback

        self.input = TextInput(
            label="Please enter the 6-digit promotion key", required=True, min_length=6, max_length=6,
            style=nextcord.TextInputStyle.short
        )
        self.add_item(self.input)

    async def callback(self, interaction: nextcord.Interaction):
        value = self.input.value

        if value.isnumeric():
            await self.nested_callback(interaction.user, int(value))
        else:
            await self.nested_callback(interaction.user, 0)
