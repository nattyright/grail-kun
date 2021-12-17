# imports for cog
import math

import discord
from discord.ext import commands, tasks
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


class PostLog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.threads = {}
        self.postlog_channel_id, self.postlog_message_id = get_postlog_message_id()

        # looped task
        self.update_threads.start()

    def init_postlog(self):
        all_channels = self.bot.get_all_channels()
        for channel in all_channels:
            if channel.category.name in ["nature reserve: forest",
                                 "nature reserve: tropic",
                                 "nature reserve: snow",
                                 "nature reserve: swamp",
                                 "nature reserve: desert",
                                 "nature reserve: lake",
                                 "The Canopus",
                                 "Rest of the world"]:
                print(channel)

    @tasks.loop(minutes=1)
    async def update_threads(self):
        await self.update_postlog()

    @update_threads.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:
            for channel in guild.channels:
                if str(channel.category) in ["nature reserve: forest",
                                             "nature reserve: tropic",
                                             "nature reserve: snow",
                                             "nature reserve: swamp",
                                             "nature reserve: desert",
                                             "nature reserve: lake",
                                             "The Canopus",
                                             "Rest of the world"]:
                    last_message = await channel.fetch_message(channel.last_message_id)
                    self.threads[channel.id] = last_message.created_at

    @commands.command()
    async def postlog(self, ctx):
        if not discord.utils.get(ctx.author.roles, name="Global Moderator") is None:
            msg_sent = await ctx.channel.send('Fetching post log...')

            self.postlog_channel_id = msg_sent.channel.id
            self.postlog_message_id = msg_sent.id
            update_postlog_message_id(self.postlog_channel_id, self.postlog_message_id)
            await self.update_postlog()
        else:
            await ctx.channel.send('[MOD ROLE REQUIRED] :*)*')

    @commands.Cog.listener('on_message')
    async def log_new_post(self, message):
        if message.channel.category.name in ["nature reserve: forest",
                                 "nature reserve: tropic",
                                 "nature reserve: snow",
                                 "nature reserve: swamp",
                                 "nature reserve: desert",
                                 "nature reserve: lake",
                                 "The Canopus",
                                 "Rest of the world"]:
            # add/update post time to log
            self.threads[message.channel.id] = message.created_at

            # update displayed log
            await self.update_postlog()

    async def update_postlog(self):

        embed_active_threads = ""
        embed_inactive_threads = ""
        cur_time = datetime.utcnow()

        for channel_id, post_time in self.threads.items():

            time_delta = (cur_time - post_time).total_seconds()
            day_count = divmod(time_delta, 86400)
            hour_count = divmod(day_count[1], 3600)
            minute_count = divmod(hour_count[1], 60)

            text = "<#" + str(channel_id) + ">: last post "
            if day_count[0] > 0:
                text += str(day_count[0]).split(".")[0] + " days, "
            if hour_count[0] > 0:
                text += str(hour_count[0]).split(".")[0] + " hrs, "
            if minute_count[0] > 0:
                text += str(minute_count[0]).split(".")[0] + " mins "
            text += "ago\n"

            # active thread
            if day_count[0] < 7:
                embed_active_threads += text
            # inactive thread
            else:
                embed_inactive_threads += text

        if embed_active_threads == "":
            embed_active_threads = "No active threads."
        if embed_inactive_threads == "":
            embed_inactive_threads = "No inactive threads."

        embed = discord.Embed(title="",
                              color=0)
        embed.add_field(name="Active Threads",
                        value=embed_active_threads,
                        inline=False)
        embed.add_field(name="Inactive Threads",
                        value=embed_inactive_threads,
                        inline=False)

        message = await self.bot.get_channel(self.postlog_channel_id).fetch_message(self.postlog_message_id)
        await message.edit(embed=embed, content="")


def setup(bot: commands.Bot):
    bot.add_cog(PostLog(bot))


def thread_is_active(post_time):
    # last post within 7 days
    cur_time = datetime.utcnow()
    day_count = math.ceil((cur_time - post_time).days)
    return day_count < 7


def get_postlog_message_id():
    with open('data/msg_ids.json', 'r', encoding='utf-8') as to_read:
        data = json.load(to_read)
        return data["postlog"]["chn_id"], data["postlog"]["msg_id"]


def update_postlog_message_id(channel_id, message_id):
    with open('data/msg_ids.json', 'r+', encoding='utf-8') as to_edit:
        data = json.load(to_edit)
        data["postlog"]["chn_id"] = channel_id
        data["postlog"]["msg_id"] = message_id
        # rewrite whole file
        to_edit.seek(0)
        json.dump(data, to_edit)
        to_edit.truncate()