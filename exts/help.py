import asyncio
import importlib
import io

import aiohttp
import naff
from naff.models.discord.channel import GuildForumPost

import common.utils as utils
from common.const import *


async def check_archive(ctx: naff.Context):
    return ctx.channel.parent_id == METADATA["channels"]["help"]


class HelpChannel(naff.Extension):
    def __init__(self, bot: naff.Client):
        self.client = bot
        self.session: aiohttp.ClientSession = bot.session
        self.help_channel: naff.GuildForum = None  # type: ignore
        asyncio.create_task(self.fill_help_channel())

    async def fill_help_channel(self):
        await self.bot.wait_until_ready()
        self.help_channel = self.bot.get_channel(METADATA["channels"]["help"])  # type: ignore

    @naff.context_menu("Create Help Thread", naff.CommandTypes.MESSAGE)  # type: ignore
    async def create_thread_context_menu(self, ctx: naff.InteractionContext):
        message: naff.Message = ctx.target  # type: ignore

        modal = naff.Modal(
            "Create Help Thread",
            [
                naff.ShortText(
                    label="What should the thread be named?",
                    value=f"[AUTO] Help thread for {message.author.username}",
                    min_length=1,
                    max_length=100,
                    custom_id="help_thread_name",
                ),
                naff.ParagraphText(
                    label="What should the question be?",
                    value=message.content,
                    min_length=1,
                    max_length=4000,
                    custom_id="edit_content",
                ),
                naff.ParagraphText(
                    label="Any addition information?",
                    required=False,
                    min_length=1,
                    max_length=1024,
                    custom_id="extra_content",
                ),
            ],
            custom_id=f"help_thread_creation_{message.channel.id}|{message.id}",
        )
        await ctx.send_modal(modal)
        await ctx.send(":white_check_mark: Modal sent.", ephemeral=True)

    def generate_tag_select(self):
        tags = self.help_channel.available_tags
        options: list[naff.SelectOption] = []

        for tag in tags:
            emoji = None
            if tag.emoji_id:
                emoji = naff.PartialEmoji(id=tag.emoji_id, name=tag.emoji_name or "emoji")
            elif tag.emoji_name:
                emoji = naff.PartialEmoji.from_str(tag.emoji_name)

            options.append(naff.SelectOption(tag.name, str(tag.id), emoji=emoji))

        options.append(
            naff.SelectOption(
                label="Remove all tags",
                value="remove_all_tags",
                emoji=naff.PartialEmoji.from_str("🗑"),
            ),
        )
        return naff.StringSelectMenu(
            options=options,
            placeholder="Select the tags you want",
            min_values=1,
            max_values=len(options),
            custom_id="TAG_SELECTION",
        )

    @naff.listen("modal_completion")
    async def context_menu_handling(self, event: naff.events.ModalCompletion):
        ctx = event.ctx

        if ctx.custom_id.startswith("help_thread_creation_"):
            await ctx.defer(ephemeral=True)

            channel_id, message_id = ctx.custom_id.removeprefix("help_thread_creation_").split("|")

            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                return await utils.error_send(
                    ctx, ":x: Could not find channel of message.", naff.MaterialColors.RED
                )

            message = await channel.fetch_message(int(message_id))  # type: ignore
            if not message:
                return await utils.error_send(
                    ctx, ":x: Could not fetch message.", naff.MaterialColors.RED
                )

            files: list[naff.File] = []

            if message.attachments:
                for attahcment in message.attachments:
                    if attahcment.size > 8388608:  # if it's over 8 MiB, that's a bit much
                        continue

                    async with self.session.get(attahcment.proxy_url) as resp:
                        try:
                            resp.raise_for_status()
                        except aiohttp.ClientResponseError:
                            continue

                        raw_file = await resp.read()
                        files.append(naff.File(io.BytesIO(raw_file), file_name=attahcment.filename))

            post_thread = await self.help_channel.create_post(
                ctx.responses["help_thread_name"],
                content=message.content,
                applied_tags=["996215708595794071"],
                auto_archive_duration=1440,  # type: ignore
                files=files,  # type: ignore
                reason="Auto help thread creation",
            )

            await post_thread.add_member(ctx.author)
            await post_thread.add_member(message.author)

            embed = None

            if content := ctx.responses.get("extra_content"):
                embed = naff.Embed(
                    title="Additional Information",
                    description=content,
                    color=ASTRO_COLOR,
                )
                embed.set_footer(text="Please create a thread in #help to ask questions!")

            select = self.generate_tag_select()

            original_message_button = naff.Button(
                style=naff.ButtonStyles.LINK,
                label="Original message",
                url=message.jump_url,
            )
            close_button = naff.Button(
                style=naff.ButtonStyles.DANGER,
                label="Close this thread",
                custom_id="close_thread",
            )

            starter_message = await post_thread.send(
                (
                    "This help thread was automatically generated. Read the message above for more"
                    " information."
                ),
                embeds=embed,
                components=[[original_message_button], [select], [close_button]],
            )
            await starter_message.pin()

            await message.reply(
                f"Hey, {message.author.mention}! At this time, we only help with support-related"
                f" questions in our help channel. Please redirect to {post_thread.mention} in order"
                " to receive help."
            )
            await ctx.send(":white_check_mark: Thread created.", ephemeral=True)

    @naff.listen("new_thread_create")
    async def first_message_for_help(self, event: naff.events.NewThreadCreate):
        thread = event.thread
        if not thread.parent_id or int(thread.parent_id) != METADATA["channels"]["help"]:
            return

        if thread.owner_id == self.bot.user.id:
            # an autogenerated thread, don't interfere
            return

        select = self.generate_tag_select()
        close_button = naff.Button(
            style=naff.ButtonStyles.DANGER,
            label="Close this thread",
            custom_id="close_thread",
        )

        message = await thread.send(
            "Hey! Once your issue is solved, press the button below to close this thread!",
            components=[[select], [close_button]],
        )
        await message.pin()

    @naff.component_callback("TAG_SELECTION")  # type: ignore
    async def modify_tags(self, ctx: naff.ComponentContext):
        if not utils.helper_check(ctx) and ctx.author.id != ctx.channel.owner_id:
            return await utils.error_send(
                ctx, ":x: You are not an advanced user.", naff.MaterialColors.YELLOW
            )

        await ctx.defer(ephemeral=True)

        channel: GuildForumPost = ctx.channel  # type: ignore
        tags = [int(v) for v in ctx.values] if "remove_all_tags" not in ctx.values else []
        await channel.edit(applied_tags=tags)
        await ctx.send(":white_check_mark: Done.", ephemeral=True)

    @naff.slash_command("archive", description="Archives a help thread.")
    @utils.helpers_only()
    @naff.check(check_archive)  # type: ignore
    async def archive(self, ctx: naff.InteractionContext):
        await ctx.send(":white_check_mark: Archiving...")
        await ctx.channel.edit(archived=True, locked=True)

    @naff.component_callback("close_thread")  # type: ignore
    async def close_help_thread(self, ctx: naff.ComponentContext):
        if not utils.helper_check(ctx) and ctx.author.id != ctx.channel.owner_id:
            return await utils.error_send(
                ctx, ":x: You are not an advanced user.", naff.MaterialColors.YELLOW
            )

        await ctx.send(":white_check_mark: Closing. Thank you for using our help system.")
        await ctx.channel.edit(archived=True, locked=True)


def setup(bot):
    importlib.reload(utils)
    HelpChannel(bot)
