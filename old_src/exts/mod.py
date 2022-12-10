import asyncio
import contextlib
import logging
from asyncio import sleep
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Optional, Union

import interactions
from interactions.ext.wait_for import wait_for_component
from pymongo.database import *

import src.const
import src.model as model
from src.const import *


class Mod(interactions.Extension):
    """An extension dedicated to /mod and other functionalities."""

    def __init__(self, bot):
        self.bot: interactions.Client = bot

        self.action_logs = interactions.Channel(id=src.const.METADATA["channels"]["action-logs"], type=1)  # type: ignore
        self.mod_logs = interactions.Channel(id=src.const.METADATA["channels"]["mod-logs"], type=1)  # type: ignore
        self.staff = interactions.Channel(id=src.const.METADATA["channels"]["staff"], type=1)  # type: ignore

    @interactions.extension_listener(name="on_start")
    async def add_httpclient(self):
        self.action_logs._client = self.bot._http
        self.mod_logs._client = self.bot._http
        self.staff._client = self.bot._http

    @interactions.extension_command(scope=METADATA["guild"])
    async def mod(self, ctx: interactions.CommandContext, **kwargs):
        """Handles all moderation aspects."""

        if not self.__check_role(ctx):
            await ctx.send(":x: You are not a moderator.", ephemeral=True)
            return interactions.StopCommand()

    @mod.group()
    async def member(self, *args, **kwargs):
        ...

    @member.subcommand()
    @interactions.option("The user you wish to ban")
    @interactions.option("The reason behind why you want to ban them.")
    async def ban(
        self,
        ctx: interactions.CommandContext,
        member: interactions.Member,
        reason: str = "N/A",
    ):
        """Bans a member from the server and logs into the database."""
        await ctx.defer(ephemeral=True)

        try:
            await member.ban(guild_id=src.const.METADATA["guild"], reason=reason)
        except interactions.LibraryException:
            await ctx.send(f":x: Could not ban {member.mention}.", ephemeral=True)
            return

        await model.Action(
            user=str(member.id),
            type=model.ActionType.BAN,
            moderator=str(ctx.author.id),
            created_at=datetime.now(),
            reason=reason,
        ).insert()

        embed = interactions.Embed(
            title="User banned",
            color=0xED4245,
            author=interactions.EmbedAuthor(
                name=f"{member.user.username}#{member.user.discriminator}",
                icon_url=member.user.avatar_url,
            ),
            fields=[
                interactions.EmbedField(
                    name="Moderator",
                    value=f"{ctx.author.mention} ({ctx.author.user.username}#{ctx.author.user.discriminator})",
                    inline=True,
                ),
                interactions.EmbedField(
                    name="Timestamps",
                    value="\n".join(
                        [
                            f"Joined: <t:{round(member.joined_at.timestamp())}:R>.",
                            f"Created: <t:{round(member.id.timestamp.timestamp())}:R>.",
                        ]
                    ),
                ),
                interactions.EmbedField(name="Reason", value=reason),
            ],
        )

        await self.action_logs.send(embeds=embed)
        await ctx.send(f":heavy_check_mark: {member.mention} has been banned.", ephemeral=True)

    @member.subcommand()
    @interactions.option("The ID of the user you wish to unban.")
    @interactions.option("The reason behind why you want to unban them.")
    async def unban(self, ctx: interactions.CommandContext, id: str, reason: str = "N/A"):
        """Unbans a user from the server and logs into the database."""
        await ctx.defer(ephemeral=True)

        try:
            user = await interactions.get(self.bot, interactions.User, object_id=int(id))
        except interactions.LibraryException:
            await ctx.send(":x: Invalid ID provided.", ephemeral=True)
            return

        try:
            guild = await interactions.get(
                self.bot, interactions.Guild, object_id=src.const.METADATA["guild"]
            )
            await guild.remove_ban(user_id=user.id, reason=reason)
        except interactions.LibraryException:
            await ctx.send(f":x: Could not unban {user.mention}.", ephemeral=True)

        await model.Action(
            user=id,
            type=model.ActionType.UNBAN,
            moderator=str(ctx.author.id),
            created_at=datetime.now(),
            reason=reason,
        ).insert()

        embed = interactions.Embed(
            title="User unbanned",
            color=0x57F287,
            author=interactions.EmbedAuthor(
                name=f"{user.username}#{user.discriminator}",
                icon_url=user.avatar_url,
            ),
            fields=[
                interactions.EmbedField(
                    name="Moderator",
                    value=f"{ctx.author.mention} ({ctx.author.user.username}#{ctx.author.user.discriminator})",
                    inline=True,
                ),
                interactions.EmbedField(name="Reason", value=reason),
            ],
        )

        await self.action_logs.send(embeds=embed)
        await ctx.send(f":heavy_check_mark: {user.mention} has been unbanned.", ephemeral=True)

    @member.subcommand()
    @interactions.option("The user you wish to kick")
    @interactions.option("The reason behind why you want to kick them.")
    async def kick(
        self,
        ctx: interactions.CommandContext,
        member: interactions.Member,
        reason: str = "N/A",
    ):
        """Kicks a member from the server and logs into the database."""
        await ctx.defer(ephemeral=True)

        try:
            await member.kick(guild_id=src.const.METADATA["guild"], reason=reason)
        except interactions.LibraryException:
            await ctx.send(f":x: Could not kick {member.mention}.", ephemeral=True)
            return

        await model.Action(
            user=str(member.id),
            type=model.ActionType.KICK,
            moderator=str(ctx.author.id),
            created_at=datetime.now(),
            reason=reason,
        ).insert()

        embed = interactions.Embed(
            title="User kicked",
            color=0xED4245,
            author=interactions.EmbedAuthor(
                name=f"{member.user.username}#{member.user.discriminator}",
                icon_url=member.user.avatar_url,
            ),
            fields=[
                interactions.EmbedField(
                    name="Moderator",
                    value=f"{ctx.author.mention} ({ctx.author.user.username}#{ctx.author.user.discriminator})",
                    inline=True,
                ),
                interactions.EmbedField(
                    name="Timestamps",
                    value="\n".join(
                        [
                            f"Joined: <t:{round(member.joined_at.timestamp())}:R>.",
                            f"Created: <t:{round(member.id.timestamp.timestamp())}:R>.",
                        ]
                    ),
                ),
                interactions.EmbedField(name="Reason", value=reason),
            ],
        )

        await self.action_logs.send(embeds=embed)
        await ctx.send(f":heavy_check_mark: {member.mention} has been kicked.", ephemeral=True)

    @member.subcommand()
    @interactions.option("The user you wish to warn")
    @interactions.option("The reason behind why you want to warn them.")
    async def warn(
        self,
        ctx: interactions.CommandContext,
        member: interactions.Member,
        reason: str = "N/A",
    ):
        """Warns a member in the server and logs into the database."""
        await ctx.defer(ephemeral=True)

        ctx_channel = await ctx.get_channel()
        await ctx_channel.send(
            content=f"{member.mention}, you have been warned for reason: {reason}."
        )

        await model.Action(
            user=str(member.id),
            type=model.ActionType.WARN,
            moderator=str(ctx.author.id),
            created_at=datetime.now(),
            reason=reason,
        ).insert()

        embed = interactions.Embed(
            title="User warned",
            color=0xFEE75C,
            author=interactions.EmbedAuthor(
                name=f"{member.user.username}#{member.user.discriminator}",
                icon_url=member.user.avatar_url,
            ),
            fields=[
                interactions.EmbedField(
                    name="Moderator",
                    value=f"{ctx.author.mention} ({ctx.author.user.username}#{ctx.author.user.discriminator})",
                    inline=True,
                ),
                interactions.EmbedField(
                    name="Timestamps",
                    value="\n".join(
                        [
                            f"Joined: <t:{round(member.joined_at.timestamp())}:R>.",
                            f"Created: <t:{round(member.id.timestamp.timestamp())}:R>.",
                        ]
                    ),
                ),
                interactions.EmbedField(name="Reason", value=reason),
            ],
        )

        await self.action_logs.send(embeds=embed)
        await ctx.send(f":heavy_check_mark: {member.mention} has been warned.", ephemeral=True)

    @member.subcommand()
    @interactions.option("The user you wish to timeout")
    @interactions.option("The reason behind why you want to timeout them.")
    @interactions.option("How long the user should be timeouted in days.")
    @interactions.option(
        "How long the user should be timeouted in hours.",
    )
    @interactions.option(
        "How long the user should be timeouted in minutes.",
    )
    @interactions.option(
        "How long the user should be timeouted in seconds.",
    )
    async def timeout(
        self,
        ctx: interactions.CommandContext,
        member: interactions.Member,
        reason: str = "N/A",
        days: int = 0,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
    ):
        """Timeouts a member in the server and logs into the database."""
        if not days and not hours and not minutes and not seconds:
            return await ctx.send(":x: missing any indicator of timeout length!", ephemeral=True)

        await ctx.defer(ephemeral=True)

        time = datetime.now()
        time += timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

        try:
            await member.modify(
                guild_id=ctx.guild_id, communication_disabled_until=time.isoformat()
            )
        except interactions.LibraryException:
            return await ctx.send(f":x: Could not timeout {member.mention}.", ephemeral=True)

        await model.Action(
            user=str(member.id),
            type=model.ActionType.TIMEOUT,
            moderator=str(ctx.author.id),
            created_at=datetime.now(),
            reason=reason,
        ).insert()

        embed = interactions.Embed(
            title="User timed out",
            color=0xFEE75C,
            author=interactions.EmbedAuthor(
                name=f"{member.user.username}#{member.user.discriminator}",
                icon_url=member.user.avatar_url,
            ),
            fields=[
                interactions.EmbedField(
                    name="Moderator",
                    value=f"{ctx.author.mention} ({ctx.author.user.username}#{ctx.author.user.discriminator})",
                    inline=True,
                ),
                interactions.EmbedField(
                    name="Timestamps",
                    value="\n".join(
                        [
                            f"Joined: <t:{round(member.joined_at.timestamp())}:R>.",
                            f"Created: <t:{round(member.id.timestamp.timestamp())}:R>.",
                        ]
                    ),
                ),
                interactions.EmbedField(name="Reason", value="N/A" if reason is None else reason),
            ],
        )

        await self.action_logs.send(embeds=embed)
        await ctx.send(
            f":heavy_check_mark: {member.mention} has been timed out until <t:{round(time.timestamp())}:F> (<t:{round(time.timestamp())}:R>).",
            ephemeral=True,
        )

    @member.subcommand()
    @interactions.option("The user you wish to untimeout")
    @interactions.option("The reason behind why you want to untimeout them.")
    async def untimeout(
        self,
        ctx: interactions.CommandContext,
        member: interactions.Member,
        reason: str = "N/A",
    ):
        """Untimeouts a member in the server and logs into the database."""
        await ctx.defer(ephemeral=True)

        if member.communication_disabled_until is None:
            return await ctx.send(f":x: {member.mention} is not timed out.", ephemeral=True)

        try:
            await member.modify(guild_id=ctx.guild_id, communication_disabled_until=None)
        except interactions.LibraryException:
            return await ctx.send(f":x: Could not untimeout {member.mention}.")

        await model.Action(
            user=str(member.id),
            type=model.ActionType.UNTIMEOUT,
            moderator=str(ctx.author.id),
            created_at=datetime.now(),
            reason=reason,
        ).insert()

        embed = interactions.Embed(
            title="User untimed out",
            color=0xFEE75C,
            author=interactions.EmbedAuthor(
                name=f"{member.user.username}#{member.user.discriminator}",
                icon_url=member.user.avatar_url,
            ),
            fields=[
                interactions.EmbedField(
                    name="Moderator",
                    value=f"{ctx.author.mention} ({ctx.author.user.username}#{ctx.author.user.discriminator})",
                    inline=True,
                ),
                interactions.EmbedField(
                    name="Timestamps",
                    value="\n".join(
                        [
                            f"Joined: <t:{round(member.joined_at.timestamp())}:R>.",
                            f"Created: <t:{round(member.id.timestamp.timestamp())}:R>.",
                        ]
                    ),
                ),
                interactions.EmbedField(name="Reason", value="N/A" if reason is None else reason),
            ],
        )

        await self.action_logs.send(embeds=embed)
        await ctx.send(f":heavy_check_mark: {member.mention} has been untimed out.", ephemeral=True)

    @mod.group()
    async def channel(self, *args, **kwargs):
        ...

    @channel.subcommand()
    @interactions.option("The amount of messages you want to delete")
    @interactions.option("Whether bulk delete should be used, default True")
    @interactions.option("The reason behind why you want purge.")
    @interactions.option(
        "The channel that should be purged",
        channel_types=[interactions.ChannelType.GUILD_TEXT],
    )
    @interactions.autodefer(ephemeral=True)
    async def purge(
        self,
        ctx: interactions.CommandContext,
        amount: int,
        bulk: bool = True,
        reason: str = "N/A",
        channel: interactions.Channel = None,
    ):
        """Purges an amount of message of a channel."""
        if not channel:
            channel = await ctx.get_channel()

        await ctx.send("Purging...", ephemeral=True)

        begin = perf_counter()
        await channel.purge(amount=amount, bulk=bulk, reason=reason)
        end = perf_counter()

        if end - begin >= 900:  # more than 15m
            time = datetime.now() + timedelta(seconds=30)
            msg = await channel.send(
                f":heavy_check_mark: {channel.mention} was purged. {ctx.author.mention} \n"
                f"**I will self-destruct in <t:{time.timestamp()}:R>**!"
            )
            await sleep(30)
            await msg.delete()

        else:
            await ctx.send(f":heavy_check_mark: {channel.mention} was purged. ", ephemeral=True)

    @channel.subcommand()
    @interactions.option("The amount of time to be set as slowmode.")
    @interactions.option("The reason behind why you want to add slow-mode.")
    @interactions.option(
        "The channel that should be slowmoded",
        channel_types=[interactions.ChannelType.GUILD_TEXT],
    )
    @interactions.autodefer(ephemeral=True)
    async def slowmode(
        self,
        ctx: interactions.CommandContext,
        time: int,
        reason: str = "N/A",
        channel: interactions.Channel = None,
    ):
        """Sets the slowmode in a channel."""
        if not channel:
            channel = await ctx.get_channel()

        await channel.modify(rate_limit_per_user=time, reason=reason)
        await ctx.send(f":heavy_check_mark: {channel.mention}'s slowmode was set!", ephemeral=True)

    @channel.subcommand()
    @interactions.option("The reason of the lock.")
    async def lock(self, ctx: interactions.CommandContext, reason: str = "N/A"):
        """Locks the current channel."""
        await ctx.get_channel()

        overwrites = ctx.channel.permission_overwrites

        for overwrite in overwrites:
            if int(overwrite.id) == int(ctx.guild_id):
                overwrite.deny |= interactions.Permissions.SEND_MESSAGES
                break
        else:
            overwrites.append(
                interactions.Overwrite(
                    id=str(ctx.guild_id),
                    deny=interactions.Permissions.SEND_MESSAGES,
                    type=0,
                )
            )

        await ctx.channel.modify(reason=reason, permission_overwrites=overwrites)

    @channel.subcommand()
    @interactions.option("The reason of the unlock")
    async def unlock(self, ctx: interactions.CommandContext, reason: str = "N/A"):
        await ctx.get_channel()

        overwrites = ctx.channel.permission_overwrites

        for overwrite in overwrites:
            if int(overwrite.id) == int(ctx.guild_id):
                overwrite.deny &= ~interactions.Permissions.SEND_MESSAGES
                overwrite.allow |= interactions.Permissions.SEND_MESSAGES
                break
        else:
            overwrites.append(
                interactions.Overwrite(
                    id=str(ctx.guild_id),
                    allow=interactions.Permissions.SEND_MESSAGES,
                    type=0,
                )
            )

        await ctx.channel.modify(reason=reason, permission_overwrites=overwrites)

    def __check_role(self, ctx: interactions.CommandContext) -> bool:
        """Checks whether an invoker has the Moderator role or not."""
        # TODO: please get rid of me when perms v2 is out. this is so dumb.
        # no bc perm system not good for this
        return str(src.const.METADATA["roles"]["Moderator"]) in [
            str(role) for role in ctx.author.roles
        ]

    @interactions.extension_listener()
    async def on_message_delete(self, message: interactions.Message):
        embed = interactions.Embed(
            title="Message deleted",
            color=0xED4245,
            author=interactions.EmbedAuthor(
                name=f"{message.author.username}#{message.author.discriminator}",
                icon_url=message.author.avatar_url,
            ),
            fields=[
                interactions.EmbedField(name="ID", value=str(message.author.id), inline=True),
                interactions.EmbedField(
                    name="Message", value=message.content or "**Message could not be retrieved.**"
                ),
            ],
        )

        await self.mod_logs.send(embeds=embed)

    @interactions.extension_listener()
    async def on_message_update(self, before: interactions.Message, after: interactions.Message):
        embed = interactions.Embed(
            title="Message updated",
            color=0xED4245,
            author=interactions.EmbedAuthor(
                name=f"{after.author.username}#{after.author.discriminator}",
                icon_url=after.author.avatar_url,
            ),
            fields=[
                interactions.EmbedField(name="ID", value=str(after.author.id), inline=True),
                interactions.EmbedField(
                    name="Before:",
                    value=before.content
                    if before and before.content
                    else "**Message could not be retrieved.**",
                ),
                interactions.EmbedField(
                    name="After:", value=after.content or "**Message could not be retrieved.**"
                ),
            ],
        )

        await self.mod_logs.send(embeds=embed)

    @interactions.extension_listener()
    async def on_guild_member_add(self, member: interactions.GuildMember):
        embed = interactions.Embed(
            title="User joined",
            color=0x57F287,
            author=interactions.EmbedAuthor(
                name=f"{member.user.username}#{member.user.discriminator}",
                icon_url=member.user.avatar_url,
            ),
            fields=[
                interactions.EmbedField(name="ID", value=str(member.user.id)),
                interactions.EmbedField(
                    name="Timestamps",
                    value="\n".join(
                        [
                            f"Joined: <t:{round(member.joined_at.timestamp())}:R>.",
                            f"Created: <t:{round(member.id.timestamp.timestamp())}:R>.",
                        ]
                    ),
                ),
            ],
        )

        await self.mod_logs.send(embeds=embed)

    @interactions.extension_listener()
    async def on_guild_member_remove(self, member: interactions.GuildMember):
        embed = interactions.Embed(
            title="User left",
            color=0xED4245,
            author=interactions.EmbedAuthor(
                name=f"{member.user.username}#{member.user.discriminator}",
                icon_url=member.user.avatar_url,
            ),
            fields=[
                interactions.EmbedField(name="ID", value=str(member.user.id)),
                interactions.EmbedField(
                    name="Timestamps",
                    value="\n".join(
                        [
                            f"Joined: <t:{round(member.joined_at.timestamp())}:R>.",
                            f"Created: <t:{round(member.id.timestamp.timestamp())}:R>.",
                        ]
                    ),
                ),
            ],
        )
        await self.mod_logs.send(embeds=embed)


def setup(bot, **kwargs):
    Mod(bot, **kwargs)