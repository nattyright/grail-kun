import discord
from discord.ext import commands


class Help(commands.Cog):
    HELP_MESSAGE_TEMPLATE = {
        "embeds": [
            {
                "title": "Help Message",
                "color": 0,
                "fields": [
                    {"name": "Mod Commands",
                     "value": "*Server Management*\n"
                              "`        f.calendar:` fetch server calendar in the current channel\n"
                              "`      f.jail @user:` drop @user in the unhorny jail\n"
                              
                              "*Sheet Review*\n"
                              "`    f.review @user:` create hidden review channel for mods and @user\n"
                              
                              "*Season 3 RP Management*\n"
                              "`   f.checkin @user:` check-in @user for the current cycle\n"
                              "`f.checkindel @user:` remove check-in for @user for the current cycle\n"
                              "`      f.checkinimg:` display season 3 activity tracker\n"},

                    {"name": "User Commands",
                     "value": "*Server Gacha*\n"
                              "` f.multi:` salt simulator (weak-willed)\n"
                              "`f.single:` salt simulator (strong-willed)\n"
                              "` f.stats:` salt simulator stats (soul crushing)\n"
                              "*Misc.*\n"
                              "`f.cytube:` [type] [source] [ep(optional)]"}
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

        for item in discord_embed["embeds"][0]["fields"]:
            embed.add_field(name=item["name"],
                            value=item["value"],
                            inline=False)

        await ctx.channel.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Help(bot))