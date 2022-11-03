# imports for cog
import discord
from discord.ext import commands


class AutoReply(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if 'where' in message.content and 'submit' in message.content:
            member_id = message.author.id
            member = '<@' + str(member_id) + '>'
            template_channel = '<#763707512092098647>'
            submission_channel = '<#763707512251088923>'
            await message.channel.send(member +
                                       'sheet submission is at...' +
                                       submission_channel +
                                       '~!')
        if 'brap' in message.content.lower().replace(" ", ""):
            member_id = message.author.id
            member = '<@' + str(member_id) + '>'
            await message.channel.send('shuddup' + member)

    @commands.command()
    async def newhelp(self, ctx):
        server_rp_rules = '<#763707512092098640>'
        big_faq_island = '<#763707512092098646>'
        writing_guidelines = '<#763707512092098648>'

        char_guidelines = '<#763707512092098647>'
        servant_params = '<#773182122906615840>'
        server_lore = '<#763707512251088921>'
        char_help = '<#827268213888253983>'

        cur_season_rules = '<#898904085066047508>'
        cur_season_map = '<#915634205923373116>'
        cur_season_plot = '<#904808272933044226>'
        cur_season_chars = '<#789127219371966535>'

        past_rp_archive = '<#763707512415191061>'
        past_season_chars = '<#763707512251088922>'

        str1 = "Ding ding! Your starter package has arrived!\n\n"

        str2 = "__Rules and FAQs__\n"
        str3 = "Before you start, please read " + \
        server_rp_rules + ", " + big_faq_island + ", and " + writing_guidelines + \
        ". All rules are final and will not be disputed, so please make sure this " + \
        "server provides exactly what you need.\n\n"

        str4 = "__Character Creation__\n"
        str5 = "For character creation rules and templates, please use " + \
        char_guidelines + " and " + servant_params + ". It is strongly encouraged that " + \
        "you give " + server_lore + " a read as well, as many questions can be answered " + \
        "with our lore. If you have any additional questions regarding character " + \
        "creation, please use " + char_help + ". Mods and other members will do their " + \
        "best to provide assistance.\n\n"

        str6 = "__Current Season Info__\n"
        str7 = "For additional lore and rules on the current season, you may look at " + \
        cur_season_rules + ", " + cur_season_map + ", and " + cur_season_plot + \
        ". Approved character sheets for the current season can be found at " + \
        cur_season_chars + ".\n\n"

        str8 = "__Past Seasons__\n"
        str9 = "If you want to take a look at our past RPs and character sheets, they can be " + \
        "found at " + past_rp_archive + " and " + past_season_chars + "."

        await ctx.channel.send(str1 +
                               str2 +
                               str3 +
                               str4 +
                               str5 +
                               str6 +
                               str7 +
                               str8 +
                               str9)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoReply(bot))
