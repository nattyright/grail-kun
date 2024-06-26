"""Commands to be used in conjunction with profile.fatechan.top."""

# imports for cog
import discord
from discord.ext import commands
from io import BytesIO

# imports for gacha
import json


class servantProfile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def claim(self, ctx, servant_id, password):
        author_id = ctx.author.id
        result = self.find_servant_from_database(servant_id, password)

        if result is not None:
            message = self.claim_servant_from_database(author_id, servant_id)
            await ctx.send(content=message)
        else:
            await ctx.send(content='Invalid Servant ID/Password combination. Servant not found/claimed.')

    @commands.command()
    async def myservants(self, ctx):
        author_id = ctx.author.id
        result = self.get_claimed_servant_from_database(author_id)
        await ctx.send(content=result)

    def find_servant_from_database(self, servant_id, password):
        result = self.bot.db_fan_servants["servants"].find_one({"info.cardURL": servant_id, "password": password})
        return result

    def claim_servant_from_database(self, author_id, servant_id):
        message = "Servant claimed."
        result = self.bot.db_fan_servants["users"].find_one({"userID": author_id}, {"claimedServants": 1})

        if result is None:
            result = [servant_id]
        else:
            result = result["claimedServants"]
            if servant_id in result:
                message = "Servant already claimed."
            else:
                result.append(servant_id)

        self.bot.db_fan_servants["users"].update_one({"userID": author_id},
                                                     {"$set": {"claimedServants": result}},
                                                     upsert=True)

        return message

    def get_claimed_servant_from_database(self, author_id):
        message = ""
        result = self.bot.db_fan_servants["users"].find_one({"userID": author_id}, {"claimedServants": 1})

        if result is None:
            message = "You have claimed 0 Servants."
        else:
            servants = result["claimedServants"]
            result = []
            servants_deleted_profiles_removed = []
            for servant_id in servants:
                servant = self.bot.db_fan_servants["servants"].find_one({"info.cardURL": servant_id}, {"info.servantName": 1})
                if servant is not None:
                    result.append(servant["info"]["servantName"])
                    servants_deleted_profiles_removed.append(servant_id)

            # update claimed servant list if it's different from the original
            # (e.g. some servant profiles were deleted)
            if len(set(servants_deleted_profiles_removed).intersection(servants)) != len(servants):
                self.bot.db_fan_servants["users"].update_one({"userID": author_id},
                                                             {"$set": {"claimedServants": servants_deleted_profiles_removed}},
                                                             upsert=True)

            message = "You have claimed " + str(len(result)) + " Servants: " + ', '.join(map(str, result))

        return message




async def setup(bot: commands.Bot):
    await bot.add_cog(servantProfile(bot))

