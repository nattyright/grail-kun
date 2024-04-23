# imports for cog
import discord
from discord.ext import commands
import json
from datetime import datetime
import math

time_504_hours = 504 # 3 minutes
time_168_hours = 168 # 1 minute
time_3600_seconds = 3600 # minute testing

class ThreadTrackerS5(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # listen for new threads under 'Season 5' Category
    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        if 'Season 5'.lower() in str(thread.category).lower():
            update_timestamp_thread_begin(str(thread.id), str(thread.name))

    # listen for archived threads in 'Archive Requests'
    @commands.Cog.listener()
    async def on_message(self, message):
        chn = str(message.channel)

        emotes = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣' ]
        count = 0

        if ('archive'.lower() in chn) and ('request'.lower() in chn):
            # get thread obj
            for thread in message.channel_mentions:
                # update thread end time
                update_timestamp_thread_end(str(thread.id), str(thread.name))
                # check for 3 week deadline
                if thread_exceeded_three_weeks(str(thread.id)):
                    await message.add_reaction(emotes[count])
                    count += 1

                # debugging
                await message.channel.send(get_json(str(thread.id)))
            

    # pause thread + lock thread
    @commands.hybrid_command(description="Pause a S5 RP Thread")
    async def pause(self, ctx: commands.Context):
        thread = ctx.message.channel

        # check if thread is in appropriate channel (s5 rp)
        if 'Season 5'.lower() not in str(thread.category).lower():
            await ctx.reply('Only S5 Threads can be paused.')

        else: 
            # check if thread has been paused in the prev 7 days (CD)
            if not is_pause_in_cooldown(str(thread.id)):
                if is_locked(str(thread.id)):
                    await ctx.reply("Thread is already locked. Please unlock it first.")
                else:
                    update_timestamp_pause_thread(str(thread.id))
                    #thread.locked = True
                    update_lock_thread(str(thread.id))
                    # lock thread
                    # Overwrite the channel permissions to disallow sending messages
                    await thread.edit(locked=True)
                    await ctx.reply("Thread locked.")

            else:
                await ctx.reply('Thread pause in 7 day cooldown :sob:')


    # unlock thread + unpause thread
    @commands.Cog.listener()
    async def on_raw_thread_update(self, payload):
        thread = payload.thread
        # check if thread was previously locked & currently UNlocked
        if 'Season 5'.lower() in str(thread.category).lower() and \
            thread_previously_locked(str(thread.id)) and \
            thread.locked == False:

            # update thread status & unpaused timestamp in JSON
            update_unlock_thread(str(thread.id))
            update_timestamp_unpause_thread(str(thread.id))

            # calculate paused time and add any time exceeding 7 days to the deadline offset
            pause_exceeded_seven_days(str(thread.id))
            await thread.send("Thread unlocked.")



async def setup(bot: commands.Bot):
    await bot.add_cog(ThreadTrackerS5(bot))




def update_timestamp_thread_begin(thread_id, thread_name):
    with open('data/roleplay/threadtracker_s5.json', 'r+', encoding='utf-8') as to_edit:
        data = json.load(to_edit)
        data[thread_id] = {
            'thread_name'    : thread_name,
            'timestamp_begin': str(discord.utils.utcnow())
        }

        # write to file
        to_edit.seek(0)
        json.dump(data, to_edit)
        to_edit.truncate()


def update_timestamp_thread_end(thread_id, thread_name):
    update_json(thread_id, 'timestamp_end', str(discord.utils.utcnow()))


def thread_exceeded_three_weeks(thread_id):
    with open('data/roleplay/threadtracker_s5.json', 'r+', encoding='utf-8') as to_edit:
        data = json.load(to_edit)
        time_begin = datetime.strptime(data[thread_id]['timestamp_begin'], '%Y-%m-%d %H:%M:%S.%f%z')
        time_end = datetime.strptime(data[thread_id]['timestamp_end'], '%Y-%m-%d %H:%M:%S.%f%z')

        # check if exceeded 3 weeks aka 504 hours

        # check if pause offset exists
        if 'pause_offset' in data[thread_id]:
            pause_offset = int(data[thread_id]['pause_offset'])
        else:
            pause_offset = 0    

        # check if pause timer exists
        if 'pause_timer' in data[thread_id]:
            pause_timer = int(data[thread_id]['pause_timer'])
        else:
            pause_timer = 0      


        data[thread_id]['exceeded_3weeks'] = str(time_diff_exceeded_limit(time_begin, 
                                                                          time_end, 
                                                                          (time_504_hours + pause_timer - pause_offset)))

        # write to file
        to_edit.seek(0)
        json.dump(data, to_edit)
        to_edit.truncate()

        return (data[thread_id]['exceeded_3weeks'] == 'True')


def pause_exceeded_seven_days(thread_id):
    with open('data/roleplay/threadtracker_s5.json', 'r+', encoding='utf-8') as to_edit:
        data = json.load(to_edit)
        time_begin = datetime.strptime(data[thread_id]['timestamp_pause'], '%Y-%m-%d %H:%M:%S.%f%z')
        time_end = datetime.strptime(data[thread_id]['timestamp_unpause'], '%Y-%m-%d %H:%M:%S.%f%z')

        time_diff_hour = time_diff(time_begin, time_end)

        # pause timer = total hours paused
        if 'pause_timer' not in data[thread_id]:
            data[thread_id]['pause_timer'] = str(time_diff_hour)
        else:
            data[thread_id]['pause_timer'] = str(int(data[thread_id]['pause_timer']) + time_diff_hour)

        # pause offset = total EXCEEDED paused time (the portion that's > 7 days during each pause)
        pause_offset = 0 if (time_diff_hour < time_168_hours) else abs(time_diff_hour - time_168_hours)

        if 'pause_offset' not in data[thread_id]:
            data[thread_id]['pause_offset'] = str(pause_offset)
        else:
            data[thread_id]['pause_offset'] = str(int(data[thread_id]['pause_offset']) + pause_offset)

        # write to file
        to_edit.seek(0)
        json.dump(data, to_edit)
        to_edit.truncate()


def is_pause_in_cooldown(thread_id):
    with open('data/roleplay/threadtracker_s5.json', 'r+', encoding='utf-8') as to_edit:
        data = json.load(to_edit)

        # never paused before
        if 'timestamp_unpause' not in data[thread_id]:
            return False
        # paused before
        else:
            time_begin = datetime.strptime(data[thread_id]['timestamp_unpause'], '%Y-%m-%d %H:%M:%S.%f%z')
            time_end = discord.utils.utcnow()

            return (not time_diff_exceeded_limit(time_begin, time_end, time_168_hours))

def is_locked(thread_id):
    with open('data/roleplay/threadtracker_s5.json', 'r+', encoding='utf-8') as to_edit:
        data = json.load(to_edit)

        # never paused before
        return data[thread_id]["is_locked"] == "True"


def update_timestamp_pause_thread(thread_id):
    update_json(thread_id, 'timestamp_pause', str(discord.utils.utcnow()))
def update_timestamp_unpause_thread(thread_id):
    update_json(thread_id, 'timestamp_unpause', str(discord.utils.utcnow()))


def update_lock_thread(thread_id):
    update_json(thread_id, 'is_locked', 'True')
def update_unlock_thread(thread_id):
    update_json(thread_id, 'is_locked', 'False')


def thread_previously_locked(thread_id):
    return validate_json_value(thread_id, 'is_locked', 'True')








### UTIL ###
def update_json(main_key, sub_key, sub_val):
    with open('data/roleplay/threadtracker_s5.json', 'r+', encoding='utf-8') as to_edit:
        data = json.load(to_edit)
        data[main_key][sub_key] = sub_val

        # write to file
        to_edit.seek(0)
        json.dump(data, to_edit)
        to_edit.truncate()

def validate_json_value(main_key, sub_key, val_to_compare):
    with open('data/roleplay/threadtracker_s5.json', 'r', encoding='utf-8') as to_compare:
        data = json.load(to_compare)
        return (data[main_key][sub_key] == val_to_compare)

def time_diff_exceeded_limit(time_1, time_2, target_diff_in_hours):

        time_difference = abs(time_2 - time_1)
        difference_in_hours = time_difference.total_seconds() / time_3600_seconds

        # Check if the difference is greater than 504 hours aka 21 days aka 3 weeks
        return (math.floor(difference_in_hours) > target_diff_in_hours)
        
def time_diff(time_1, time_2):
        time_difference = abs(time_2 - time_1)
        difference_in_hours = time_difference.total_seconds() / time_3600_seconds
        return math.floor(difference_in_hours)

def get_json(thread_id):
    with open('data/roleplay/threadtracker_s5.json', 'r+', encoding='utf-8') as to_view:
        data = json.load(to_view)
        return str(data[thread_id])