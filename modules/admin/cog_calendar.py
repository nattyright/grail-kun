# imports for calendar
from __future__ import print_function
import datetime
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from httplib2 import Http
import json

# imports for cog
import discord
from discord.ext import commands, tasks


# vars for cog
CALENDAR_CHANNEL_ID = 0
CALENDAR_MESSAGE_ID = 0
ENUM_ONGOING_EVENT = 0
ENUM_UPCOMING_EVENT = 1

# vars for calendar
# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
SERVICE_ACC_FILE = ".credentials/faterp-bot-service-account-key.json"
SERVICE_ACC_CREDENTIALS = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACC_FILE, SCOPES)
FATERP_CAL_ID = 'vbmcbuagv8ul3fiii6n385ahhc@group.calendar.google.com'

TIME_MAX = '2021-12-01T10:00:08.236687Z'


class Calendar(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_server_calendar.start()

        global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID
        CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID = get_calendar_message_id()

    @commands.command()
    async def calendar(self, ctx):
        if not discord.utils.get(ctx.author.roles, name="Global Moderator") is None:
            global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID
            msg_sent = await ctx.channel.send('Fetching server calendar...')

            CALENDAR_CHANNEL_ID = msg_sent.channel.id
            CALENDAR_MESSAGE_ID = msg_sent.id
            update_calendar_message_id(CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID)
            await self.update_server_calendar_once_only()
        else:
            await ctx.channel.send('[ADMIN ROLE REQUIRED] :*)*')

    @tasks.loop(minutes=1)
    async def update_server_calendar(self):
        global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID
        if CALENDAR_MESSAGE_ID != 0 and CALENDAR_CHANNEL_ID != 0:
            message = await self.bot.get_channel(CALENDAR_CHANNEL_ID).fetch_message(CALENDAR_MESSAGE_ID)

            discord_embed = get_calendar_events_as_json()

            embed = discord.Embed(title="",
                                  color=0)
            embed.add_field(name="Server Time",
                            value=discord_embed["content"],
                            inline=False)

            if discord_embed["embeds"][0]["fields"][ENUM_ONGOING_EVENT]["value"] != "":
                embed.add_field(name="Today's Events",
                                value=discord_embed["embeds"][0]["fields"][ENUM_ONGOING_EVENT]["value"],
                                inline=False)

            if discord_embed["embeds"][0]["fields"][ENUM_UPCOMING_EVENT]["value"] != "":
                embed.add_field(name="Upcoming Events",
                                value=discord_embed["embeds"][0]["fields"][ENUM_UPCOMING_EVENT]["value"],
                                inline=False)
            await message.edit(embed=embed, content="")

    @update_server_calendar.before_loop
    async def before_update(self):
        print('waiting...')
        await self.bot.wait_until_ready()

    async def update_server_calendar_once_only(self):
        await self.bot.wait_until_ready()
        global CALENDAR_CHANNEL_ID, CALENDAR_MESSAGE_ID
        message = await self.bot.get_channel(CALENDAR_CHANNEL_ID).fetch_message(CALENDAR_MESSAGE_ID)
        discord_embed = get_calendar_events_as_json()
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


def setup(bot: commands.Bot):
    bot.add_cog(Calendar(bot))



def update_calendar_message_id(channel_id, message_id):
    with open('data/msg_ids.json', 'r+', encoding='utf-8') as to_edit:
        data = json.load(to_edit)
        data["calendar"]["chn_id"] = channel_id
        data["calendar"]["msg_id"] = message_id
        # rewrite whole file
        to_edit.seek(0)
        json.dump(data, to_edit)
        to_edit.truncate()


def get_calendar_message_id():
    with open('data/msg_ids.json', 'r', encoding='utf-8') as to_read:
        data = json.load(to_read)
        return data["calendar"]["chn_id"], data["calendar"]["msg_id"]


def get_calendar_events_as_json():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    # Authorize usage of the API
    http_auth = SERVICE_ACC_CREDENTIALS.authorize(Http())
    service = build('calendar', 'v3', http=http_auth)

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    now_plus_one_month = (datetime.datetime.utcnow() + datetime.timedelta(weeks=2)).isoformat() + 'Z'
    # temporary for s3 signups period
    # now_plus_one_month = TIME_MAX
    #print('Getting the upcoming 10 events')
    events_result = service.events().list(calendarId=FATERP_CAL_ID,
                                        timeMin=now, timeMax=now_plus_one_month,
                                        maxResults=50, singleEvents=True,
                                        orderBy='startTime').execute()
    events = events_result.get('items', [])

    # sort events into single and multi events
    if not events:
        print('No upcoming events found.')
    for event in events:
        event['event_end_date'] = datetime.datetime.strptime(event['end'].get('dateTime', event['end'].get('date')),
                                                    '%Y-%m-%d').date()
        event['event_start_date'] = datetime.datetime.strptime(event['start'].get('dateTime', event['start'].get('date')),
                                                      '%Y-%m-%d').date()
        event['duration'] = (event['event_end_date'] - event['event_start_date']).days

    # print event list
    #print('Ongoing Events')
    ongoing_event_message = ""
    for event in events:
        current_date = datetime.datetime.utcnow().date()
        event_has_begun = (event['event_start_date'] <= current_date)
        if event_has_begun:
            if event['duration'] > 1:
                days_left_in_event = (event['event_end_date'] - current_date).days
                ongoing_event_message += '(' + str(days_left_in_event) + ' Days Remaining) ' + event['summary'] + '\n'
            else:
                start = event['start'].get('dateTime', event['start'].get('date'))
                ongoing_event_message += '(Today) ' + event['summary'] + '\n'
    #print(ongoing_event_message)

    #print('Upcoming Events')
    upcoming_event_message = ""
    upcoming_event_date = ""
    for event in events:
        current_date = datetime.datetime.utcnow().date()
        start = event['start'].get('dateTime', event['start'].get('date'))
        event_has_begun = (event['event_start_date'] <= current_date)

        if not event_has_begun:

            if upcoming_event_date != start:
                upcoming_event_date = start
                upcoming_event_message += "```" + start + "```" + " " + event['summary'] + '\n'
            else:
                upcoming_event_message += event['summary'] + '\n'
    #print(upcoming_event_message)
    #datetime.datetime.utcnow().replace(second=0, microsecond=0).isoformat()[:-3]
    cur_time = datetime.datetime.utcnow().strftime("%Y-%m-%d, %I:%M %p")

    discord_embed = {
        "content": cur_time,
        "embeds": [
            {
                "title": "Server Calendar",
                "color": 0,
                "fields": [
                    {"name": "Ongoing Events", "value": ""},
                    {"name": "Upcoming Events", "value": ""}
                ]
            }
        ]
    }

    discord_embed["embeds"][0]["fields"][ENUM_ONGOING_EVENT]["value"] = ongoing_event_message
    discord_embed["embeds"][0]["fields"][ENUM_UPCOMING_EVENT]["value"] = upcoming_event_message
    return discord_embed
