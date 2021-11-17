import discord
from discord.ext import commands


class Help(commands.Cog):
    HELP_MESSAGE_TEMPLATE = {
        "embeds": [
            {
                "title": "Help Message",
                "color": 0,
                "fields": [
                    {"name": "Admin Commands",
                     "value": "```f.calendar```Fetch server calendar.```f.clockin @user``````f.clockindel @user``````f.clockinimg```S3 activity tracker"},
                    {"name": "User Commands",
                     "value": "```f.multi```Salt sim (weak-willed).```f.single```Salt sim (strong-willed).```f.cytube```[type] [source] [ep(optional)]"}
                ]
            }
        ]
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def help(self, ctx):
        discord_embed = Help.HELP_MESSAGE_TEMPLATE

        embed = discord.Embed(title="",
                              color=0)
        embed.add_field(name="Admin Commands",
                        value=discord_embed["embeds"][0]["fields"][0]["value"],
                        inline=False)
        embed.add_field(name="User Commands",
                        value=discord_embed["embeds"][0]["fields"][1]["value"],
                        inline=False)
        await ctx.channel.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Help(bot))