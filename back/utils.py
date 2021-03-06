
import json
import random
import re
import emoji
from typing import Optional, Union

import discord
import sources.text.utils as U
from discord.ext import commands

from back.general import BOT_PREFIX, EMPTY, GRAPHICS, stripLines


class Fail(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

def determinePrefix(_: commands.Bot, message: discord.Message):
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

def getRandomAvatarImageAndTime():
    with open(U.PATHS.AVATAR_ROTATION, "r") as f:
        rotation: dict[str, list[tuple[str, str]]] = json.load(f)
    if not rotation.get("unused"):
        rotation["unused"] = list(U.PATHS.AVATARS.items())
    if rotation.get("current") in rotation["unused"]:
        rotation["unused"].remove(rotation.get("current"))

    path = random.choice(rotation["unused"])
    rotation["unused"].remove(path)
    rotation["current"] = path
    with open(U.PATHS.AVATAR_ROTATION, "w") as f:
        json.dump(rotation, f)
    with open(path[1], "rb") as im:
        return im.read()

dashPat = re.compile(r"-")
spacePat = re.compile(r"\s+")
ePat = re.compile(r"e")
def shuffleWord(word):
    alphabet = "qwertyuiopasdfghjklzxcvbnm"
    alphanum = "1234567890qwertyuiopasdfghjklzxcvbnm"
    splits     = [(word[:i], word[i:]) for i in range(len(word) + 1)]
    deletes    = [a + b[1:] for a, b in splits if b]
    transposes = [a + b[1] + b[0] + b[2:] for a, b in splits if len(b)>1]
    replaces   = [a + c + b[1:] for a, b in splits for c in alphabet if b]
    inserts    = [a + c + b     for a, b in splits for c in alphabet]
    shuffles = set(deletes + transposes + replaces + inserts)
    for w in ["".join(let for let in shuffle if let in alphanum) for shuffle in shuffles]: shuffles.add(w)
    for w in [re.sub(dashPat, " ", shuffle) for shuffle in shuffles]: shuffles.add(w)
    for w in [re.sub(spacePat, "-", shuffle) for shuffle in shuffles]: shuffles.add(w)
    for w in [re.sub(ePat, "\u00e9", shuffle) for shuffle in shuffles]: shuffles.add(w) # accented e (for flabebe)
    return shuffles

def getEmbed(*,
    title: str=None, description: str=None, fields: list[Union[tuple[str, str], tuple[str, str, bool]]]=None,
    image: str=None, footer=None, url=None, thumbnail=None, color=0xD67AE2, author=None,
    noStrip: bool=False
):
    """ Creates a custom embed. """
    
    if not description: description = ""
    if not fields: fields = []
    
    e = discord.Embed(
        title=title,
        description=stripLines(description)
    )
    for field in fields:
        e.add_field(
            name=field[0],
            value=EMPTY if not len(field) >= 2 else field[1],
            inline=False if not len(field) == 3 else field[2]
        )
    if author:      e.author = author
    if color:       e.color = color
    if description: e.description = description if noStrip else stripLines(description)
    if footer:      e.set_footer(text=footer)
    if image:       e.set_image(url=image)
    if thumbnail:   e.set_thumbnail(url=thumbnail)
    if url:         e.url = url
    return e

def getMuOSEmbed(*, title: str, description: str=None, fields: list[Union[tuple[str, str], tuple[str, str, bool]]]=None, imageURL: str=None, footer=None, url=None, thumbnail=None, author=None):
    if not thumbnail: thumbnail = random.choice(GRAPHICS)
    e = getEmbed(title=title, description=description, fields=fields, image=imageURL, footer=footer, url=url, thumbnail=thumbnail, author=author)
    return e

emojiPat = re.compile(r"(<:\w+:\d+>)")
def getEmojisFromText(text: str):
    emojis: list[str] = []
    for char in text:
        if char in emoji.UNICODE_EMOJI_ENGLISH:
            emojis.append(char)
    for match in emojiPat.findall(text):
        emojis.append(match)
    return emojis
class Page:
    def __init__(self, content: Optional[str]=None, embed: Optional[discord.Embed]=None):
        self.content = content
        self.embed = embed

class Paginator:
    pages: list[Page]
    issuerID: int
    ignoreIndex: bool
    isDM: bool
    length: int
    focused: int
    locked: bool
    changing: bool
    numbers: bool
    
    def __init__(self, pages: list[Page], issuerID: int, *, ignoreIndex: bool, isDM: bool):
        self.pages = pages
        self.issuerID = issuerID
        self.ignoreIndex = ignoreIndex
        self.isDM = isDM
        
        self.length = len(self.pages)
        self.focused = 0
        self.locked = False if not isDM else True
        self.changing = False
        self.numbers = False
    
    def updateFooter(self):
        if not self.ignoreIndex:
            for i, page in enumerate(self.pages):
                if not page.embed:
                    page.embed = discord.Embed(
                        title=EMPTY,
                        description=U.paginationIndex(i + 1, self.length, self.locked)
                    )
                else:
                    page.embed.set_footer(
                        text=U.paginationIndex(i + 1, self.length, self.locked)
                    )
    
    def lock(self):
        self.locked = True
        self.updateFooter()
    def unlock(self):
        self.locked = False
        self.updateFooter()
    
    def setChanging(self):
        self.changing = True
    
    def unsetChanging(self):
        self.changing = False
    
    def getReactions(self):
        reactions = []
        amLarg = self.length > len(U.indices)
        
        if self.numbers and not amLarg:
            reactions = U.indices[:self.length]
        else:
            reactions = U.arrows
        
        if not self.isDM and not amLarg:
            reactions.append(U.switches[int(self.numbers)])
            reactions.append(U.emojiUnlock if self.locked else U.emojiLock)
        
        return reactions
    
    async def refocus(self, emoji: str, message: discord.Message):
        if emoji == U.emojiFirst:
            self.focused = 0
        elif emoji == U.emojiPrior and self.focused > 0:
            self.focused -= 1
        elif emoji == U.emojiNext and self.focused < self.length - 1:
            self.focused += 1
        elif emoji == U.emojiLast:
            self.focused = self.length - 1
            
        elif emoji in U.indices:
            self.focused = U.indices.index(emoji)
        elif emoji in U.switches and not self.isDM:
            await message.clear_reactions()
            self.numbers = not self.numbers
        elif emoji == U.emojiLock and not self.isDM:
            self.lock()
        elif emoji == U.emojiUnlock and not self.isDM:
            self.unlock()
        
        return self.getFocused()
    
    def getFocused(self):
        return self.pages[self.focused]
    

class DictPaginator(Paginator):
    pages: dict[str, list[Page]]

    def __init__(self, pages: dict[str, list[Page]], issuerID: int, startFocused: str):
        self.pages = pages
        self.issuerID = issuerID
        self.ignoreIndex = True

        self.focused = startFocused
        self.subFocused = 0
    
    def getReactions(self, _):
        reactions = self.pages.keys()
        if len(self.pages[self.focused]) > 1:
            reactions += U.smolArrows
        return reactions
    
    def refocus(self, emoji: str):
        if emoji in self.pages:
            self.focused = emoji
        elif emoji == U.emojiPrior and self.subFocused > 0:
            self.subFocused -= 1
        elif emoji == U.emojiNext and self.subFocused < len(self.pages[self.focused]):
            self.subFocused += 1
        
        return self.getFocused()
    
    def getFocused(self):
        return self.pages[self.focused][self.subFocused]


toListen: dict[int, Paginator] = {}
        
async def updatePaginatedMessage(message: discord.Message, user: discord.User, paginator: Paginator, emoji: Optional[str]=None):
    if not user.id == paginator.issuerID: return
    paginator.setChanging()
    oldFocused = paginator.getFocused()
    if emoji:
        if not isinstance(message.channel, discord.DMChannel):
            await message.remove_reaction(emoji, user)
        focused = await paginator.refocus(emoji, message)
        if not oldFocused is focused:
            await message.edit(content=focused.content, embed=focused.embed)
    
    newReactions = paginator.getReactions()
    for reaction in newReactions:
        await message.add_reaction(reaction)
    paginator.unsetChanging()

_RawPagesDEPR = list[dict[str, Union[str, discord.Embed]]]
async def paginateDEPR(ctx: commands.Context, contents: _RawPagesDEPR, ignoreIndex: bool=False):
    pages = []
    for page in contents:
        pages.append(Page(**page))
    if not pages:
        raise IndexError("No pages were given to the pagination function.")
    
    paginator = Paginator(pages, ctx.author.id, ignoreIndex=ignoreIndex, isDM=isinstance(ctx.channel, discord.DMChannel))
    await sendPaginator(ctx, paginator)

RawEmbed = dict[str, Union[str, tuple[str, str], tuple[str, str, bool]]]
RawPage = Union[str, RawEmbed, tuple[str, RawEmbed]]
RawPages = list[RawPage]
def buildRawPage(page: RawPage):
    if isinstance(page, str):
        return Page(content=page)
    if isinstance(page, dict):
        return Page(embed=getMuOSEmbed(**page))
    if isinstance(page, (list, tuple)):
        return Page(content=page[0], embed=getMuOSEmbed(**page[1]))

async def paginate(ctx: commands.Context, contents: RawPages, *, ignoreIndex: bool=False):
    pages = []
    for page in contents:
        pages.append(buildRawPage(page))
    paginator = Paginator(pages, ctx.author.id, ignoreIndex=ignoreIndex, isDM=isinstance(ctx.channel, discord.DMChannel))
    await sendPaginator(ctx, paginator)

DictPages = dict[str, RawPages]
async def paginateDict(ctx: commands.Context, contents: DictPages, startFocused = str):
    pages: dict[str, list[Page]] = {}
    for emoji in contents:
        pages[emoji] = []
        for page in contents[emoji]:
            pages[emoji].append(buildRawPage(page))
    if not pages:
        raise IndexError("No pages were given to the pagination function.")
    
    paginator = DictPaginator(pages, ctx.author.id, startFocused)
    await sendPaginator(ctx, paginator)

async def sendPaginator(ctx: commands.Context, paginator: Paginator):
    focused = paginator.getFocused()
    message: discord.Message = await ctx.send(content=focused.content, embed=focused.embed)
    if len(paginator.pages) == 1: return
    toListen[message.id] = paginator
    await updatePaginatedMessage(message, ctx.author, paginator)

async def onReaction(message: discord.Message, emoji: str, user: Union[discord.Member, discord.User]):
    if user.bot or not message.id in toListen: return
    paginator = toListen[message.id]
    
    emoji = str(emoji)
    await updatePaginatedMessage(message, user, paginator, emoji)
