# imports for cog
import discord
from discord.ext import commands
import json


class SheetReview(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def review(self, ctx):
        if not discord.utils.get(ctx.author.roles, name="Global Moderator") is None:
            try:
                # get member
                member_id = str(ctx.message.mentions[0].id)
                member = await ctx.guild.fetch_member(member_id)
                channel_name = "hidden review " + member.name

                # create new private channel as 'hidden review member_name'
                # make channel private and only viewable to mods + the member
                mod_role = discord.utils.get(ctx.guild.roles, name='Global Moderator')

                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    member: discord.PermissionOverwrite(read_messages=True),
                    mod_role: discord.PermissionOverwrite(read_messages=True)
                }

                category = discord.utils.get(ctx.guild.categories, name='getting started')
                channel = await ctx.guild.create_text_channel(channel_name,
                                                              category=category,
                                                              overwrites=overwrites)

            except IndexError:
                await ctx.channel.send('Format: `f.review @user`')
        else:
            await ctx.channel.send('[MOD ROLE REQUIRED] :*)*')


async def setup(bot: commands.Bot):
    await bot.add_cog(SheetReview(bot))
