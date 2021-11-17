# imports for cog
import math

import discord
from discord.ext import commands
from io import BytesIO

# imports for gacha
from datetime import datetime

import json
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw

TRACKER_PATH = 'data/images/tracker/'

with open("data/images/tracker/tracker.json", "r", encoding="utf-8") as to_read:
    TRACKER_DATA = json.load(to_read)


class ActivityTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def clockin(self, ctx):
        if not discord.utils.get(ctx.author.roles, name="Administrator") is None:
            try:
                id = str(ctx.message.mentions[0].id)
                name = ctx.message.mentions[0].display_name

                if id not in TRACKER_DATA:
                    TRACKER_DATA[id] = {}
                    TRACKER_DATA[id]['NAME'] = name
                    TRACKER_DATA[id]['ACTIVITY'] = [get_cycle_count()]
                else:
                    TRACKER_DATA[id]['NAME'] = name
                    if TRACKER_DATA[id]['ACTIVITY'][-1] != get_cycle_count():
                        TRACKER_DATA[id]['ACTIVITY'].append(get_cycle_count())

                await ctx.channel.send('Tracker updated')

                with open('data/images/tracker/tracker.json', 'r+', encoding='utf-8') as to_edit:
                    to_edit.seek(0)
                    json.dump(TRACKER_DATA, to_edit)
                    to_edit.truncate()
            except IndexError:
                await ctx.channel.send('Format: `f.clockin @user`')

        else:
            await ctx.channel.send('[ADMIN ROLE REQUIRED] :*)*')

    @commands.command()
    async def clockinimg(self, ctx):
        img = get_base_tracker_image()
        with BytesIO() as image_binary:
            img.save(image_binary, 'PNG')
            image_binary.seek(0)
            await ctx.channel.send(content=None, file=discord.File(fp=image_binary, filename='image.png'))


    @commands.command()
    async def clockindel(self, ctx):
        if not discord.utils.get(ctx.author.roles, name="Administrator") is None:
            try:
                id = str(ctx.message.mentions[0].id)
                name = ctx.message.mentions[0].display_name

                if id not in TRACKER_DATA:
                    await ctx.channel.send("Participant does not exist")
                else:
                    try:
                        TRACKER_DATA[id]['ACTIVITY'].remove(get_cycle_count())
                        await ctx.channel.send('Tracker updated')
                    except ValueError:
                        await ctx.channel.send('Nothing to delete')

                with open('data/images/tracker/tracker.json', 'r+', encoding='utf-8') as to_edit:
                    to_edit.seek(0)
                    json.dump(TRACKER_DATA, to_edit)
                    to_edit.truncate()
            except IndexError:
                await ctx.channel.send('Format: `f.clockin @user`')

        else:
            await ctx.channel.send('[ADMIN ROLE REQUIRED] :*)*')


def setup(bot: commands.Bot):
    bot.add_cog(ActivityTracker(bot))


def get_cycle_count():
    year, month, day = TRACKER_DATA["s3startdate"]
    start_date = datetime(year, month, day)
    cur_date = datetime.now()
    cycle_count = math.ceil((cur_date - start_date).days / 7)
    return cycle_count


def get_base_tracker_image():
    cycle = get_cycle_count()
    bg = Image.open(TRACKER_PATH + 'bg.png')
    marker = Image.open(TRACKER_PATH + 'tri_' + str(cycle) + '.png')
    bg.paste(marker, (0, 0), marker)
    count = 1

    for k, v in TRACKER_DATA.items():
        if k != "s3startdate":
            font = ImageFont.truetype(TRACKER_PATH + 'Helvetica-Bold.ttf', 24)
            msg = v['NAME']

            # checkboxes
            check_b = Image.open(TRACKER_PATH + 'check_black.png')
            check_r = Image.open(TRACKER_PATH + 'check_red.png')
            for c in v['ACTIVITY']:
                bg.paste(check_b, (225 + (c - 1) * 41, 37 + count * 39), check_b)
            if (cycle - v['ACTIVITY'][-1]) > 2:
                bg.paste(check_r, (225 + (v['ACTIVITY'][-1] - 1) * 41, 37 + count * 39), check_r)

            # labels
            # red: 3 weeks deadline
            if (cycle - v['ACTIVITY'][-1]) > 2:
                label = Image.open(TRACKER_PATH + 'label_red.png')
                bg_draw = ImageDraw.Draw(label)
            # black: no deadline yet
            else:
                label = Image.open(TRACKER_PATH + 'label_black.png')
                bg_draw = ImageDraw.Draw(label)

            W, H = 186, 7
            w, h = bg_draw.textsize(msg, font=font)
            bg_draw.text(((W - w) / 2, H), msg,
                         font=font, fill='rgb(255, 255, 255)')

            bg.paste(label, (37, 37 + count * 39), label)
            count += 1

    # bg.show()
    return bg
