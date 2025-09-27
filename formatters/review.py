import logging
import requests
import re
from datetime import datetime
import config

logger = logging.getLogger(__name__)

class ReviewFormatter:
    def __init__(self, api_url, base_url, headers):
        self.api_url = api_url
        self.base_url = base_url
        self.headers = headers

    def _make_api_request(self, params):
        """Helper function to make API requests with the required User-Agent."""
        try:
            response = requests.get(self.api_url, params=params, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None

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
        if not revisions: 
            return {}

        first_rev = revisions[-1]
        last_rev = revisions[0]

        return {
            'creator': first_rev.get('user'),
            'editor': last_rev.get('user'),
            'created_utc': first_rev.get('timestamp')
        }

    def get_talk_page_content(self, title):
        """Gets the content of the talk page for an article."""
        talk_title = f"Talk:{title}"
        params = {
            "action": "query", 
            "titles": talk_title, 
            "prop": "revisions",
            "rvprop": "content", 
            "rvslots": "main", 
            "format": "json"
        }
        data = self._make_api_request(params)
        
        if not data or 'query' not in data or 'pages' not in data['query']:
            logger.warning(f"No talk page data found for {talk_title}")
            return ""

        page_id = list(data['query']['pages'].keys())[0]
        if page_id == '-1':
            logger.info(f"Talk page does not exist for {talk_title}")
            return ""

        pages = data['query']['pages'][page_id]
        if 'revisions' not in pages or not pages['revisions']:
            logger.info(f"No revisions found for talk page {talk_title}")
            return ""

        content = pages['revisions'][0]['slots']['main']['*']
        logger.debug(f"Talk page content length for {talk_title}: {len(content)}")
        return content

    def count_peer_review_templates(self, talk_content):
        """Counts the number of peer_reviewed templates in the talk page content."""
        if not talk_content:
            return 0

        # Pattern to match {{peer_reviewed or {{peer reviewed (case insensitive)
        # This handles both single line and multiline templates
        pattern = r'\{\{\s*peer_?reviewed\s*(?:\|[^}]*)*\}\}'
        matches = re.findall(pattern, talk_content, re.IGNORECASE | re.DOTALL)
        
        count = len(matches)
        logger.info(f"Found {count} peer_reviewed template(s) in talk page")
        
        # Log the matches for debugging
        for i, match in enumerate(matches, 1):
            logger.debug(f"Peer review template {i}: {match[:100]}...")
        
        return count

    def get_review_attempt_number(self, title):
        """Determines if this is the 1st, 2nd, or 3rd review attempt."""
        talk_content = self.get_talk_page_content(title)
        peer_review_count = self.count_peer_review_templates(talk_content)
        
        # If no peer review templates, this is the 1st time
        # If 1 template, this is the 2nd time (1st review completed)
        # If 2 templates, this is the 3rd time (2nd review completed)
        attempt_number = peer_review_count + 1
        
        logger.info(f"Article '{title}' is being submitted for review for the {attempt_number} time")
        return attempt_number

    def format_message(self, article_data, url_slug):
        """Creates the message for a 'Review' article."""
        def user_link(user):
            user_url_slug = user.replace(' ', '_')
            user_page_url = f"https://en.wikinews.org/wiki/User:{user_url_slug}"
            return f"[{user}]({user_page_url})"

        def ordinal(n):
            """Convert number to ordinal (1st, 2nd, 3rd, etc.)"""
            if 10 <= n % 100 <= 20:
                suffix = 'th'
            else:
                suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
            return f"{n}{suffix}"

        title = article_data['title']
        article_url = f"https://en.wikinews.org/wiki/{url_slug}"
        
        # Get revision details
        rev_details = self.get_article_revision_details(title)
        created_dt = datetime.strptime(rev_details['created_utc'], "%Y-%m-%dT%H:%M:%SZ")
        
        # Determine review attempt number
        attempt_number = self.get_review_attempt_number(title)
        attempt_ordinal = ordinal(attempt_number)
        
        # Build the message
        message = f"**[{title}]({article_url})** has been submitted for review for {attempt_ordinal} time.\n\n"
        message += f"**Created on:** {created_dt.strftime(f'{config.DATE_FORMAT} %H:%M UTC')}\n"
        message += f"**Created by:** {user_link(rev_details.get('creator', 'N/A'))}\n"
        message += f"**Last edited by:** {user_link(rev_details.get('editor', 'N/A'))}\n\n"
        
        talk_url = f"https://en.wikinews.org/wiki/Talk:{url_slug}"
        message += f"([Join the discussion]({talk_url}))"
        
        return message
