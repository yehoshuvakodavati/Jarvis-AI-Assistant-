import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin, urlparse, parse_qs, unquote
import re
from config import (
    SEARCH_TIMEOUT, CONTENT_FETCH_TIMEOUT,
    MAX_CONTENT_LENGTH, MIN_CONTENT_LENGTH,
    USER_AGENT, UNWANTED_PHRASES, UNWANTED_TAGS,
    AD_INDICATORS, LOG_LEVEL
)

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

import requests
from bs4 import BeautifulSoup


def search_web(query):
    url = f"https://html.duckduckgo.com/html/?q={query}"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "lxml")

    results = []

    for a in soup.select(".result__a"):
        link = a.get("href")
        if link:
            results.append(link)

    return results[:3]   # top 3 results
def extract_text(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5)

        soup = BeautifulSoup(res.text, "lxml")

        # remove junk tags
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()

        text = soup.get_text(separator=" ")

        return text[:3000]   # limit size

    except:
        return ""
def search_and_summarize(query):
    links = search_web(query)

    combined_text = ""

    for link in links:
        content = extract_text(link)
        if content:
            combined_text += content

    if not combined_text:
        return "Commander, I could not find useful information"

    from brain import ask_jarvis

    summary = ask_jarvis(
        f"Extract only useful information and give short answer:\n{combined_text}"
    )

    return f"Commander, {summary}"
def _decode_ddg_url(href):
    """Decode DuckDuckGo redirect URLs to real destination URLs."""
    if not href:
        return None
    if href.startswith("/l/?"):
        parsed = urlparse(href)
        query_params = parse_qs(parsed.query)
        uddg = query_params.get("uddg")
        if uddg:
            return unquote(uddg[0])
    return href


def _clean_query_tokens(query):
    normalized = re.sub(r"[^a-z0-9]+", " ", query.lower())
    return [token for token in normalized.split() if len(token) > 2]


def _score_link(link, title, query):
    """Score search result relevance based on query terms."""
    if not link or not link.startswith("http"):
        return 0
    tokens = _clean_query_tokens(query)
    score = 0
    text = (title or "") + " " + link
    text = text.lower()
    for token in tokens:
        if token in text:
            score += 10
    if "wikipedia.org" in link:
        score += 5
    if "duckduckgo.com" in link or "facebook.com" in link or "twitter.com" in link:
        score -= 20
    return score

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}


def search_duckduckgo(query):
    """
    Search DuckDuckGo for a query and return first link.
    
    Args:
        query: Search query string
        
    Returns:
        str: First valid URL from search results or None
    """
    try:
        url = f"https://duckduckgo.com/html/?q={query}"
        response = requests.get(url, headers=HEADERS, timeout=SEARCH_TIMEOUT)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Find result links
        results = soup.find_all("a", class_="result__a")
        candidates = []

        if results:
            for result in results:
                link = result.get("href")
                link = _decode_ddg_url(link)
                title = result.get_text(" ", strip=True)
                score = _score_link(link, title, query)
                if link and link.startswith("http"):
                    candidates.append((score, link))

        if candidates:
            candidates.sort(reverse=True, key=lambda item: item[0])
            best_score, best_link = candidates[0]
            if best_score > 0:
                return best_link
            return candidates[0][1]
        return None
        
    except requests.exceptions.Timeout:
        logger.error("DuckDuckGo search timed out")
        return None
    except Exception as e:
        logger.error(f"Error searching DuckDuckGo: {str(e)}")
        return None


def search_wikipedia(query):
    """
    Fallback: Search Wikipedia for a query.
    
    Args:
        query: Search query string
        
    Returns:
        str: Wikipedia article URL or None
    """
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json"
        response = requests.get(url, headers=HEADERS, timeout=SEARCH_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        results = data.get("query", {}).get("search", [])
        
        if results:
            page_title = results[0]["title"].replace(" ", "_")
            return f"https://en.wikipedia.org/wiki/{page_title}"
        
        logger.warning(f"No Wikipedia results found for: {query}")
        return None
        
    except Exception as e:
        logger.error(f"Error searching Wikipedia: {str(e)}")
        return None


def get_first_link(query):
    """
    Get first link from search (try DuckDuckGo first, fallback to Wikipedia).
    
    Args:
        query: Search query string
        
    Returns:
        str: Valid URL or None
    """
    # Try DuckDuckGo first
    link = search_duckduckgo(query)
    if link:
        return link
    
    logger.info("DuckDuckGo failed, trying Wikipedia fallback...")
    # Fallback to Wikipedia
    link = search_wikipedia(query)
    if link:
        return link
    
    logger.error(f"Could not find any links for query: {query}")
    return None


def clean_text(text):
    """
    Clean and normalize text content.
    
    Args:
        text: Raw text to clean
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
    
    # Remove extra whitespace and newlines
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = " ".join(lines)
    
    # Remove extra spaces
    text = " ".join(text.split())
    
    # Remove common navigation/boilerplate text (case-insensitive)
    text_lower = text.lower()
    for phrase in UNWANTED_PHRASES:
        # Use case-insensitive replace
        idx = text_lower.find(phrase.lower())
        if idx != -1:
            # Only remove if it's a complete phrase (surrounded by spaces or punctuation)
            start = idx
            end = idx + len(phrase)
            if start == 0 or text[start-1] in ' .,;:\n':
                if end >= len(text) or text[end] in ' .,;:\n':
                    text = text[:start] + " " + text[end:]
                    text_lower = text.lower()
    
    # Limit to reasonable length
    if len(text) > MAX_CONTENT_LENGTH:
        text = text[:MAX_CONTENT_LENGTH]
    
    return text.strip()


def remove_unwanted_tags(soup):
    """
    Remove script, style, nav, footer, and other non-content tags.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        BeautifulSoup: Cleaned soup object
    """
    for tag in soup(UNWANTED_TAGS):
        tag.decompose()
    
    # Remove elements with common ad/tracking classes
    for indicator in AD_INDICATORS:
        for element in soup.find_all(class_=lambda x: x and indicator in x.lower()):
            element.decompose()
    
    return soup


def fetch_page_content(url):
    """
    Fetch and clean content from a web page with multiple extraction strategies.
    
    Args:
        url: The URL to fetch
        
    Returns:
        str: Cleaned text content or None
    """
    try:
        if not url or not url.startswith("http"):
            logger.error(f"Invalid URL: {url}")
            return None
        
        response = requests.get(url, headers=HEADERS, timeout=CONTENT_FETCH_TIMEOUT, allow_redirects=True)
        response.raise_for_status()
        
        # Set encoding to UTF-8
        response.encoding = "utf-8"
        
        # Try with html.parser first
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Log what we have
        logger.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")
        logger.debug(f"HTML paragraphs found: {len(soup.find_all('p'))}")
        logger.debug(f"HTML divs found: {len(soup.find_all('div'))}")
        
        # Strategy 1: Extract from article, main, or content containers BEFORE removing tags
        text = None
        content_selectors = [
            "article",
            ("div", {"class": lambda x: x and ("content" in x.lower() or "article" in x.lower() or "post" in x.lower() or "story" in x.lower())}),
            ("div", {"class": lambda x: x and "main" in x.lower()}),
            "main",
            ("div", {"id": lambda x: x and ("content" in x.lower() or "main" in x.lower())}),
            "section"
        ]
        query_tokens = _clean_query_tokens(urlparse(url).path.replace("-", " "))

        def _score_element(element):
            element_text = element.get_text(separator=" ", strip=True)
            if not element_text or len(element_text) < MIN_CONTENT_LENGTH:
                return 0
            score = len(element_text)
            score += len(element.find_all("p")) * 40
            score += len(element.find_all("h1")) * 80
            score += len(element.find_all("h2")) * 40
            element_lower = element_text.lower()
            for token in query_tokens:
                if token in element_lower:
                    score += 100
            return score

        best_element = None
        best_score = 0
        
        for selector in content_selectors:
            try:
                if isinstance(selector, str):
                    element = soup.find(selector)
                else:
                    element = soup.find(selector[0], selector[1])

                if element:
                    element_score = _score_element(element)
                    logger.debug(f"Selector {selector} score: {element_score}")
                    if element_score > best_score:
                        best_score = element_score
                        best_element = element
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {str(e)}")
                continue
        
        if best_element:
            text = best_element.get_text(separator=" ", strip=True)
            logger.info(f"Best structured element score {best_score}: {len(text)} chars")
        
        # Strategy 2: If no structured content found, extract paragraphs with query relevance
        if not text:
            paragraphs = soup.find_all("p")
            if paragraphs:
                paragraph_texts = [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
                combined = " ".join(paragraph_texts)
                if len(combined) > MIN_CONTENT_LENGTH:
                    text = combined
                    logger.info(f"Found {len(paragraph_texts)} paragraphs: {len(text)} chars")
        
        # Strategy 3: If still nothing, find best div by paragraph density and relevance
        if not text:
            divs = [div for div in soup.find_all("div") if len(div.get_text(strip=True)) > MIN_CONTENT_LENGTH]
            if divs:
                scored_divs = []
                for div in divs:
                    score = _score_element(div)
                    if score > 0:
                        scored_divs.append((score, div))
                if scored_divs:
                    scored_divs.sort(reverse=True, key=lambda item: item[0])
                    best_div = scored_divs[0][1]
                    text = best_div.get_text(separator=" ", strip=True)
                    logger.info(f"Found best div score {scored_divs[0][0]}: {len(text)} chars")
        
        # Strategy 4: Fallback to entire body
        if not text:
            body = soup.find("body")
            if body:
                text = body.get_text(separator=" ", strip=True)
                logger.info(f"Using body content: {len(text)} chars")
            else:
                text = soup.get_text(separator=" ", strip=True)
                logger.info(f"Using full page content: {len(text)} chars")
        
        # Validate content
        if not text:
            logger.warning(f"No text extracted from {url}")
            return None
        
        if len(text) < MIN_CONTENT_LENGTH:
            logger.warning(f"Content too short from {url}: {len(text)} chars (min: {MIN_CONTENT_LENGTH})")
            return None
        
        # Clean the text
        cleaned = clean_text(text)
        
        if not cleaned:
            logger.error(f"No valid content after cleaning from {url}")
            return None
        
        logger.info(f"Successfully fetched {len(cleaned)} chars from {url}")
        return cleaned
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {url}")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error fetching {url}")
        return None
    except Exception as e:
        logger.error(f"Error fetching content from {url}: {str(e)}")
        return None