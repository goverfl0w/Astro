import logging
from urllib.parse import quote_plus

import interactions
from beanie import init_beanie
from interactions.ext.wait_for import setup
from motor.motor_asyncio import *
from pymongo.server_api import ServerApi

from .const import *
from .model import Action, Tag

log = logging.getLogger()
log.setLevel(logging.DEBUG)

stderr_handler = logging.StreamHandler()
stderr_handler.setLevel(logging.WARNING)
log.addHandler(stderr_handler)

file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="a")
file_handler.setFormatter(logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s"))
file_handler.setLevel(logging.INFO)
log.addHandler(file_handler)

presence = interactions.ClientPresence(
    activities=[
        interactions.PresenceActivity(
            name="you. 👀", type=interactions.PresenceActivityType.WATCHING
        ),
    ],
    status=interactions.StatusType.DND,
)
bot = interactions.Client(
    TOKEN,
    intents=(
        interactions.Intents.GUILDS
        | interactions.Intents.GUILD_MEMBERS
        | interactions.Intents.GUILD_BANS
        | interactions.Intents.GUILD_MESSAGES
        | interactions.Intents.DIRECT_MESSAGES  # commands can work in DMs too.
        | interactions.Intents.GUILD_MESSAGE_CONTENT
        | interactions.Intents.GUILDS
    ),
    presence=presence,
    disable_sync=False,
)
setup(bot)


async def db_setup():
    client = AsyncIOMotorClient(MONGO_DB_URL, server_api=ServerApi("1"))
    await init_beanie(client.Astro, document_models=[Tag, Action])


bot._loop.create_task(db_setup())


[bot.load(f"src.exts.{ext}") for ext in EXTENSIONS]


@bot.event
async def on_ready():
    print(f"Logged in as {bot.me.name}.")


@bot.command(
    name="subscribe",
    description='Adds the changelog and/or external pings role, "subscribing" to you to release news.',
    scope=METADATA["guild"],
    options=[
        interactions.Option(
            name="changelog",
            description="To what changelogs do you want to subscribe? (default only main library)",
            required=False,
            type=interactions.OptionType.STRING,
            choices=[
                interactions.Choice(name="Only Main Library Changelogs", value="main"),
                interactions.Choice(name="Only External Library Changelogs", value="external"),
                interactions.Choice(name="Both Changelogs", value="both"),
            ],
        )
    ],
)
async def subscribe(ctx: interactions.CommandContext, changelog: str = "main"):

    await ctx.defer(ephemeral=True)  # this could take more than 3 seconds ig?

    if changelog == "main":
        role: int = METADATA["roles"].get("Changelog pings")

        if role in ctx.member.roles:
            await ctx.member.remove_role(role=role, guild_id=METADATA["guild"])
            await ctx.send(":heavy_check_mark: Role removed.", ephemeral=True)
        else:
            await ctx.member.add_role(role=role, guild_id=METADATA["guild"])
            await ctx.send(":heavy_check_mark: Role added.", ephemeral=True)

    elif changelog == "external":
        role: int = METADATA["roles"].get("External Changelog pings")

        if role in ctx.member.roles:
            await ctx.member.remove_role(role=role, guild_id=METADATA["guild"])
            await ctx.send(":heavy_check_mark: Role removed.", ephemeral=True)
        else:
            await ctx.member.add_role(role=role, guild_id=METADATA["guild"])
            await ctx.send(":heavy_check_mark: Role added.", ephemeral=True)

    elif changelog == "both":
        resp = ":heavy_check_mark: "
        role1: int = METADATA["roles"].get("Changelog pings")
        role2: int = METADATA["roles"].get("External Changelog pings")

        if role1 in ctx.member.roles:
            await ctx.member.remove_role(role=role1, guild_id=METADATA["guild"])
            resp += "Changelog pings role removed. "
        else:
            await ctx.member.add_role(role=role1, guild_id=METADATA["guild"])
            resp += "Changelog pings role added. "

        if role2 in ctx.member.roles:
            await ctx.member.remove_role(role=role2, guild_id=METADATA["guild"])
            resp += "External Changelog pings role removed. "
        else:
            await ctx.member.add_role(role=role2, guild_id=METADATA["guild"])
            resp += "External Changelog pings role added. "

        return await ctx.send(resp, ephemeral=True)


@bot.command(name="add-role-menu", description="N/A.", scope=METADATA["guild"])
async def add_role_menu(ctx: interactions.CommandContext):
    if str(ctx.author.id) == "242351388137488384":
        _channel: dict = await bot._http.get_channel(METADATA["channels"]["information"])
        _roles: list[str] = [
            role
            for role in METADATA["roles"]
            if role
            not in [
                "Changelog pings",
                "Helper",
                "Moderator",
                "External Changelog pings",
            ]
        ]

        channel = interactions.Channel(**_channel, _client=bot._http)
        role_menu = interactions.SelectMenu(
            options=[
                interactions.SelectOption(
                    label=lang,
                    value=lang,
                    emoji=interactions.Emoji(
                        id=None,
                        name=METADATA["roles"][lang]["emoji"],
                        animated=False,
                    ),
                )
                for lang in _roles
            ],
            placeholder="Choose a language.",
            custom_id="language_role",
            max_values=1,
        )
        await channel.send(components=role_menu)
        await ctx.send(":heavy_check_mark:", ephemeral=True)
    else:
        await ctx.send("You cannot use this command.", ephemeral=True)


@bot.component("language_role")
async def language_role_selection(ctx: interactions.ComponentContext, choice: list[str]):
    role: int
    roles: dict = {}
    [
        roles.update({role: METADATA["roles"][role]})
        for role in METADATA["roles"]
        if role not in ["Changelog pings", "Helper", "Moderator", "External Changelog pings"]
    ]

    # so many people have been complaining about the bot being "broken"
    # when in reality it's a poor latency match between their client and
    # the application. the deferrence is being added to ensure that
    # a loading state will always appear.
    await ctx.defer(ephemeral=True)

    match choice[0]:
        case "한국어":
            role = roles.get("한국어")
        case "Русский":
            role = roles.get("Русский")
        case "Deutsch":
            role = roles.get("Deutsch")
        case "Français":
            role = roles.get("Français")
        case "हिंदी":
            role = roles.get("हिंदी")
        case "Italiano":
            role = roles.get("Italiano")
        case "Polskie":
            role = roles.get("Polskie")
        case "Español":
            role = roles.get("Español")
        case "Україна":
            role = roles.get("Україна")
        case _:
            await ctx.send(":x: The role you selected was invalid.", ephemeral=True)
            return

    if role["id"] in ctx.member.roles:
        await ctx.member.remove_role(role=role["id"], guild_id=METADATA["guild"])
        await ctx.send(":heavy_check_mark: Role removed.", ephemeral=True)
    else:
        await ctx.member.add_role(role=role["id"], guild_id=METADATA["guild"])
        await ctx.send(":heavy_check_mark: Role added.", ephemeral=True)


@bot.command(scope=METADATA["guild"])
@interactions.option("the thing to look for")
async def letmegooglethat(ctx: interactions.CommandContext, param: str):
    if str(METADATA["roles"]["Helper"]) not in [str(role) for role in ctx.author.roles]:
        return await ctx.send(":x: You are not a helper.", ephemeral=True)

    q = quote_plus(param)
    await ctx.send("collecting Google things...", ephemeral=True)
    await (await ctx.get_channel()).send(f"<https://letmegooglethat.com/?q={q}>")