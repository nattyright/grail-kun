import asyncio

import aiohttp
import discord
import os
from dotenv import load_dotenv
from discord.ext.commands import Bot
from discord.ext import commands, tasks
from discord.ui import Select
import mongodb_client

# setup mongodb database
db = mongodb_client.get_database('grail-kun')
db_fan_servants = mongodb_client.get_database('fan-servants')

# setup bot env
load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.all()
intents.members = True
client = commands.Bot(command_prefix="f.", help_command=None, intents=intents)


"""
@client.event
async def on_ready():
    # add db
    client.db = db
    client.db_fan_servants = db_fan_servants

    # on ready message
    print('We have logged in as {0.user}'.format(client))

    # load cogs
    for folder in os.listdir("modules"):
        for file in os.listdir("modules/" + folder):
            if file.startswith("cog"):
                await client.load_extension(f"modules.{folder}.{file[:-3]}")

    # set status message
    await client.change_presence(activity=discord.Game('fateRP bot | f.help'))
"""



class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="f.", help_command=None, intents=intents)

    async def setup_hook(self):
        self.background_task.start()
        self.session = aiohttp.ClientSession()
        # load cogs
        for folder in os.listdir("modules"):
            for file in os.listdir("modules/" + folder):
                if file.startswith("cog"):
                    await self.load_extension(f"modules.{folder}.{file[:-3]}")

    async def close(self):
        await super().close()
        await self.session.close()

    @tasks.loop(minutes=10)
    async def background_task(self):
        print('Running background task...')

    async def on_ready(self):
        # add db
        self.db = db
        self.db_fan_servants = db_fan_servants

        # sync slash commands
        await self.tree.sync()

        # on ready message
        print('We have logged in as {0.user}'.format(self))
        print('Ready!')

bot = MyBot()
bot.run(TOKEN)