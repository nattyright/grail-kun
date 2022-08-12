# imports for cog
import discord
from discord.ext import commands
import json


class Jail(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def jail(self, ctx):
        if not discord.utils.get(ctx.author.roles, name="Global Moderator") is None:
            try:
                # get member
                id = str(ctx.message.mentions[0].id)
                member = await ctx.guild.fetch_member(id)

                # check if member is already in jail
                already_jailed = False
                for role in member.roles:
                    if role.name == "unhorny jail":
                        already_jailed = True

                if not already_jailed:
                    # save current roles to database
                    roles = []
                    for role in member.roles:
                        if role.name != "@everyone":
                            roles.append(role.id)
                    self.save_roles_to_database(id, roles)

                    # remove current roles
                    for role in member.roles:
                        if role.name != "@everyone":
                            await member.remove_roles(role, reason='Being unhorny', atomic=True)

                    # add jail role
                    role = discord.utils.get(ctx.guild.roles, name='unhorny jail')
                    await member.add_roles(role, reason='Being unhorny', atomic=True)

                else:
                    await ctx.channel.send('Member is already in jail')

            except IndexError:
                await ctx.channel.send('Format: `f.jail @user`')
        else:
            await ctx.channel.send('[MOD ROLE REQUIRED] :*)*')

    @commands.command()
    async def unjail(self, ctx):
        if not discord.utils.get(ctx.author.roles, name="Global Moderator") is None:
            try:
                # get member
                id = str(ctx.message.mentions[0].id)
                member = await ctx.guild.fetch_member(id)

                # check if member is actually in jail
                already_jailed = False
                for role in member.roles:
                    if role.name == "unhorny jail":
                        already_jailed = True

                if already_jailed:
                    # remove jail role
                    role = discord.utils.get(ctx.guild.roles, name='unhorny jail')
                    await member.remove_roles(role, reason='No longer unhorny', atomic=True)

                    # get previous roles from database
                    role_ids = self.get_roles_from_database(id)

                    # add previous roles
                    for role_id in role_ids:
                        role = discord.utils.get(ctx.guild.roles, id=int(role_id))
                        await member.add_roles(role, reason='No longer unhorny', atomic=True)
                else:
                    await ctx.channel.send('Member is not in jail')

            except IndexError:
                await ctx.channel.send('Format: `f.jail @user`')
        else:
            await ctx.channel.send('[MOD ROLE REQUIRED] :*)*')

    def get_roles_from_database(self, user_id):
        user_details = self.bot.db["jail"].find_one({"userID": user_id})
        if not user_details:
            return []
        else:
            # get existing data
            data = self.bot.db["jail"].find_one({"userID": user_id})
            return data['roles']

    def save_roles_to_database(self, user_id, roles):
        user_details = self.bot.db["jail"].find_one({"userID": user_id})
        if not user_details:
            # create new data
            self.bot.db["jail"].insert_one({"userID": user_id, "roles": roles})
        else:
            # update existing data
            self.bot.db["jail"].update_one({"userID": user_id},
                                           {"$set": {"roles": roles}})


async def setup(bot: commands.Bot):
    await bot.add_cog(Jail(bot))
