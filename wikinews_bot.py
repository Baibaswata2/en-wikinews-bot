# wikinews_bot.py

import requests
import logging
import json
import os
import sys
import asyncio
import re
from bs4 import BeautifulSoup
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

# Import settings from the configuration file
import config
# Import the complete content processing functions
from sentence_splitter import split_into_sentences, cleanup_content

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=config.LOGGING_LEVEL
)
logger = logging.getLogger(__name__)

def escape_markdown_v2(text: str) -> str:
    """Escapes text for Telegram's MarkdownV2 parse mode."""
    if not isinstance(text, str):
        return ''
    # A list of characters to escape
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    # Use re.sub to escape only the characters in the list
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

class WikinewsBot:
    """A bot to monitor a specific Wikinews category based on a given configuration."""
    def __init__(self, category_config):
        self.config = category_config
        self.api_url = config.WIKI_API_URL
        self.base_url = config.WIKI_BASE_URL
        self.state_file_path = self._get_state_file_path()
        self.last_checked_article_title = self.load_last_checked_article_title()

        self.headers = {
            'User-Agent': 'WikinewsTelegramBot/1.2 (https://github.com/Baibaswata2/en-wikinews-bot; baibaswataray@gmail.com)'
        }

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

    def get_article_summary(self, title):
        """Extracts the first two sentences from a Wikinews article using comprehensive cleanup."""
        logger.info(f"Getting summary for article: {title}")
        
        # METHOD 1: Get the FULL wikitext content (not just first section)
        wikitext_params = {
            "action": "query", 
            "titles": title, 
            "prop": "revisions",
            "rvprop": "content", 
            "rvslots": "main", 
            "format": "json"
        }
        wikitext_data = self._make_api_request(wikitext_params)
        
        if (wikitext_data and 'query' in wikitext_data and 'pages' in wikitext_data['query']):
            page_id = list(wikitext_data['query']['pages'].keys())[0]
            if page_id != '-1': # Page exists
                pages = wikitext_data['query']['pages'][page_id]
                if 'revisions' in pages and pages['revisions']:
                    # Get the FULL wikitext content
                    full_wikitext = pages['revisions'][0]['slots']['main']['*']
                    logger.debug(f"Got FULL wikitext content, length: {len(full_wikitext)}")
                    logger.debug(f"First 500 chars of wikitext: {full_wikitext[:500]}")
                    
                    # Use the comprehensive cleanup function on FULL content
                    summary = cleanup_content(full_wikitext, sentence_count=2)
                    if summary and len(summary.strip()) > 10: # Make sure we got meaningful content
                        logger.info(f"SUCCESS: Summary from FULL wikitext: '{summary[:150]}...'")
                        return summary
                    else:
                        logger.warning(f"Wikitext cleanup produced insufficient content: '{summary}'")

        # METHOD 2: Get FULL parsed HTML content (not just section 0)
        logger.info("Trying to get FULL parsed HTML content")
        full_html_params = {
            "action": "parse", 
            "page": title, 
            "prop": "text",
            # Remove section=0 to get FULL content
            "format": "json"
        }
        full_html_data = self._make_api_request(full_html_params)
        
        if (full_html_data and 'parse' in full_html_data and 'text' in full_html_data['parse']):
            raw_html = full_html_data['parse']['text']['*']
            logger.debug(f"Got FULL HTML content, length: {len(raw_html)}")
            
            soup = BeautifulSoup(raw_html, 'html.parser')
            
            # Get ALL text content from the full HTML
            all_text = soup.get_text()
            logger.debug(f"Extracted all text from HTML, length: {len(all_text)}")
            logger.debug(f"First 500 chars of extracted text: {all_text[:500]}")
            
            # Use sentence splitter on the full text
            sentences = split_into_sentences(all_text)
            logger.debug(f"Split full text into {len(sentences)} sentences")
            
            if sentences:
                # Filter sentences to get meaningful content (skip very short ones)
                meaningful_sentences = []
                for i, sentence in enumerate(sentences):
                    clean_sentence = sentence.strip()
                    if len(clean_sentence) > 15: # Skip very short sentences
                        meaningful_sentences.append(clean_sentence)
                        logger.debug(f"Meaningful sentence {len(meaningful_sentences)}: '{clean_sentence[:100]}...'")
                        if len(meaningful_sentences) >= 2:
                            break
                
                if meaningful_sentences:
                    summary = ' '.join(meaningful_sentences[:2])
                    logger.info(f"SUCCESS: Summary from FULL HTML: '{summary[:150]}...'")
                    return summary
        
        # METHOD 3: Fallback to first section only (original method)
        logger.info("Falling back to first section only method")
        params = {
            "action": "parse", "page": title, "prop": "text",
            "section": 0, "format": "json"
        }
        data = self._make_api_request(params)
        if not (data and 'parse' in data and 'text' in data['parse']):
            logger.error(f"Failed to get any content for '{title}'")
            return ""
        
        raw_html = data['parse']['text']['*']
        logger.debug(f"Fallback: First section HTML length: {len(raw_html)}")
        
        soup = BeautifulSoup(raw_html, 'html.parser')
        paragraphs = soup.find_all('p')
        
        for i, p in enumerate(paragraphs):
            text_content = p.get_text().strip()
            if text_content and len(text_content) > 20:
                sentences = split_into_sentences(text_content)
                if sentences and len(sentences) >= 1:
                    summary = ' '.join(sentences[:2]) if len(sentences) >= 2 else sentences[0]
                    logger.info(f"FALLBACK: Summary from first section: '{summary[:100]}...'")
                    return summary
        
        logger.error(f"Could not extract any meaningful content from '{title}'")
        return ""

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
        
        first_rev = revisions[-1]
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
            last_idx = next(i for i, a in enumerate(all_articles) if a['title'] == self.last_checked_article_title)
            new_articles = all_articles[:last_idx]
        except StopIteration:
            logger.warning(f"[{self.config['category_name']}] Last checked article not found. Processing latest.")
            new_articles = [all_articles[0]]
        
        return new_articles[::-1]

async def broadcast_message(bot, message, targets):
    """Sends a formatted message to a list of Telegram targets using MarkdownV2."""
    for target in targets:
        try:
            await bot.send_message(
                chat_id=target['chat_id'],
                message_thread_id=target.get('thread_id'),
                text=message,
                parse_mode='MarkdownV2', # Use the more reliable MarkdownV2
                disable_web_page_preview=True
            )
            logger.info(f"Successfully sent message to target: {target}")
        except TelegramError as e:
            logger.error(f"Failed to send message to {target}: {e}")

def format_published_message(details):
    """Creates the message for a 'Published' article using MarkdownV2."""
    title = escape_markdown_v2(details['title'])
    date = escape_markdown_v2(details['date'])
    
    message = f"**{title}**\n\n"
    message += f"{date}\n\n"
    if details['summary']:
        summary = escape_markdown_v2(details['summary'])
        message += f"{summary}\n\n"
        logger.info(f"Added summary to message: '{details['summary'][:50]}...'")
    else:
        logger.warning("No summary available for message")
    message += f"[Read more...]({details['url']})\n\n"
    message += f"([Talk page]({details['talk_page_url']}) | [History]({details['history_url']}))"
    return message

def format_developing_message(details):
    """Creates the message for a 'Developing' article with the new format using MarkdownV2."""
    def format_user_link(username):
        """Helper to create a MarkdownV2 link for a wiki user."""
        if not username or username == 'N/A':
            return 'N/A'
        user_url_slug = username.replace(' ', '_')
        user_url = f"{config.WIKI_BASE_URL}User:{user_url_slug}"
        return f"[{escape_markdown_v2(username)}]({user_url})"

    escaped_title = escape_markdown_v2(details['title'])
    created_date = escape_markdown_v2(details['created_date'])

    message = (
        f"📝 **New draft article started**\n"
        f"**Title:** [{escaped_title}]({details['url']})\n\n"
        f"**Created on:** {created_date}\n"
        f"**Created by:** {format_user_link(details.get('creator', 'N/A'))}\n"
        f"**Last edited by:** {format_user_link(details.get('editor', 'N/A'))}\n\n"
        f"([Help improve this draft]({details['edit_url']}) • [Join the discussion]({details['talk_page_url']}))"
    )
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
        latest_article_data = None

        for article_data in new_articles:
            title = article_data['title']
            # Correctly replace spaces with underscores for the URL path
            url_slug = title.replace(' ', '_')
            page_url = f"{config.WIKI_BASE_URL}{url_slug}"
            
            details = {'title': title, 'url': page_url}

            if category_config['message_type'] == 'published':
                summary = bot_instance.get_article_summary(title)
                details.update({
                    'summary': summary,
                    'date': datetime.strptime(article_data['timestamp'], "%Y-%m-%dT%H:%M:%SZ").strftime(config.DATE_FORMAT),
                    'talk_page_url': f"{config.WIKI_BASE_URL}Talk:{url_slug}",
                    'history_url': f"{config.WIKI_API_URL.replace('api.php', 'index.php')}?title={url_slug}&action=history"
                })
                message = format_published_message(details)

            elif category_config['message_type'] == 'developing':
                rev_details = bot_instance.get_article_revision_details(title)
                created_dt = datetime.strptime(rev_details.get('created_utc', article_data['timestamp']), "%Y-%m-%dT%H:%M:%SZ")
                details.update({
                    'creator': rev_details.get('creator', 'N/A'),
                    'editor': rev_details.get('editor', 'N/A'),
                    # Match the format: "September 26, 2025, 11:41 UTC"
                    'created_date': created_dt.strftime("%B %d, %Y, %H:%M UTC"),
                    'edit_url': f"{config.WIKI_API_URL.replace('api.php', 'index.php')}?title={url_slug}&action=edit",
                    'talk_page_url': f"{config.WIKI_BASE_URL}Talk:{url_slug}"
                })
                message = format_developing_message(details)

            else:
                logger.warning(f"Unknown message type '{category_config['message_type']}'. Skipping.")
                continue

            logger.info(f"Final message for '{title}':\n{message}")
            await broadcast_message(telegram_bot, message, category_config['telegram_targets'])
            latest_article_data = article_data
        
        if latest_article_data:
            bot_instance.save_last_checked_article(latest_article_data)

if __name__ == '__main__':
    try:
        asyncio.run(main_async())
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)
