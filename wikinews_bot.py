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

# How many historical (already-removed) titles to remember in the notified set.
# Prevents the set from growing unboundedly over time.
MAX_NOTIFIED_HISTORY = 200


class WikinewsBot:
    """A bot to monitor a specific Wikinews category based on a given configuration."""

    def __init__(self, category_config):
        self.config = category_config
        self.api_url = config.WIKI_API_URL
        self.base_url = config.WIKI_BASE_URL
        self.state_file_path = self._get_state_file_path()

        self.headers = {
            'User-Agent': 'WikinewsTelegramBot/1.1 (https://github.com/Baibaswata2/en-wikinews-bot; baibaswataray@gmail.com)'
        }

        # --- State loading (strategy differs by message type) ---
        msg_type = category_config['message_type']

        if msg_type in ('developing', 'review'):
            # These categories use a notified-set strategy to avoid duplicate
            # notifications when a newer article is removed from the category.
            self.notified_titles = self._load_notified_titles()
            self.last_checked_article_title = None   # not used for these types
        else:
            # 'published' keeps the original single-title / timestamp strategy.
            self.notified_titles = None
            self.last_checked_article_title = self._load_last_checked_article_title()

        # Initialize appropriate formatter
        if msg_type == 'published':
            self.formatter = PublishedFormatter(self.api_url, self.base_url, self.headers)
        elif msg_type == 'developing':
            self.formatter = DevelopingFormatter(self.api_url, self.base_url, self.headers)
        elif msg_type == 'review':
            self.formatter = ReviewFormatter(self.api_url, self.base_url, self.headers)
        else:
            raise ValueError(f"Unknown message type: {msg_type}")

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _get_state_file_path(self):
        """Determines the correct path for the state file."""
        if os.environ.get('GITHUB_WORKSPACE'):
            return os.path.join(os.environ.get('GITHUB_WORKSPACE'), self.config['state_file'])
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config['state_file'])

    # ------------------------------------------------------------------
    # State loading
    # ------------------------------------------------------------------

    def _load_last_checked_article_title(self):
        """(Published) Loads the last checked article title from the state file."""
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

    def _load_notified_titles(self):
        """
        (Developing / Review) Loads the set of already-notified article titles.

        Supports two state-file formats:
          - New format: {"notified_titles": ["Title A", "Title B", ...]}
          - Old format: {"title": "...", "timestamp": "..."}  (migrated automatically)
        """
        try:
            if os.path.exists(self.state_file_path):
                with open(self.state_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # New format
                if 'notified_titles' in data:
                    titles = set(data['notified_titles'])
                    logger.info(
                        f"[{self.config['category_name']}] Loaded {len(titles)} notified title(s)."
                    )
                    return titles

                # Old format — migrate on the fly
                if 'title' in data and data['title']:
                    logger.info(
                        f"[{self.config['category_name']}] Migrating old state format. "
                        f"Seeding notified set with: {data['title']}"
                    )
                    return {data['title']}

        except Exception as e:
            logger.error(f"[{self.config['category_name']}] Error loading state file: {e}")

        # No usable state file — seed from config if available
        initial = self.config.get('initial_article')
        if initial:
            logger.warning(
                f"[{self.config['category_name']}] State file not found. "
                f"Seeding notified set with initial_article: {initial}"
            )
            return {initial}

        logger.warning(
            f"[{self.config['category_name']}] No state file and no initial_article. "
            f"Starting with empty notified set."
        )
        return set()

    # ------------------------------------------------------------------
    # State saving
    # ------------------------------------------------------------------

    def save_last_checked_article(self, article_data):
        """(Published) Saves the latest article data to the state file."""
        try:
            with open(self.state_file_path, 'w', encoding='utf-8') as f:
                state_to_save = {
                    'title': article_data.get('title'),
                    'timestamp': article_data.get('timestamp')
                }
                json.dump(state_to_save, f, ensure_ascii=False, indent=4)
            logger.info(
                f"[{self.config['category_name']}] Saved last checked article: {article_data.get('title')}"
            )
        except Exception as e:
            logger.error(f"[{self.config['category_name']}] Error saving state file: {e}")

    def save_notified_titles(self, current_category_titles):
        """
        (Developing / Review) Persists the notified set to the state file.

        Pruning strategy: keep ALL titles currently in the category (so we never
        re-notify them even if the category fluctuates), plus the most recent
        MAX_NOTIFIED_HISTORY titles that have already left the category.
        This bounds file growth while still preventing re-notification of
        recently removed articles.
        """
        current_set = set(current_category_titles)

        # Split notified titles into "still in category" and "already left"
        still_in = [t for t in self.notified_titles if t in current_set]
        already_left = [t for t in self.notified_titles if t not in current_set]

        # Keep only the tail of the historical list to cap growth
        pruned_left = already_left[-MAX_NOTIFIED_HISTORY:]

        final_list = still_in + pruned_left

        try:
            with open(self.state_file_path, 'w', encoding='utf-8') as f:
                json.dump({'notified_titles': final_list}, f, ensure_ascii=False, indent=4)
            logger.info(
                f"[{self.config['category_name']}] Saved notified set: "
                f"{len(still_in)} in-category + {len(pruned_left)} historical = {len(final_list)} total."
            )
        except Exception as e:
            logger.error(f"[{self.config['category_name']}] Error saving state file: {e}")

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # New-article detection
    # ------------------------------------------------------------------

    def check_for_new_articles(self):
        """
        Checks for new articles and returns them in chronological order
        (oldest first), ready for sequential notification.

        - For 'developing' and 'review': returns every article currently in
          the category that has NOT yet been notified. This is immune to
          removals because membership in notified_titles is permanent.

        - For 'published': keeps the original index-based logic which is
          safe because published articles are never un-published.
        """
        all_articles = self.get_category_members()
        if not all_articles:
            logger.info(f"[{self.config['category_name']}] No articles found.")
            return []

        msg_type = self.config['message_type']

        # ---- Developing / Review: notified-set strategy ----
        if msg_type in ('developing', 'review'):
            # Bootstrap: if the notified set is empty, seed it silently with
            # whatever is currently in the category so we don't spam on first run.
            if not self.notified_titles:
                logger.info(
                    f"[{self.config['category_name']}] Empty notified set on first run. "
                    f"Seeding with {len(all_articles)} current article(s) — no messages sent."
                )
                self.notified_titles = {a['title'] for a in all_articles}
                self.save_notified_titles([a['title'] for a in all_articles])
                return []

            new_articles = [a for a in all_articles if a['title'] not in self.notified_titles]

            # Return in chronological order (oldest first) so messages arrive in order
            new_articles_sorted = new_articles[::-1]

            logger.info(
                f"[{self.config['category_name']}] {len(new_articles_sorted)} new article(s) "
                f"(out of {len(all_articles)} in category, "
                f"{len(self.notified_titles)} already notified)."
            )
            return new_articles_sorted

        # ---- Published: original index-based strategy ----
        # For Review category, if no initial article is set, use the first article found
        if not self.last_checked_article_title and self.config['category_name'] == 'Review':
            if all_articles:
                self.last_checked_article_title = all_articles[0]['title']
                logger.info(
                    f"[{self.config['category_name']}] Setting initial article to: "
                    f"{self.last_checked_article_title}"
                )
                return []

        try:
            last_idx = next(
                i for i, a in enumerate(all_articles)
                if a['title'] == self.last_checked_article_title
            )
            new_articles = all_articles[:last_idx]
        except StopIteration:
            logger.warning(
                f"[{self.config['category_name']}] Last checked article not found. Processing latest."
            )
            new_articles = [all_articles[0]] if all_articles else []

        return new_articles[::-1]


# ------------------------------------------------------------------
# Telegram helpers
# ------------------------------------------------------------------

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


# ------------------------------------------------------------------
# Main — farewell run
# ------------------------------------------------------------------

FAREWELL_MESSAGE = (
    "Hello community, I am the notification bot. I will stop working from today. "
    "I may be reactivated in the future with the new Wikinews Pulse site. "
    "Until then, goodbye and thank you all."
)

FAREWELL_TARGETS = [
    {"chat_id": "-1002591426405", "thread_id": "5"},
    {"chat_id": "-1002113193375", "thread_id": "1112"},
]

async def main_async():
    """Sends the farewell message to the specified targets and exits."""
    if not config.BOT_TOKEN:
        logger.error("Telegram bot token is not configured.")
        sys.exit(1)

    telegram_bot = Bot(token=config.BOT_TOKEN)

    logger.info("Sending farewell message...")
    await broadcast_message(telegram_bot, FAREWELL_MESSAGE, FAREWELL_TARGETS)
    logger.info("Farewell message sent. Bot is shutting down.")


if __name__ == '__main__':
    try:
        asyncio.run(main_async())
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)
