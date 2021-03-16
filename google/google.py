import functools
import urllib
from collections import namedtuple

import aiohttp
import discord
from io import BytesIO
from html2text import html2text as h2t
from bs4 import BeautifulSoup
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils import menus


# TODO Add optional way to use from google search api


nsfwcheck = lambda ctx: (not ctx.guild) or ctx.channel.is_nsfw()


class Google(commands.Cog):
    """
    A Simple google search with image support as well
    A fair bit of querying stuff is taken from  Kowlin's cog - https://github.com/Kowlin/refactored-cogs
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def google(self, ctx, *, query: str = None):
        """Search in google from discord"""
        if not query:
            await ctx.send("Please enter something to search")
        else:
            isnsfw = nsfwcheck(ctx)
            async with ctx.typing():
                response = await self.get_result(query, nsfw=isnsfw)
                pages = []
                groups = [response[0][n : n + 3] for n in range(0, len(response[0]), 3)]
                for num, group in enumerate(groups, 1):
                    emb = discord.Embed(title=f"Google Search: {query[:50]}...")
                    for result in group:
                        desc = (
                            f"[{result.url[:60]}]({result.url})\n" if result.url else ""
                        ) + f"{result.desc}"[:1024]
                        emb.add_field(
                            name=f"{result.title}",
                            value=desc or "Nothing",
                            inline=False,
                        )
                    emb.description = f"Page {num} of {len(groups)}"
                    emb.set_footer(
                        text=f"Safe Search: {not isnsfw} | " + response[1].replace("\n", " ")
                    )
                    pages.append(emb)
            if pages:
                await menus.menu(ctx, pages, controls=menus.DEFAULT_CONTROLS)
            else:
                await ctx.send("No result")

    @google.command(aliases=["img"])
    async def image(self, ctx, *, query: str = None):
        """Search google images from discord"""
        if not query:
            await ctx.send("Please enter some image name to search")
        else:
            isnsfw = nsfwcheck(ctx)
            async with ctx.typing():
                response = await self.get_result(query, images=True, nsfw=isnsfw)
                size = len(tuple(response))
                pages = []
                for i, j in enumerate(response, 1):
                    pages.append(
                        discord.Embed(title=f"Pages: {i}/{size}")
                        .set_image(url=j)
                        .set_footer(text=f"Safe Search: {not isnsfw}")
                    )
            if pages:
                await menus.menu(ctx, pages, controls=menus.DEFAULT_CONTROLS)
            else:
                await ctx.send("No result")

    @commands.is_owner()
    @google.command(hidden=True)
    async def debug(self, ctx, *, url):
        options = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=options) as resp:
                text = await resp.text()
        f = BytesIO(bytes(text, "utf-8"))
        await ctx.send(file=discord.File(f, filename="filename.html"))
        f.close()

    def parser_text(self, text):
        """My bad logic for scraping"""
        soup = BeautifulSoup(text, features="html.parser")
        s = namedtuple("searchres", "url title desc")
        final = []
        stats = h2t(str(soup.find("div", id="result-stats")))

        def get_card():
            """Getting cards if present, here started the pain"""
            # common card
            if card := soup.find("div", class_="g mnr-c g-blk"):
                if desc := card.find("span", class_="hgKElc"):
                    final.append(s(None, "Google Info Card:", h2t(str(desc))))
                    return

            # calculator card
            if card := soup.find("div", class_="tyYmIf"):
                if question := card.find("span", class_="vUGUtc"):
                    if answer := card.find("span", class_="qv3Wpe"):
                        tmp = h2t(str(question)).strip("\n")
                        final.append(
                            s(None, "Google Calculator:", f"**{tmp}** {h2t(str(answer))}")
                        )
                        return

            # sidepage card
            if card := soup.find("div", class_="liYKde g VjDLd"):
                if title := soup.find("div", class_="SPZz6b"):
                    if desc := card.find("div", class_="kno-rdesc"):
                        if remove := desc.find(class_="Uo8X3b"):
                            remove.decompose()
                        final.append(
                            s(
                                None,
                                "Google Featured Card: "
                                + h2t(str(title)).replace("\n", " ").replace("#", ""),
                                h2t(str(desc)),
                            )
                        )
                        return

            # time cards (or more)
            if card := soup.find("div", class_="vk_c"):
                if tail := card.find("table", class_="d8WIHd"):
                    tail.decompose()
                tmp = h2t(str(card)).replace("\n\n", "\n").split("\n")
                final.append(s(None, tmp[0], "\n".join(tmp[1:])))
                return

            # translator cards
            if card := soup.find("div", class_="tw-src-ltr"):
                langs = soup.find("div", class_="pcCUmf")
                src_lang = "**" + langs.find("span", class_="source-language").text + "**"
                dest_lang = "**" + langs.find("span", class_="target-language").text + "**"
                final_text = ""
                if source := card.find("div", id="KnM9nf"):
                    final_text += (
                        src_lang
                        + "\n`"
                        + source.find("div", class_="tw-ta-container hide-focus-ring tw-nfl")
                        .find("textarea")
                        .text
                    ) + "`\n"

                if dest := card.find("div", id="kAz1tf"):
                    final_text += dest_lang + "\n`" + h2t(str(dest.find("span"))).strip("\n") + "`"
                final.append(s(None, "Google Translator", final_text))
                return

            # Unit conversions
            if card := soup.find("div", class_="nRbRnb"):
                final_text = "\N{ZWSP}\n**"
                if source := card.find("div", class_="vk_sh c8Zgcf"):
                    final_text += h2t(str(source)).strip("\n")
                if dest := card.find("div", class_="dDoNo ikb4Bb vk_bk gsrt gzfeS"):
                    final_text += " " + h2t(str(dest)).strip("\n") + "**"
                if time := card.find("div", class_="hqAUc"):
                    tmp = h2t(str(time)).replace("\n", " ").split("·")
                    final_text += (
                        "\n"
                        + (f"`{tmp[0].strip()}` ·{tmp[1]}" if len(tmp) == 2 else "·".join(tmp))
                        + "\n\N{ZWSP}"
                    )
                final.append(s(None, "Unit Conversion", final_text))

            # Definition cards
            if card := soup.find("div", class_="KIy09e"):
                final_text = ""
                if word := card.find("div", class_="DgZBFd XcVN5d frCXef"):
                    final_text += "`" + word.text + "`"
                if pronounciate := card.find("div", class_="S23sjd g30o5d"):
                    final_text += "   |   " + pronounciate.text
                if type_ := card.find("div", class_="pgRvse vdBwhd ePtbIe"):
                    final_text += "   |   " + type_.text + "\n\n"
                if definition := card.find("div", class_="L1jWkf h3TRxf"):
                    for text in definition.findAll("div")[:2]:
                        final_text += "`" + h2t(str(text)).strip("\n") + "`" + "\n"
                final.append(s(None, "Definition", final_text))

        get_card()
        for res in soup.findAll("div", class_="g"):
            if name := res.find("div", class_="yuRUbf"):
                url = name.a["href"]
                if title := name.find("h3", "LC20lb DKV0Md"):
                    title = title.text
                else:
                    title = url
            else:
                url = None
                title = None
            if desc := res.find("div", class_="IsZvec"):
                if remove := desc.find("span", class_="f"):
                    remove.decompose()
                desc = h2t(str(desc.find("span", class_="aCOpRe")))
            else:
                desc = "Not found"
            if title:
                final.append(s(url, title, desc))
        return final, stats

    def parser_image(self, html):
        soup = BeautifulSoup(html, features="html.parser")
        return [x.get("src", "https://http.cat/404") for x in soup.findAll("img", class_="t0fcAb")]

    async def get_result(self, query, images=False, nsfw=False):
        """Fetch the data"""
        # TODO make this fetching a little better
        encoded = urllib.parse.quote_plus(query, encoding="utf-8", errors="replace")
        options = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.169 Safari/537.36"
        }
        if not nsfw:
            encoded += "&safe=active"
        if not images:
            url = "https://www.google.com/search?q="
            async with aiohttp.ClientSession() as session:
                async with session.get(url + encoded, headers=options) as resp:
                    text = await resp.text()
            prep = functools.partial(self.parser_text, text)
        else:
            # TYSM fixator, for the non-js query url
            url = "https://www.google.com/search?tbm=isch&sfr=gws&gbv=1&q="
            async with aiohttp.ClientSession() as session:
                async with session.get(url + encoded, headers=options) as resp:
                    text = await resp.text()
            prep = functools.partial(self.parser_image, text)
        return await self.bot.loop.run_in_executor(None, prep)
