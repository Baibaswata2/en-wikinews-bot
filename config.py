# config.py

import os
import logging

# The base URL for the English Wikinews API.
WIKI_API_URL = "https://en.wikinews.org/w/api.php"

# The base URL for reading Wikinews articles.
WIKI_BASE_URL = "https://en.wikinews.org/wiki/"

# The category to monitor for new articles.
CATEGORY_TO_TRACK = "Published"

# The desired date format for messages
DATE_FORMAT = "%B %d, %Y"


## -- TELEGRAM SETTINGS -- ##

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# A list of all destinations where the bot should send messages.
TELEGRAM_TARGETS = [
    {'chat_id': '-1002218836962'}, 
    {'chat_id': '-1002478167736', 'thread_id': '308'},
]

## -- BOT OPERATIONAL SETTINGS -- ##

LAST_CHECKED_FILE = "last_checked_article.json"

LOGGING_LEVEL = logging.INFO

INITIAL_REFERENCE_ARTICLE = "Example article title from English Wikinews"
