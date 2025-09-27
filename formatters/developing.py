import logging
import requests
from datetime import datetime
import config

logger = logging.getLogger(__name__)

class DevelopingFormatter:
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

    def format_message(self, article_data, url_slug):
        """Creates the message for a 'Developing' article with proper formatting."""
        def user_link(user):
            user_url_slug = user.replace(' ', '_')
            user_page_url = f"https://en.wikinews.org/wiki/User:{user_url_slug}"
            return f"[{user}]({user_page_url})"

        title = article_data['title']
        article_url = f"https://en.wikinews.org/wiki/{url_slug}"
        
        rev_details = self.get_article_revision_details(title)
        created_dt = datetime.strptime(rev_details['created_utc'], "%Y-%m-%dT%H:%M:%SZ")
        
        message = "📰 New draft article started\n\n"
        message += f"**Title:** [{title}]({article_url})\n\n"
        message += f"**Created on:** {created_dt.strftime(f'{config.DATE_FORMAT} %H:%M UTC')}\n"
        message += f"**Created by:** {user_link(rev_details.get('creator', 'N/A'))}\n"
        message += f"**Last edited by:** {user_link(rev_details.get('editor', 'N/A'))}\n\n"
        
        edit_url = f"https://en.wikinews.org/w/index.php?title={url_slug}&action=edit"
        talk_url = f"https://en.wikinews.org/wiki/Talk:{url_slug}"
        
        message += f"([Help improve this draft]({edit_url}) • [Join the discussion]({talk_url}))"
        
        return message
