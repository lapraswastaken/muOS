
import asyncio
#from solos import printNLP
import datetime as dt
import discord
from discord.ext import commands, tasks
import os
import traceback
from typing import Union

from CogDex import CogDex
from CogMod import CogMod
from CogRand import CogRand
from Help import Help
from sources.general import BOT_PREFIX, MENTION_ME
from sources.ids import TEST
from utils import Fail, getRandomAvatarImageAndTime, handlePaginationReaction

intents: discord.Intents = discord.Intents.default()
intents.members = True

def determinePrefix(bot: commands.Bot, message: discord.Message):
    if isinstance(message.channel, discord.DMChannel):
        if message.content.startswith(BOT_PREFIX):
            return BOT_PREFIX
        if message.content.startswith(BOT_PREFIX.title()):
            return BOT_PREFIX.title()
        return ""
    else:
        if message.content.startswith(BOT_PREFIX.title()):
            return BOT_PREFIX.title()
        return BOT_PREFIX

client = commands.Bot(
    command_prefix=determinePrefix,
    case_insensitive=True,
    help_command=Help(verify_checks=False),
    intents=intents
)
cogRand = CogRand(client)
client.add_cog(cogRand)
cogDex = CogDex(client)
client.add_cog(cogDex)
cogMod = CogMod()
client.add_cog(cogMod)

@tasks.loop(hours=24 * 2)
async def changeAvatar():
    print("Changing avatar")
    im = getRandomAvatarImageAndTime()
    await client.user.edit(avatar=im)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}.")
    now = dt.datetime.now()
    then = now.replace(day=now.day + now.day % 2, hour=0, minute=0, second=0, microsecond=0)
    if now > then:
        then = then.replace(day=then.day + 2)
    print(f"Next profile picture change:\n  {then}")
    
    await asyncio.sleep((then - now).total_seconds())
    changeAvatar.start()

@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return
    if message.author.bot:
        """
        print(f"[{str(dt.datetime.now().time())[:-7]}, #{message.channel.name}] {message.author.name}: {message.content}")
        printNLP(message.content)
        """
    else:
        await client.process_commands(message)

@client.event
async def on_message_delete(message: discord.Message):
    if message.author.bot: return
    await cogMod.handleMessageDelete(message)

@client.event
async def on_reaction_add(reaction: discord.Reaction, user: Union[discord.User, discord.Member]):
    #print("on_reaction_add")
    if user.bot: return
    await handlePaginationReaction(reaction.message, reaction.emoji, user)

@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """
    print("on_raw_reaction_add")
    if not payload.message_id in [message.id for message in client.cached_messages]:
        user = await client.fetch_user(payload.user_id)
        channel = await client.fetch_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)
        await handlePaginationReaction(message, payload.emoji, user)
    """


@client.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    toRaise = None
    toSend = ""
    if isinstance(error, commands.MissingRequiredArgument):
        toSend += f"You missed a required argument `{error.param.name}`."
    elif isinstance(error, commands.BadUnionArgument):
        toSend += f"There was an error converting the argument `{error.param.name}`."
    elif isinstance(error, commands.CommandNotFound):
        toSend += f"This command does not exist!"
    elif isinstance(error, commands.CommandInvokeError):
        error: Exception = error.original
        if isinstance(error, Fail):
            toSend += error.message
            print(error.message)
        else:
            toSend += f"An unexpected error occurred. Please let {MENTION_ME} know."
            toRaise = error
    else:
        toSend += f"An unexpected error occurred. Please let {MENTION_ME} know."
        toRaise = error
    if toRaise and ctx.guild.id == TEST.ID:
        toSend += f"\n```\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}```"
    if ctx.command:
        toSend += f"\nIf you need help with this command, please use `{BOT_PREFIX}help {ctx.command.qualified_name}`."
    await ctx.send(toSend)
    if toRaise:
        raise toRaise

@client.check
async def globalCheck(ctx: commands.Context):
    channelName = ctx.channel.name if not isinstance(ctx.channel, discord.DMChannel) else "DM"
    print(f"[{str(dt.datetime.now().time())[:-7]}, #{channelName}] {ctx.message.author.name}: {ctx.message.content}")
    return True

with open("./sources/key.txt", "r") as f:
    client.run(f.read())