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
    """A bot to monitor a specific Wikinews category based on a given configuration."""
    def __init__(self, category_config):
        self.config = category_config
        self.api_url = config.WIKI_API_URL
        self.base_url = config.WIKI_BASE_URL
        self.state_file_path = self._get_state_file_path()
        self.last_checked_article = self.load_last_checked_article()

        self.headers = {
            'User-Agent': 'WikinewsTelegramBot/1.1 (https://github.com/Baibaswata2/en-wikinews-bot; baibaswataray@gmail.com)'
        }

    def _get_state_file_path(self):
        """Determines the correct path for the state file."""
        if os.environ.get('GITHUB_WORKSPACE'):
            return os.path.join(os.environ.get('GITHUB_WORKSPACE'), self.config['state_file'])
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config['state_file'])

    def load_last_checked_article(self):
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

    def save_last_checked_article(self, title):
        """Saves the latest article title to the state file."""
        try:
            with open(self.state_file_path, 'w', encoding='utf-8') as f:
                json.dump({'title': title}, f, ensure_ascii=False, indent=4)
            logger.info(f"[{self.config['category_name']}] Saved last checked article: {title}")
        except Exception as e:
            logger.error(f"[{self.config['category_name']}] Error saving state file: {e}")

    def _make_api_request(self, params):
        """Helper function to make API requests with the required User-Agent."""
        try:
            # Add the headers to every request made to the API
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
            "cmlimit": 50, "cmsort": "timestamp", "cmdir": "desc", "format": "json"
        }
        data = self._make_api_request(params)
        return data.get('query', {}).get('categorymembers', []) if data else []

    def get_article_summary(self, title):
        """Extracts the first two sentences from a Wikinews article."""
        params = {
            "action": "parse", "page": title, "prop": "text",
            "section": 0, "format": "json"
        }
        data = self._make_api_request(params)
        if not (data and 'parse' in data and 'text' in data['parse']):
            logger.error(f"Failed to get content for '{title}'")
            return ""
        
        soup = BeautifulSoup(data['parse']['text']['*'], 'html.parser')
        first_paragraph = soup.find('p', string=lambda t: t and t.strip())
        if not first_paragraph: return ""
        
        text = first_paragraph.get_text().strip()
        sentences = text.split('. ')
        summary = '. '.join(sentences[:2])
        return summary + '.' if not summary.endswith('.') else summary

    def get_article_revision_details(self, title):
        """Gets creator, editor, and creation time for an article."""
        params = {
            "action": "query", "titles": title, "prop": "revisions",
            "rvprop": "user|timestamp", "rvlimit": "max", "format": "json"
        }
        data = self._make_api_request(params)
        if not data or not data.get('query', {}).get('pages'):
            return {}
        
        page_id = list(data['query']['pages'].keys())[0]
        revisions = data['query']['pages'][page_id].get('revisions', [])
        if not revisions: return {}
        
        first_rev = revisions[-1] # First revision is the last in the list
        last_rev = revisions[0]
        
        return {
            'creator': first_rev.get('user'),
            'editor': last_rev.get('user'),
            'created_utc': first_rev.get('timestamp')
        }

    def check_for_new_articles(self):
        """Checks for new articles since the last run and returns them in chronological order."""
        all_articles = self.get_category_members()
        if not all_articles:
            logger.info(f"[{self.config['category_name']}] No articles found.")
            return []

        try:
            last_idx = next(i for i, a in enumerate(all_articles) if a['title'] == self.last_checked_article)
            new_articles = all_articles[:last_idx]
        except StopIteration:
            logger.warning(f"[{self.config['category_name']}] Last checked article not found. Processing latest.")
            new_articles = [all_articles[0]]
        
        return new_articles[::-1] # Oldest to newest

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

def format_published_message(details):
    """Creates the message for a 'Published' article."""
    message = f"*{details['title']}*\n\n"
    message += f"{details['date']}\n\n"
    if details['summary']:
        message += f"{details['summary']}\n\n"
    message += f"[Read more...]({details['url']})\n\n"
    message += f"([Talk page]({details['talk_page_url']}) | [History]({details['history_url']}))"
    return message

def format_developing_message(details):
    """Creates the message for a 'Developing' article."""
    def user_link(user):
        user_url_slug = user.replace(' ', '_')
        return f"[{user}](https://en.wikinews.org/wiki/User:{user_url_slug}) ([talk](https://en.wikinews.org/wiki/User_talk:{user_url_slug}))"

    message = "A new draft has started....\n\n"
    message += f"*[_{details['title']}_]({details['url']})*\n\n"
    message += f"Page created on: {details['created_date']}\n"
    message += f"Created by: {user_link(details['creator'])}\n"
    message += f"Last edited: {user_link(details['editor'])}\n\n"
    message += f"([Help develop the article]({details['edit_url']}) | [discuss it]({details['talk_page_url']}))"
    return message

async def main_async():
    """Main function to run the bot check for all configured categories."""
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
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
        latest_article_title = None

        for article_data in new_articles:
            title = article_data['title']
            url_slug = title.replace(' ', '_')
            page_url = f"{config.WIKI_BASE_URL}{url_slug}"
            
            details = {'title': title, 'url': page_url}

            if category_config['message_type'] == 'published':
                details.update({
                    'summary': bot_instance.get_article_summary(title),
                    'date': datetime.strptime(article_data['timestamp'], "%Y-%m-%dT%H:%M:%SZ").strftime(config.DATE_FORMAT),
                    'talk_page_url': f"{config.WIKI_BASE_URL}Talk:{url_slug}",
                    'history_url': f"{config.WIKI_API_URL.replace('api.php', 'index.php')}?title={url_slug}&action=history"
                })
                message = format_published_message(details)

            elif category_config['message_type'] == 'developing':
                rev_details = bot_instance.get_article_revision_details(title)
                created_dt = datetime.strptime(rev_details['created_utc'], "%Y-%m-%dT%H:%M:%SZ")
                details.update({
                    'creator': rev_details.get('creator', 'N/A'),
                    'editor': rev_details.get('editor', 'N/A'),
                    'created_date': created_dt.strftime(f"{config.DATE_FORMAT} %H:%M UTC"),
                    'edit_url': f"{config.WIKI_API_URL.replace('api.php', 'index.php')}?title={url_slug}&action=edit",
                    'talk_page_url': f"{config.WIKI_BASE_URL}Talk:{url_slug}"
                })
                message = format_developing_message(details)

            else:
                logger.warning(f"Unknown message type '{category_config['message_type']}'. Skipping.")
                continue

            await broadcast_message(telegram_bot, message, category_config['telegram_targets'])
            latest_article_title = title
        
        if latest_article_title:
            bot_instance.save_last_checked_article(latest_article_title)

if __name__ == '__main__':
    try:
        asyncio.run(main_async())
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)

