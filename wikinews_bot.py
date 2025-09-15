# wikinews_bot.py

import requests
import logging
import json
import os
import sys
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

# Import settings from the configuration file
import config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=config.LOGGING_LEVEL
)
logger = logging.getLogger(__name__)

class WikinewsBot:
    """
    A bot to monitor English Wikinews for new articles and post them to Telegram.
    """
    def __init__(self):
        self.api_url = config.WIKI_API_URL
        self.base_url = config.WIKI_BASE_URL
        self.last_checked_file_path = self._get_last_checked_file_path()
        self.last_checked_article = self.load_last_checked_article()

    def _get_last_checked_file_path(self):
        if os.environ.get('GITHUB_WORKSPACE'):
            return os.path.join(os.environ.get('GITHUB_WORKSPACE'), config.LAST_CHECKED_FILE)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), config.LAST_CHECKED_FILE)

    def load_last_checked_article(self):
        """Loads the last checked article title from the state file."""
        try:
            if os.path.exists(self.last_checked_file_path):
                with open(self.last_checked_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Loaded last checked article: {data.get('title')}")
                    return data.get('title')
        except Exception as e:
            logger.error(f"Error loading state file: {e}")
        
        logger.warning("State file not found or invalid. Using initial reference article.")
        return config.INITIAL_REFERENCE_ARTICLE

    def save_last_checked_article(self, title):
        """Saves the latest article title to the state file."""
        try:
            os.makedirs(os.path.dirname(self.last_checked_file_path), exist_ok=True)
            with open(self.last_checked_file_path, 'w', encoding='utf-8') as f:
                json.dump({'title': title}, f, ensure_ascii=False, indent=4)
            logger.info(f"Saved last checked article: {title}")
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    def get_category_members(self):
        """Fetches the latest members of the configured Wikinews category."""
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{config.CATEGORY_TO_TRACK}",
            "cmlimit": 50,
            "cmsort": "timestamp",
            "cmdir": "desc",
            "format": "json"
        }
        try:
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('query', {}).get('categorymembers', [])
        except requests.RequestException as e:
            logger.error(f"Error fetching category members: {e}")
            return []

    def get_article_summary(self, title):
        """Extracts the first two sentences from a Wikinews article."""
        params = {
            "action": "parse",
            "page": title,
            "prop": "text",
            "section": 0,
            "format": "json"
        }
        try:
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'parse' not in data or 'text' not in data['parse']:
                logger.error(f"Failed to get content for '{title}'")
                return ""

            html_content = data['parse']['text']['*']
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find the first paragraph with meaningful text
            first_paragraph = soup.find('p', string=lambda t: t and t.strip())
            if not first_paragraph:
                logger.warning(f"No suitable paragraph found in '{title}'")
                return ""

            text = first_paragraph.get_text().strip()
            # Split by period followed by a space for better sentence detection
            sentences = text.split('. ')
            summary = '. '.join(sentences[:2])
            # Ensure the summary ends with a period
            if not summary.endswith('.'):
                summary += '.'
            return summary
        except requests.RequestException as e:
            logger.error(f"Error getting article content for '{title}': {e}")
            return ""

    def get_article_details(self, article_data):
        """Gathers all necessary details for a given article."""
        title = article_data['title']
        page_url = f"{self.base_url}{title.replace(' ', '_')}"
        timestamp_str = article_data.get('timestamp')
        
        try:
            publish_date = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
            formatted_date = publish_date.strftime(config.DATE_FORMAT)
        except (ValueError, TypeError):
            formatted_date = "Unknown date"

        return {
            'title': title,
            'url': page_url,
            'summary': self.get_article_summary(title),
            'date': formatted_date,
            'talk_page_url': f"{self.base_url}Talk:{title.replace(' ', '_')}",
            'history_url': f"{self.api_url.replace('api.php', 'index.php')}?title={title.replace(' ', '_')}&action=history"
        }

    def check_for_new_articles(self):
        """
        Checks for new articles since the last run and returns them in chronological order.
        """
        all_articles = self.get_category_members()
        if not all_articles:
            logger.info("No articles found in the category.")
            return []

        # Find the index of the last checked article
        try:
            last_checked_index = next(i for i, article in enumerate(all_articles) if article['title'] == self.last_checked_article)
        except StopIteration:
            # If the last article isn't in the list
            # we'll just process the single newest article to be safe.
            logger.warning(f"Last checked article '{self.last_checked_article}' not found. Processing the latest article.")
            return [all_articles[0]]

        # New articles are those that appear before the last checked one in the list
        new_articles = all_articles[:last_checked_index]
        
        # Return them in oldest-to-newest order for sequential posting
        return new_articles[::-1]


async def broadcast_message(bot_token, message):
    """Sends a formatted message to all configured Telegram targets."""
    bot = Bot(token=bot_token)
    for target in config.TELEGRAM_TARGETS:
        try:
            await bot.send_message(
                chat_id=target['chat_id'],
                message_thread_id=target.get('thread_id'), # Will be None if not specified
                text=message,
                parse_mode='Markdown',
                disable_web_page_preview=False
            )
            logger.info(f"Successfully sent message to target: {target}")
        except TelegramError as e:
            logger.error(f"Failed to send message to target {target}: {e}")

def format_telegram_message(details):
    """Creates the Markdown-formatted message string from article details."""
    message = f"*{details['title']}*\n\n"
    message += f"{details['date']}\n\n"
    if details['summary']:
        message += f"{details['summary']}\n\n"
    message += f"[Read more...]({details['url']})\n\n"
    message += f"([Talk page]({details['talk_page_url']}) | [History]({details['history_url']}))"
    return message

async def main_async():
    """Main asynchronous function to run the bot check."""
    logger.info("Starting Wikinews bot check...")
    
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("Telegram bot token is not configured. Please set it in config.py or as an environment variable.")
        sys.exit(1)
        
    bot = WikinewsBot()
    new_articles = bot.check_for_new_articles()

    if not new_articles:
        logger.info("No new articles found.")
        return

    logger.info(f"Found {len(new_articles)} new article(s).")
    latest_article_title = None
    for article_data in new_articles:
        details = bot.get_article_details(article_data)
        message = format_telegram_message(details)
        await broadcast_message(config.BOT_TOKEN, message)
        latest_article_title = details['title']

    # After processing all new articles, save the title of the very last one
    if latest_article_title:
        bot.save_last_checked_article(latest_article_title)

    logger.info("Bot check finished.")

if __name__ == '__main__':
    try:
        asyncio.run(main_async())
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)
