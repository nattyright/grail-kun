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
                     "value": "```f.multi```Salt sim (weak-willed).```f.single```Salt sim (strong-willed)."}
                ]
            }
        ]
    }
    return discord_embed
