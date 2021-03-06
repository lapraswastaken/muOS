
from typing import Callable, Mapping, Optional, Union

import discord
import sources.text as T
from back.utils import getMuOSEmbed, paginateDEPR
from discord.ext import commands


def getNonhiddenCommands(ctx: commands.Context, commands: list[commands.Command], getter: Callable[[commands.Command], Union[commands.Command, str]]=lambda x: x) -> list[Union[commands.Command, str]]:
    return [getter(command) for command in commands if all(check(ctx) for check in command.checks)]

class Help(commands.DefaultHelpCommand):
    async def send_bot_help(self, mapping: Mapping[Optional[commands.Cog], list[commands.Command]]):
        pages = []
        cogNames = [cog.qualified_name for cog in mapping if isinstance(cog, commands.Cog) and getNonhiddenCommands(self.context, mapping[cog])]
        for i, cog in enumerate(mapping):
            if not cog: continue
            cmds = getNonhiddenCommands(self.context, mapping[cog], lambda cmd: cmd.qualified_name)
            if not cmds: continue
            pages.append({
                "content": T.HELP.cogPaginationContent(cogNames, i),
                "embed": getMuOSEmbed(**T.HELP.cogEmbed(cog.qualified_name, cog.description, cmds))
            })
        await paginateDEPR(self.context, pages, True)
    
    async def sendPaginatedHelp(self, parentName: str, cmds: list[commands.Command], aliases: Optional[list[str]]=None):
        pages = []
        commandNames = [cmd.qualified_name for cmd in cmds]
        for i, command in enumerate(cmds):
            pages.append({
                "content": T.HELP.commandPaginationContent(parentName, commandNames, i, aliases),
                "embed": getMuOSEmbed(**T.HELP.commandEmbed(command.qualified_name, command.aliases, command.help))
            })
        await paginateDEPR(self.context, pages, True)
    
    async def send_cog_help(self, cog: commands.Cog):
        await self.sendPaginatedHelp(cog.qualified_name, getNonhiddenCommands(self.context, cog.get_commands()))
    
    async def send_group_help(self, group: commands.Group):
        await self.sendPaginatedHelp(group.qualified_name, getNonhiddenCommands(self.context, group.commands), group.aliases)
    
    async def send_command_help(self, command: commands.Command):
        embed = getMuOSEmbed(
            **T.HELP.commandEmbedWithFooter(command.qualified_name, command.aliases, command.help, command.cog_name)
        )
        await self.context.send(embed=embed)
