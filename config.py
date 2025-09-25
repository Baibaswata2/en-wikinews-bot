# config.py

import os
import logging

## -- WIKINEWS SETTINGS -- ##
WIKI_API_URL = "https://en.wikinews.org/w/api.php"
WIKI_BASE_URL = "https://en.wikinews.org/wiki/"
DATE_FORMAT = "%B %d, %Y"

## -- TELEGRAM BOT TOKEN -- ##
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

## -- LOGGING SETTINGS -- ##
LOGGING_LEVEL = logging.INFO

## -- CATEGORY MONITORING CONFIGURATION -- ##
MONITORED_CATEGORIES = [
    {
        "category_name": "Published",
        "message_type": "published",
        "state_file": "published_state.json",
        "initial_article": "UN Security Council to hold emergency meeting on Iran",
        "telegram_targets": [
            {'chat_id': '-1002218836962'},
            {'chat_id': '-1002478167736', 'thread_id': '308'},
        ]
    },
    {
        "category_name": "Developing",
        "message_type": "developing", 
        "state_file": "developing_state.json",
        "initial_article": "Another recent article title from the Developing category",
        "telegram_targets": [
            {'chat_id': 'YOUR_DEVELOPING_NEWS_CHANNEL_ID'}, 
        ]
    },
]
