import discord
import asyncio
import os
import time
from dotenv import load_dotenv

import google_calendar
import help
import gacha_fgo

load_dotenv()
TOKEN = os.getenv("TOKEN")
CALENDAR_CHANNEL_ID = 0
CALENDAR_MESSAGE_ID = 0
CALENDAR_UPDATE_INTERVAL = 43200  # seconds, this is 12 hours
ENUM_ONGOING_EVENT = 0
ENUM_UPCOMING_EVENT = 1

client = discord.Client()

COOLDOWN = True


@client.event
async def on_ready():
    global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID
    print('We have logged in as {0.user}'.format(client))
    # set up calendar
    CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID = google_calendar.get_calendar_message_id()
    client.loop.create_task(update_server_calendar())


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('f.help'):
        discord_embed = help.get_help_message()

        embed = discord.Embed(title="",
                              color=0)
        embed.add_field(name="Admin Commands",
                        value=discord_embed["embeds"][0]["fields"][0]["value"],
                        inline=False)
        embed.add_field(name="User Commands",
                        value=discord_embed["embeds"][0]["fields"][1]["value"],
                        inline=False)
        await message.channel.send(embed=embed)

    if message.content.startswith('f.calendar') and \
            not discord.utils.get(message.author.roles, name="Administrator") is None:
        global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID
        msg_sent = await message.channel.send('Fetching server calendar...')

        CALENDAR_CHANNEL_ID = msg_sent.channel.id
        CALENDAR_MESSAGE_ID = msg_sent.id
        google_calendar.update_calendar_message_id(CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID)
        await update_server_calendar_once_only()

    if message.content.startswith('f.gacha'):
        global COOLDOWN
        if COOLDOWN:
            COOLDOWN = False

            cards = gacha_fgo.print_roll_result(gacha_fgo.ten_roll())
            author_id = '<@' + str(message.author.id) + '>'
            await message.channel.send('Servant Fes Banner #1 ' + author_id)
            for card in cards:
                embed = discord.Embed(title="",
                                      color=card['color'])
                embed.set_thumbnail(url=card['url'])
                embed.add_field(name=card['name'],
                                value=card['value'],
                                inline=False)
                await message.channel.send(embed=embed)
            time.sleep(1)
            COOLDOWN = True
        else:
            author_id = '<@' + str(message.author.id) + '>'
            await message.channel.send('wait and cope ' + author_id)


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
