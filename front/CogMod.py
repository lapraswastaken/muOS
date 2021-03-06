
#from __future__ import annotations
# ^ has to be commented out because of some bullshit in the core file
from back.utils import determinePrefix
from typing import Callable, Coroutine, Optional, Type, TypeVar

import discord
import sources.text.mod as M
from back.general import Cmd
from back.ids import IDS, LOG_CHANNEL_IDS, IDs, meCheck
from discord.ext import commands

Ctx = commands.Context

class MiniEntry:
    def __init__(self, userID: int, targetUserID: int, count: int):
        self.userID = userID
        self.targetUserID = targetUserID
        self.count = count

T = TypeVar("T", bound="discord.Snowflake")
class CogMod(commands.Cog, name=M.COG.NAME, description=M.COG.DESCRIPTION):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.oldEntries: dict[int, dict[int, MiniEntry]] = {}
        self.deleteIgnores: set[int] = set()

        self.setup()
    
    def addDeleteIgnore(self, mid: int):
        self.deleteIgnores.add(mid)
    
    async def getNewEntries(self, guild: discord.Guild) -> dict[int, MiniEntry]:
        
        # set an arbitrary number of audit log entries to go through before stopping
        timeout = 300
        newDeleteEntries: dict[int, MiniEntry]  = {}
        entry: discord.AuditLogEntry
        async for entry in guild.audit_logs():
            timeout -= 1
            if timeout <= 0:
                break
            # we don't care about anything except message delete actions
            if not entry.action == discord.AuditLogAction.message_delete: continue
            
            # add the entry as a MiniEntry object to the collection of delete entries
            newDeleteEntries[entry.id] = MiniEntry(entry.user.id, entry.target.id, entry.extra.count)
        return newDeleteEntries
    
    async def onReady(self):
        guild: discord.Guild
        async for guild in self.bot.fetch_guilds(limit=None):
            try:
                self.oldEntries[guild.id] = self.getNewEntries(guild)
            except discord.Forbidden:
                print(f"Missing permission to view audit logs in {guild.name}")
            
    async def onMessageDelete(self, message: discord.Message):
        # we want to ignore the deletion of
        if message.id in self.deleteIgnores:
            # messages that the bot is supposed to ignore (tupper messages and such),
            self.deleteIgnores.discard(message.id)
            return
        if (
            # direct messages,
            isinstance(message.channel, discord.DMChannel) or
            # messages in guilds that don't have a log channel set up,
            not message.guild.id in LOG_CHANNEL_IDS or
            # messages from the bot,
            message.author.id == self.bot.user.id or
            # messages that start with the bot's prefix
            message.content.startswith(determinePrefix(None, message))
        ):
            return
        
        # organize the audit log entries for the message's guild
        oldEntries = self.oldEntries[message.guild.id]
        newEntries = await self.getNewEntries(message.guild)
        
        retrievedDeleterID: Optional[int] = None
        for newID in newEntries:
            newEntry = newEntries[newID]
            # we only care about MiniEntry objects that have the same owner of the
            #  deleted message as the message that triggered this callback
            if not newEntry.targetUserID == message.author.id: continue
            
            # if the entry was processed in an earlier `getNewEntries` call,
            if newID in oldEntries:
                # we need to check if this message deletion has ticked that entry's count up
                oldEntry = oldEntries[newID]
                if newEntry.count == oldEntry.count + 1:
                    retrievedDeleterID = newEntry.userID
                    break
            else:
                # otherwise, it's a new deletion, and things are easy
                retrievedDeleterID = newEntry.userID
                break
        
        if retrievedDeleterID != None and retrievedDeleterID != message.author.id:
            deleter: discord.Member = await message.guild.fetch_member(retrievedDeleterID)
            
            channel: discord.TextChannel = message.guild.get_channel(LOG_CHANNEL_IDS[message.guild.id])
            await channel.send(M.INFO.DELETED_MESSAGE(message.author.id, deleter.id, message.jump_url))
            await channel.send(
                message.content,
                embed=message.embeds[0] if message.embeds else None,
                files=[await attachment.to_file(use_cached=True) for attachment in message.attachments]
            )
        self.oldEntries[message.guild.id] = newEntries
    
    def makeIDChanger(self, check: Callable[[Ctx], bool], listTarget: str, type_: Type[T],
        addMeta: Cmd, addSender: Callable[[Ctx, bool, T], Coroutine],
        rmMeta: Cmd, rmSender: Callable[[Ctx, bool, T], Coroutine],
        idGetter: Callable[[T], int]
    ):
        @commands.command(**addMeta.meta)
        @commands.check(check)
        async def adder(self, ctx: Ctx, *, item: type_):
            res = IDS.add(listTarget, idGetter(item))
            await addSender(ctx, res, item)
        @commands.command(**rmMeta.meta)
        @commands.check(check)
        async def remover(self, ctx: Ctx, *, item: type_):
            res = IDS.remove(listTarget, idGetter(item))
            await rmSender(ctx, res, item)
        adder.cog = self
        remover.cog = self
        self.__cog_commands__ = self.__cog_commands__ + (adder, remover)
    
    def setup(self):
        self.makeIDChanger(
            meCheck, IDs.modRoles, discord.Role,
            M.ADD_MOD_ROLE, lambda ctx, res, role: ctx.send(M.INFO.ADD_MOD_ROLE(role.name, res)),
            M.RM_MOD_ROLE, lambda ctx, res, role: ctx.send(M.INFO.RM_MOD_ROLE(role.name, res)),
            lambda role: role.id
        )
        self.makeIDChanger(
            IDs.modCheck, IDs.dmRoles, discord.Role,
            M.ADD_DM_ROLE, lambda ctx, res, role: ctx.send(M.INFO.ADD_DM_ROLE(role.name, res)),
            M.RM_DM_ROLE, lambda ctx, res, role: ctx.send(M.INFO.RM_DM_ROLE(role.name, res)),
            lambda role: role.id
        )
        self.makeIDChanger(
            IDs.modCheck, IDs.rpChannels, discord.TextChannel,
            M.ADD_RP_CHANNEL, lambda ctx, res, channel: ctx.send(M.INFO.ADD_RP_CHANNEL(channel.id, res)),
            M.RM_RP_CHANNEL, lambda ctx, res, channel: ctx.send(M.INFO.RM_RP_CHANNEL(channel.id, res)),
            lambda channel: channel.id
        )
