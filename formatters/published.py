import logging
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from sentence_splitter import split_into_sentences, cleanup_content
import config

logger = logging.getLogger(__name__)

class PublishedFormatter:
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

    def get_article_summary(self, title):
        """Extracts the first two sentences from a Wikinews article using comprehensive cleanup."""
        logger.info(f"Getting summary for article: {title}")

        # METHOD 1: Extract from full wikitext content
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
            if page_id != '-1':
                pages = wikitext_data['query']['pages'][page_id]
                if 'revisions' in pages and pages['revisions']:
                    full_wikitext = pages['revisions'][0]['slots']['main']['*']
                    logger.debug(f"Got FULL wikitext content, length: {len(full_wikitext)}")
                    
                    summary = cleanup_content(full_wikitext, sentence_count=2)
                    if summary and len(summary.strip()) > 10:
                        logger.info(f"SUCCESS: Summary from FULL wikitext: '{summary[:150]}...'")
                        return summary
                    else:
                        logger.warning(f"Wikitext cleanup produced insufficient content: '{summary}'")

        # METHOD 2: Extract from full parsed HTML content
        logger.info("Trying to get FULL parsed HTML content")
        full_html_params = {
            "action": "parse", 
            "page": title, 
            "prop": "text",
            "format": "json"
        }
        full_html_data = self._make_api_request(full_html_params)
        
        if (full_html_data and 'parse' in full_html_data and 'text' in full_html_data['parse']):
            raw_html = full_html_data['parse']['text']['*']
            logger.debug(f"Got FULL HTML content, length: {len(raw_html)}")
            
            soup = BeautifulSoup(raw_html, 'html.parser')
            all_text = soup.get_text()
            logger.debug(f"Extracted all text from HTML, length: {len(all_text)}")
            
            sentences = split_into_sentences(all_text)
            logger.debug(f"Split full text into {len(sentences)} sentences")
            
            if sentences:
                # Filter out very short sentences to get meaningful content
                meaningful_sentences = []
                for i, sentence in enumerate(sentences):
                    clean_sentence = sentence.strip()
                    if len(clean_sentence) > 15:
                        meaningful_sentences.append(clean_sentence)
                        logger.debug(f"Meaningful sentence {len(meaningful_sentences)}: '{clean_sentence[:100]}...'")
                        if len(meaningful_sentences) >= 2:
                            break
                
                if meaningful_sentences:
                    summary = ' '.join(meaningful_sentences[:2])
                    logger.info(f"SUCCESS: Summary from FULL HTML: '{summary[:150]}...'")
                    return summary
        
        # METHOD 3: Fallback to first section only
        logger.info("Falling back to first section only method")
        params = {
            "action": "parse", "page": title, "prop": "text",
            "section": 0, "format": "json"
        }
        data = self._make_api_request(params)
        if not (data and 'parse' in data and 'text' in data['parse']):
            logger.error(f"Failed to get content for '{title}' - API response: {data}")
            return ""

        raw_html = data['parse']['text']['*']
        logger.debug(f"Fallback: First section HTML length: {len(raw_html)}")

        soup = BeautifulSoup(raw_html, 'html.parser')
        paragraphs = soup.find_all('p')
        logger.debug(f"Found {len(paragraphs)} paragraph elements")

        first_paragraph = None
        for i, p in enumerate(paragraphs):
            text_content = p.get_text().strip()
            logger.debug(f"Paragraph {i}: '{text_content[:100]}...' (length: {len(text_content)})")
            
            # Skip empty paragraphs or very short ones
            if text_content and len(text_content) > 20:
                first_paragraph = p
                break
        
        if not first_paragraph:
            logger.warning(f"No suitable paragraph found for '{title}'")
            # Try to get any text content as fallback
            all_text = soup.get_text().strip()
            logger.debug(f"Fallback: Using all text content (length: {len(all_text)})")
            if all_text:
                sentences = split_into_sentences(all_text)
                if sentences:
                    summary = ' '.join(sentences[:2])
                    logger.info(f"Fallback summary extracted: '{summary[:100]}...'")
                    return summary
            return ""
        
        text = first_paragraph.get_text().strip()
        logger.debug(f"First paragraph text: '{text[:200]}...' (full length: {len(text)})")
        
        sentences = split_into_sentences(text)
        logger.debug(f"Split into {len(sentences)} sentences:")
        for i, sentence in enumerate(sentences[:3]):
            logger.debug(f"  Sentence {i+1}: '{sentence.strip()}'")
        
        if not sentences:
            logger.warning(f"No sentences found after splitting for '{title}'")
            return ""
        
        summary = ' '.join(sentences[:2])
        logger.info(f"Final summary for '{title}': '{summary[:100]}...' (full length: {len(summary)})")
        return summary

    def format_message(self, article_data, url_slug):
        """Creates the message for a 'Published' article."""
        title = article_data['title']
        page_url = f"{self.base_url}{url_slug}"
        
        summary = self.get_article_summary(title)
        date = datetime.strptime(article_data['timestamp'], "%Y-%m-%dT%H:%M:%SZ").strftime(config.DATE_FORMAT)
        
        details = {
            'title': title,
            'summary': summary,
            'date': date,
            'url': page_url,
            'talk_page_url': f"{self.base_url}Talk:{url_slug}",
            'history_url': f"{self.api_url.replace('api.php', 'index.php')}?title={url_slug}&action=history"
        }

        message = f"*{details['title']}*\n\n"
        message += f"{details['date']}\n\n"
        if details['summary']:
            message += f"{details['summary']}\n\n"
            logger.info(f"Added summary to message: '{details['summary'][:50]}...'")
        else:
            logger.warning("No summary available for message")
        message += f"[Read more...]({details['url']})\n\n"
        message += f"([Talk page]({details['talk_page_url']}) | [History]({details['history_url']}))"
        
        return message
