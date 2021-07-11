def get_help_message():
    discord_embed = {
        "embeds": [
            {
                "title": "Help Message",
                "color": 0,
                "fields": [
                    {"name": "Admin Commands",
                     "value": "```f.calendar```Fetch server calendar."},
                    {"name": "User Commands",
                     "value": "```f.gacha```Salt sim."}
                ]
            }
        ]
    }
    return discord_embed
