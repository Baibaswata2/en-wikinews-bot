# wikinews_bot.py

import requests
import logging
import json
import os
import sys
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

import config
from formatters import PublishedFormatter, DevelopingFormatter, ReviewFormatter

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=config.LOGGING_LEVEL
)
logger = logging.getLogger(__name__)

class WikinewsBot:
    """A bot to monitor a specific Wikinews category based on a given configuration."""
    def __init__(self, category_config):
        self.config = category_config
        self.api_url = config.WIKI_API_URL
        self.base_url = config.WIKI_BASE_URL
        self.state_file_path = self._get_state_file_path()
        self.last_checked_article_title = self.load_last_checked_article_title()

        self.headers = {
            'User-Agent': 'WikinewsTelegramBot/1.1 (https://github.com/Baibaswata2/en-wikinews-bot; baibaswataray@gmail.com)'
        }

        # Initialize appropriate formatter
        if category_config['message_type'] == 'published':
            self.formatter = PublishedFormatter(self.api_url, self.base_url, self.headers)
        elif category_config['message_type'] == 'developing':
            self.formatter = DevelopingFormatter(self.api_url, self.base_url, self.headers)
        elif category_config['message_type'] == 'review':
            self.formatter = ReviewFormatter(self.api_url, self.base_url, self.headers)
        else:
            raise ValueError(f"Unknown message type: {category_config['message_type']}")

    def _get_state_file_path(self):
        """Determines the correct path for the state file."""
        if os.environ.get('GITHUB_WORKSPACE'):
            return os.path.join(os.environ.get('GITHUB_WORKSPACE'), self.config['state_file'])
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config['state_file'])

    def load_last_checked_article_title(self):
        """Loads the last checked article title from the state file."""
        try:
            if os.path.exists(self.state_file_path):
                with open(self.state_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    title = data.get('title')
                    logger.info(f"[{self.config['category_name']}] Loaded last checked article: {title}")
                    return title
        except Exception as e:
            logger.error(f"[{self.config['category_name']}] Error loading state file: {e}")

        logger.warning(f"[{self.config['category_name']}] State file not found. Using initial article.")
        return self.config['initial_article']

    def save_last_checked_article(self, article_data):
        """Saves the latest article data (title and timestamp) to the state file."""
        try:
            with open(self.state_file_path, 'w', encoding='utf-8') as f:
                state_to_save = {
                    'title': article_data.get('title'),
                    'timestamp': article_data.get('timestamp')
                }
                json.dump(state_to_save, f, ensure_ascii=False, indent=4)
            logger.info(f"[{self.config['category_name']}] Saved last checked article: {article_data.get('title')}")
        except Exception as e:
            logger.error(f"[{self.config['category_name']}] Error saving state file: {e}")

    def _make_api_request(self, params):
        """Helper function to make API requests with the required User-Agent."""
        try:
            response = requests.get(self.api_url, params=params, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None

    def get_category_members(self):
        """Fetches the latest members of the configured Wikinews category."""
        params = {
            "action": "query", "list": "categorymembers",
            "cmtitle": f"Category:{self.config['category_name']}",
            "cmlimit": 50, "cmsort": "timestamp", "cmdir": "desc", "format": "json",
            "cmprop": "title|timestamp"
        }
        data = self._make_api_request(params)
        return data.get('query', {}).get('categorymembers', []) if data else []

    def check_for_new_articles(self):
        """Checks for new articles since the last run and returns them in chronological order."""
        all_articles = self.get_category_members()
        if not all_articles:
            logger.info(f"[{self.config['category_name']}] No articles found.")
            return []

        # For Review category, if no initial article is set, use the first article found
        if not self.last_checked_article_title and self.config['category_name'] == 'Review':
            if all_articles:
                self.last_checked_article_title = all_articles[0]['title']
                logger.info(f"[{self.config['category_name']}] Setting initial article to: {self.last_checked_article_title}")
                return []

        try:
            last_idx = next(i for i, a in enumerate(all_articles) if a['title'] == self.last_checked_article_title)
            new_articles = all_articles[:last_idx]
        except StopIteration:
            logger.warning(f"[{self.config['category_name']}] Last checked article not found. Processing latest.")
            new_articles = [all_articles[0]] if all_articles else []

        return new_articles[::-1]

async def broadcast_message(bot, message, targets):
    """Sends a formatted message to a list of Telegram targets."""
    for target in targets:
        try:
            await bot.send_message(
                chat_id=target['chat_id'],
                message_thread_id=target.get('thread_id'),
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            logger.info(f"Successfully sent message to target: {target}")
        except TelegramError as e:
            logger.error(f"Failed to send message to {target}: {e}")

async def main_async():
    """Main function to run the bot check for all configured categories."""
    if not config.BOT_TOKEN:
        logger.error("Telegram bot token is not configured.")
        sys.exit(1)

    telegram_bot = Bot(token=config.BOT_TOKEN)

    for category_config in config.MONITORED_CATEGORIES:
        logger.info(f"--- Checking category: {category_config['category_name']} ---")
        bot_instance = WikinewsBot(category_config)
        new_articles = bot_instance.check_for_new_articles()

        if not new_articles:
            logger.info(f"No new articles for '{category_config['category_name']}'.")
            continue

        logger.info(f"Found {len(new_articles)} new article(s) for '{category_config['category_name']}'.")
        latest_article_data = None

        for article_data in new_articles:
            title = article_data['title']
            url_slug = title.replace(' ', '_')

            # For Published category, verify the article has been properly reviewed
            if category_config['message_type'] == 'published':
                if not bot_instance.formatter.check_article_review_status(title):
                    logger.warning(f"Skipping '{title}' - No valid review found (false detection)")
                    continue

            # Use the appropriate formatter to create the message
            try:
                message = bot_instance.formatter.format_message(article_data, url_slug)
                logger.info(f"Final message for '{title}':\n{message}")
                await broadcast_message(telegram_bot, message, category_config['telegram_targets'])
                latest_article_data = article_data
            except Exception as e:
                logger.error(f"Error formatting message for '{title}': {e}")
                continue

        if latest_article_data:
            bot_instance.save_last_checked_article(latest_article_data)

if __name__ == '__main__':
    try:
        asyncio.run(main_async())
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)
