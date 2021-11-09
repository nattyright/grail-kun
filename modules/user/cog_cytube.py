from discord.ext import commands
import os


class Cytube(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def cytube2(self, ctx, show_type, source, episode=""):
        if show_type == 'anime':
            command = "ssh -i .credentials/id_rsa root@135.148.2.69 'anime dl "
            command += '"' + source + '" --episodes ' + episode
            command += "'"
        else:
            command = "ssh -i .credentials/id_rsa root@135.148.2.69 'cd /var/www/h5ai && " + \
                      "./_h5ai/private/annie " + source + "'"
        os.system(command)


def setup(bot: commands.Bot):
    bot.add_cog(Cytube(bot))