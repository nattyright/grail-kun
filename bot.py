import asyncio
import aiohttp
import discord
import os
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord.ui import Select
import mongodb_client
from typing import Optional


class GrailBot(commands.Bot):
    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.token = os.getenv("TOKEN")
        if not self.token:
            raise ValueError("Bot token not found in environment variables")
        
        # Initialize intents
        intents = discord.Intents.all()
        intents.members = True

        # Call parent constructor
        super().__init__(
            command_prefix="f.", 
            help_command=None, 
            intents=intents,
            description="Starry Night RP Discord Bot"
        )

        # Initialize database connections
        # setup mongodb database
        self.db = mongodb_client.get_database('grail-kun')
        self.db_fan_servants = mongodb_client.get_database('fan-servants')
        self.sessions: Optional[aiohttp.ClientSession] = None


    async def setup_hook(self) -> None:
        """
        Initialize bot settings and load extensions.
        """
        try:
            # Create aiohttp sessions
            self.session = aiohttp.ClientSession()
            # Load all cogs
            await self.load_cogs()
            # Start background tasks
            self.background_task.start()
        except Exception as e:
            print(f"Error in setup: {str(e)}")
            raise


    async def load_cogs(self) -> None:
        """
        Load all cogs from the modules directory.
        """
        loaded_cogs = 0
        for folder in os.listdir("modules"):
            folder_path = os.path.join("modules", folder)
            if not os.path.isdir(folder_path):
                continue

            for file in os.listdir(folder_path):
                if file.startswith("cog") and file.endswith(".py"):
                    try:
                        await self.load_extension(f"modules.{folder}.{file[:-3]}")
                        loaded_cogs += 1
                    except Exception as e:
                        print(f"Failed to load extension {file}: {str(e)}")
        
        print(f"Successfully loaded {loaded_cogs} cogs")


    async def close(self):
        """
        Clean up resources on bot shutdown.
        """
        if self.session:
            await self.session.close()
        await super().close()


    @tasks.loop(minutes=10)
    async def background_task(self) -> None:
        """
        Background tasks that run every 10 minutes.
        """
        try:
            print('Running background tasks...')
            # placeholder background tasks
        except Exception as e:
            print(f"Error in background task: {str(e)}")


    @background_task.before_loop
    async def before_background_task(self) -> None:
        """
        Wait for bot to be ready before starting background tasks.
        """
        await self.wait_until_ready()


    async def on_ready(self) -> None:
        """
        Handler for when the bot is ready.
        """
        try:
            # Sync slash commands
            await self.tree.sync()
            # Set status
            await self.change_presence(
                activity=discord.Game('StarryNight Bot | f.help')
            )

            print(f"Logged in as {self.user} (ID: {self.user.id})")
            print("Ready!")
        except Exception as e:
            print(f"Error in on_ready: {str(e)}")
        

def main():
    """
    Main entry point for the bot.
    """
    try:
        bot = GrailBot()
        bot.run(bot.token)
    except Exception as e:
        print(f"Failed to start bot: {str(e)}")


if __name__ == "__main__":
    main()