import os
import logging

## -- WIKINEWS SETTINGS -- ##
WIKI_API_URL = "https://en.wikinews.org/w/api.php"
WIKI_BASE_URL = "https://en.wikinews.org/wiki/"
DATE_FORMAT = "%B %d, %Y"

## -- TELEGRAM BOT TOKEN -- ##
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

## -- LOGGING SETTINGS -- ##
LOGGING_LEVEL = logging.INFO

## -- CATEGORY MONITORING CONFIGURATION -- ##
MONITORED_CATEGORIES = [
    {
        "category_name": "Published",
        "message_type": "published",
        "state_file": "published_state.json",
        "initial_article": "New York judge rules terrorism charges legally insufficient in Mangione case",
        "telegram_targets": [
            {"chat_id": "-1002591426405", "thread_id": "5"},
        ],
    },
    {
        "category_name": "Developing",
        "message_type": "developing",
        "state_file": "developing_state.json",
        "initial_article": "GrowHo launches tech platform to support Grampanchayats and rural employment",
        "telegram_targets": [
            {"chat_id": "-1002113193375", "thread_id": "1110"},

        ],
    },
    {
        "category_name": "Review",
        "message_type": "review",
        "state_file": "review_state.json",
        "initial_article": "Unification Church leader Hak Ja Han arrested in South Korea over bribery allegations", 
        "telegram_targets": [
            {"chat_id": "-1002113193375", "thread_id": "1113"},           
        ],
    },
]
