import discord
import os
from dotenv import load_dotenv
from discord.ext.commands import Bot
from discord_components import DiscordComponents
import mongodb_client

# setup mongodb database
db = mongodb_client.get_database()

# setup bot env
load_dotenv()
TOKEN = os.getenv("TOKEN")

client = Bot(command_prefix="f.", help_command=None)
# buttons and select option (not in official discord.py yet
DiscordComponents(client)


@client.event
async def on_ready():
    # add db
    client.db = db

    # load cogs
    for folder in os.listdir("modules"):
        for file in os.listdir("modules/" + folder):
            if file.startswith("cog"):
                client.load_extension(f"modules.{folder}.{file[:-3]}")

    # on ready message
    print('We have logged in as {0.user}'.format(client))

    # set status message
    await client.change_presence(activity=discord.Game('fateRP bot | f.help'))


client.run(TOKEN)
