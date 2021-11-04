import discord
import asyncio
import os
from dotenv import load_dotenv
from io import BytesIO
# downloading animu
import os

from discord.ext.commands import Bot
from discord_components import DiscordComponents, Select, SelectOption

import google_calendar
import bot_help
import gacha_fgo
import mongodb_client

# setup mongodb database
db = mongodb_client.get_database()

# setup calender
load_dotenv()
TOKEN = os.getenv("TOKEN")
CALENDAR_CHANNEL_ID = 0
CALENDAR_MESSAGE_ID = 0
CALENDAR_UPDATE_INTERVAL = 21600  # seconds, this is 6 hours
ENUM_ONGOING_EVENT = 0
ENUM_UPCOMING_EVENT = 1

# setup gacha bot banner options
BANNER_LABEL_1 = "15 Million Downloads Pickup Summon"
BANNER_LABEL_2 = "Christmas 2021 Pickup Summon"
BANNER_LABEL_3 = ""

BANNER_VALUE_1 = "18m_dl"
BANNER_VALUE_2 = "xmas_2021"
BANNER_VALUE_3 = ""

BANNER_VALUES = {"lb5_orion": "Lostbelt No.5 Atlantis Pickup Summon (S.Orion)",
                 "lb5_europa": "Lostbelt No.5 Atlantis Pickup Summon (Europa)",
                 "lb5_achilles": "Lostbelt No.5 Atlantis Pickup Summon 2",
                 "newyear_2022": "New Year 2022 Pickup Summon (Yang Guifei)",
                 "sparrow_benny": "Revival: Sparrow's Inn Pickup Summon (Beni)",
                 "sparrow_tamamo": "Revival: Sparrow's Inn Pickup Summon (Tamamo)",
                 "sparrow_assli": "Revival: Sparrow's Inn Pickup Summon 2",
                 "amazones_cleo": "Amazoness Dot Com Pickup Summon (Cleo)",
                 "amazones_neet": "Amazoness Dot Com Pickup Summon (Osakabehime)",
                 "valentines_2022_singlerateup": "Valentine's 2022 Pickup Summon (Sei)",
                 "19m_dl": "19 Mil Downloads Pickup Summon",
                 "chaldea_boys_singlerateup": "Chaldea Boys Collection 2022 Pickup Summon (Odysseus)"
                 }

client = Bot(command_prefix="f.", help_command=None)
# buttons and select option (not in official discord.py yet
DiscordComponents(client)

COOLDOWN = True


"""
Initialize bot
"""


@client.event
async def on_ready():
    global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID
    print('We have logged in as {0.user}'.format(client))
    # set status message
    await client.change_presence(activity=discord.Game('fateRP bot | f.help'))
    # set up calendar
    CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID = google_calendar.get_calendar_message_id()
    client.loop.create_task(update_server_calendar())


@client.command()
async def help(ctx):
    discord_embed = bot_help.get_help_message()

    embed = discord.Embed(title="",
                          color=0)
    embed.add_field(name="Admin Commands",
                    value=discord_embed["embeds"][0]["fields"][0]["value"],
                    inline=False)
    embed.add_field(name="User Commands",
                    value=discord_embed["embeds"][0]["fields"][1]["value"],
                    inline=False)
    await ctx.channel.send(embed=embed)




"""
Cytube commands
"""


@client.command()
async def cytube(ctx, type, source, episode=""):
    if type == 'anime':
        command = "ssh -i .credentials/id_rsa root@135.148.2.69 'anime dl "
        command += '"' + source + '" --episodes ' + episode
        command += "'"
    else:
        command = "ssh -i .credentials/id_rsa root@135.148.2.69 'cd /var/www/h5ai && " + \
                  "./_h5ai/private/annie " + source + "'"
    os.system(command)


"""
Gacha commands
"""


def update_gacha_database(ctx, banner_id, roll_count):
    get_gacha_data(db, ctx.author.id, banner_id, roll_count)


def get_gacha_data(db, user_id, banner_id, roll_count=0):
    user_details = db["fgogacha"].find_one({"userID": user_id, "bannerID": banner_id})
    if not user_details:
        # create new data or simply retrieve data if not rolling
        create_gacha_data(db, user_id, banner_id, roll_count)
    else:
        if roll_count == 0:
            pass
        elif roll_count == 1:
            single_count = user_details["single"] + 1
            multi_count = user_details["multi"]
            db["fgogacha"].update_one({"userID": user_id, "bannerID": banner_id}, {"$set": {"single": single_count}})
        else:
            single_count = user_details["single"]
            multi_count = user_details["multi"] + 1
            db["fgogacha"].update_one({"userID": user_id, "bannerID": banner_id}, {"$set": {"multi": multi_count}})


def create_gacha_data(db, user_id, banner_id, roll_count):
    # roll_count 0 means we're just getting data, not rolling
    if roll_count == 0:
        pass
    elif roll_count == 1:
        db["fgogacha"].insert_one({"userID": user_id, "bannerID": banner_id, "single": 1, "multi": 0})
    else:
        db["fgogacha"].insert_one({"userID": user_id, "bannerID": banner_id, "single": 0, "multi": 1})


@client.command()
async def multi(ctx):
    global COOLDOWN
    author_id = '<@' + str(ctx.author.id) + '>'

    if COOLDOWN:
        COOLDOWN = False

        msg_sent = await ctx.send(
            "Pick a banner",
            components=[
                Select(placeholder="Available banners",
                       options=[SelectOption(label=BANNER_LABEL_1, value=BANNER_VALUE_1),
                                SelectOption(label=BANNER_LABEL_2, value=BANNER_VALUE_2),
                                # SelectOption(label=BANNER_LABEL_3, value=BANNER_VALUE_3),
                                SelectOption(label="Story Banner", value="story")])
            ]
        )
        interaction = await client.wait_for("select_option")
        await msg_sent.delete()
        await ctx.send(content='Generating 11-roll for ' + interaction.component[0].label + '...' + author_id)
        # update database
        update_gacha_database(ctx, interaction.component[0].value, 10)
        # roll the gacha
        await sent_ten_roll_image(ctx, author_id, interaction.component[0].value)
        COOLDOWN = True
    else:
        await ctx.channel.send('wait and cope ' + author_id)


@client.command()
async def single(ctx):
    global COOLDOWN
    author_id = '<@' + str(ctx.author.id) + '>'

    if COOLDOWN:
        COOLDOWN = False

        msg_sent = await ctx.send(
            "Pick a banner",
            components=[
                Select(placeholder="Available banners",
                       options=[SelectOption(label=BANNER_LABEL_1, value=BANNER_VALUE_1),
                                SelectOption(label=BANNER_LABEL_2, value=BANNER_VALUE_2),
                                # SelectOption(label=BANNER_LABEL_3, value=BANNER_VALUE_3),
                                SelectOption(label="Story Banner", value="story")])
            ]
        )
        interaction = await client.wait_for("select_option")
        await msg_sent.delete()
        await ctx.send(content='Generating single roll for ' + interaction.component[0].label + '...' + author_id)
        # update database
        update_gacha_database(ctx, interaction.component[0].value, 1)
        # roll the gacha
        await sent_single_roll_image(ctx, author_id, interaction.component[0].value)
        COOLDOWN = True
    else:
        await ctx.channel.send('wait and cope ' + author_id)


@client.event
async def sent_ten_roll_image(message, author_id, banner_name):
    cards = gacha_fgo.print_roll_result(gacha_fgo.ten_roll(banner_name))
    cards_im = gacha_fgo.generate_ten_roll_image(cards)
    with BytesIO() as image_binary:
        cards_im.save(image_binary, 'PNG')
        image_binary.seek(0)
        await message.channel.send(content=author_id, file=discord.File(fp=image_binary, filename='image.png'))


@client.event
async def sent_single_roll_image(message, author_id, banner_name):
    card = gacha_fgo.print_roll_result_single(gacha_fgo.single_roll(banner_name))
    card_im = gacha_fgo.generate_single_roll_image(card)
    with BytesIO() as image_binary:
        card_im.save(image_binary, 'PNG')
        image_binary.seek(0)
        await message.channel.send(content=author_id, file=discord.File(fp=image_binary, filename='image.png'))


"""
Calender commands
"""


@client.command()
async def calendar(ctx):
    if not discord.utils.get(ctx.author.roles, name="Administrator") is None:
        global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID
        msg_sent = await ctx.channel.send('Fetching server calendar...')

        CALENDAR_CHANNEL_ID = msg_sent.channel.id
        CALENDAR_MESSAGE_ID = msg_sent.id
        google_calendar.update_calendar_message_id(CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID)
        await update_server_calendar_once_only()
    else:
        await ctx.channel.send('[ADMIN ROLE REQUIRED] :*)*')


@client.event
async def update_server_calendar():
    await client.wait_until_ready()
    while not client.is_closed():
        global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID

        if CALENDAR_MESSAGE_ID != 0 and CALENDAR_CHANNEL_ID != 0:
            message = await client.get_channel(CALENDAR_CHANNEL_ID).fetch_message(CALENDAR_MESSAGE_ID)

            discord_embed = google_calendar.get_calendar_events_as_json()

            embed = discord.Embed(title="",
                                  color=0)
            embed.add_field(name="Server Time",
                            value=discord_embed["content"],
                            inline=False)
            embed.add_field(name="Today's Events",
                            value=discord_embed["embeds"][0]["fields"][ENUM_ONGOING_EVENT]["value"],
                            inline=False)
            embed.add_field(name="Upcoming Events",
                            value=discord_embed["embeds"][0]["fields"][ENUM_UPCOMING_EVENT]["value"],
                            inline=False)
            await message.edit(embed=embed, content="")
            await asyncio.sleep(CALENDAR_UPDATE_INTERVAL)


@client.event
async def update_server_calendar_once_only():
    await client.wait_until_ready()
    global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID
    message = await client.get_channel(CALENDAR_CHANNEL_ID).fetch_message(CALENDAR_MESSAGE_ID)
    discord_embed = google_calendar.get_calendar_events_as_json()
    embed = discord.Embed(title="",
                          color=0)
    embed.add_field(name="Server Time",
                    value=discord_embed["content"],
                    inline=False)
    embed.add_field(name="Today's Events",
                    value=discord_embed["embeds"][0]["fields"][ENUM_ONGOING_EVENT]["value"],
                    inline=False)
    embed.add_field(name="Upcoming Events",
                    value=discord_embed["embeds"][0]["fields"][ENUM_UPCOMING_EVENT]["value"],
                    inline=False)
    await message.edit(embed=embed, content="")


client.run(TOKEN)
