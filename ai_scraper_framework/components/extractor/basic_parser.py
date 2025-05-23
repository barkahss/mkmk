"""
Basic HTML parsing utility using BeautifulSoup.

This module provides the `BasicParser` class, which wraps BeautifulSoup
to offer simple methods for extracting common HTML elements like the page title
and hyperlinks from a given HTML content string.
"""
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

# Assuming ExtractorError is defined in the core exceptions module.
from ai_scraper_framework.core.exceptions import ExtractorError

class BasicParser:
    """
    A basic HTML parser that uses BeautifulSoup to extract common elements
    such as the page title and all hyperlinks from an HTML document.

    Attributes:
        soup (BeautifulSoup): An instance of BeautifulSoup representing the parsed HTML.
    """
    def __init__(self, html_content: str):
        """
        Initializes the BasicParser with the provided HTML content.

        Args:
            html_content (str): The HTML content string to be parsed.

        Raises:
            ExtractorError: If `html_content` is None, or if BeautifulSoup
                            encounters an unrecoverable error during parsing
                            (though BeautifulSoup is generally robust to malformed HTML).
        """
        if html_content is None:
            # Explicitly check for None, as BeautifulSoup might handle it in unexpected ways.
            raise ExtractorError("HTML content cannot be None for BasicParser.")
        
        try:
            # Initialize BeautifulSoup with the html.parser.
            # 'html.parser' is Python's built-in parser, requiring no external C dependencies like lxml.
            # For more complex scenarios or performance needs, 'lxml' or 'html5lib' could be considered.
            self.soup = BeautifulSoup(html_content, 'html.parser')
        except Exception as e:
            # Catching a broad exception during BeautifulSoup initialization,
            # as various issues (though rare for 'html.parser') could occur.
            raise ExtractorError(f"Failed to initialize BeautifulSoup parser: {e}")

    def get_title(self) -> Optional[str]:
        """
        Extracts the text content of the <title> tag from the parsed HTML.

        Returns:
            Optional[str]: The stripped text content of the page's title tag.
                           Returns None if the title tag is not found, or if it has no string content.
        """
        if self.soup and self.soup.title and self.soup.title.string:
            # Ensure the title tag and its string content exist, then strip whitespace.
            return self.soup.title.string.strip()
        return None # Return None if no title or title string is found.

    def get_links(self) -> List[Dict[str, str]]:
        """
        Extracts all hyperlinks (<a> tags that have an 'href' attribute) from the parsed HTML.

        Each link is returned as a dictionary containing its display text and the URL (href).

        Returns:
            List[Dict[str, str]]: A list of dictionaries. Each dictionary has:
                - 'text' (str): The stripped anchor text of the link.
                - 'href' (str): The value of the 'href' attribute (the URL).
            Returns an empty list if no valid links (<a> tags with href) are found.
        """
        links_data: List[Dict[str, str]] = []
        if not self.soup:
            # Should not happen if constructor succeeded, but defensive check.
            return links_data

        # Use soup.find_all() to get all <a> tags that possess an href attribute.
        # This efficiently filters out <a> tags used as anchors without actual links.
        for link_tag in self.soup.find_all('a', href=True):
            href: str = link_tag['href']  # 'href' is guaranteed to exist by the find_all condition.
            
            # Get the text content of the link.
            # strip=True removes leading/trailing whitespace and normalizes multiple spaces within text.
            text: str = link_tag.get_text(strip=True) 
            
            links_data.append({'text': text, 'href': href})
        
        return links_data

# The if __name__ == '__main__': block was removed as part of test formalization.
# Formal tests for this class are located in 'tests/components/extractor/test_basic_parser.py'.
