"""
web_search.py — Real web search for Maez

Uses DuckDuckGo (no API key required) to search the web
and return summarized results. Injected into reasoning
context when Maez needs current information.
"""

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

logger = logging.getLogger("maez")

_cache = {}
_cache_ttl = 300  # 5 minutes


def search(query: str, max_results: int = 5) -> dict:
    """Search the web using DuckDuckGo. Returns dict with results."""
    cache_key = query.lower().strip()
    if cache_key in _cache:
        age = time.time() - _cache[cache_key]['timestamp']
        if age < _cache_ttl:
            logger.debug("Web search cache hit: %s", query)
            return _cache[cache_key]['result']

    logger.info("Web search: %s", query)

    try:
        # DuckDuckGo instant answer API
        params = urllib.parse.urlencode({
            'q': query, 'format': 'json',
            'no_html': '1', 'skip_disambig': '1',
        })
        url = f"https://api.duckduckgo.com/?{params}"
        req = urllib.request.Request(
            url, headers={'User-Agent': 'Maez/1.0 (Personal AI Agent)'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        results = []

        # Abstract (direct answer)
        if data.get('Abstract'):
            results.append({
                'title': data.get('Heading', 'Direct Answer'),
                'snippet': data['Abstract'],
                'url': data.get('AbstractURL', ''),
                'source': data.get('AbstractSource', ''),
            })

        # Related topics
        for topic in data.get('RelatedTopics', [])[:max_results]:
            if isinstance(topic, dict) and topic.get('Text'):
                results.append({
                    'title': topic.get('Text', '')[:100],
                    'snippet': topic.get('Text', ''),
                    'url': topic.get('FirstURL', ''),
                    'source': 'DuckDuckGo',
                })

        # Fallback to HTML search if no instant answer
        if not results:
            results = _html_search(query, max_results)

        result = {
            'query': query,
            'results': results[:max_results],
            'result_count': len(results),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'success': len(results) > 0,
        }

        _cache[cache_key] = {'result': result, 'timestamp': time.time()}
        logger.info("Web search: %d results for '%s'", len(results), query)
        return result

    except Exception as e:
        logger.error("Web search failed: %s", e)
        return {
            'query': query, 'results': [], 'result_count': 0,
            'error': str(e), 'success': False,
        }


def _html_search(query: str, max_results: int = 5) -> list:
    """Fallback: scrape DuckDuckGo HTML search."""
    try:
        params = urllib.parse.urlencode({'q': query, 'kl': 'us-en'})
        url = f"https://html.duckduckgo.com/html/?{params}"
        req = urllib.request.Request(url, headers={
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64) '
                'AppleWebKit/537.36 Chrome/120.0.0.0'
            )
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        def strip_tags(text):
            return re.sub(r'<[^>]+>', '', text).strip()

        results = []
        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL
        )
        titles = re.findall(
            r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL
        )
        urls = re.findall(
            r'class="result__url"[^>]*>(.*?)</span>', html, re.DOTALL
        )

        for i in range(min(max_results, len(snippets))):
            results.append({
                'title': strip_tags(titles[i]) if i < len(titles) else '',
                'snippet': strip_tags(snippets[i]),
                'url': strip_tags(urls[i]).strip() if i < len(urls) else '',
                'source': 'DuckDuckGo',
            })
        return results
    except Exception as e:
        logger.error("HTML search fallback failed: %s", e)
        return []


def format_for_context(result: dict) -> str:
    """Format search results for prompt injection."""
    if not result.get('success') or not result.get('results'):
        return f"[WEB SEARCH: '{result.get('query', '')}'] No results found."

    lines = [
        f"[WEB SEARCH: '{result['query']}'] "
        f"{result['result_count']} results — {result['timestamp']}"
    ]
    for i, r in enumerate(result['results'][:3], 1):
        lines.append(f"  {i}. {r['title']}")
        lines.append(f"     {r['snippet'][:200]}")
        if r.get('url'):
            lines.append(f"     Source: {r['url']}")
    return '\n'.join(lines)


NEWS_RSS_FEEDS = {
    'general': [
        'https://feeds.reuters.com/reuters/topNews',
        'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
        'https://feeds.bbci.co.uk/news/rss.xml',
    ],
    'tech': [
        'https://techcrunch.com/feed/',
        'https://www.theverge.com/rss/index.xml',
        'https://feeds.arstechnica.com/arstechnica/index',
    ],
    'ai': [
        'https://techcrunch.com/tag/artificial-intelligence/feed/',
        'https://venturebeat.com/ai/feed/',
        'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml',
    ],
}


def search_rss(topic: str = 'general', max_results: int = 5) -> dict:
    """Fetch real headlines from RSS feeds. Returns actual stories."""
    import xml.etree.ElementTree as ET

    # Detect topic from query text
    topic_lower = topic.lower()
    if any(w in topic_lower for w in ['ai', 'artificial', 'machine learning', 'llm', 'model', 'openai', 'claude']):
        feeds = NEWS_RSS_FEEDS['ai']
    elif any(w in topic_lower for w in ['tech', 'technology', 'software', 'startup', 'apple', 'google', 'microsoft']):
        feeds = NEWS_RSS_FEEDS['tech']
    else:
        feeds = NEWS_RSS_FEEDS.get(topic, NEWS_RSS_FEEDS['general'])

    # Check cache
    cache_key = f"rss:{topic_lower}"
    if cache_key in _cache:
        age = time.time() - _cache[cache_key]['timestamp']
        if age < _cache_ttl:
            return _cache[cache_key]['result']

    logger.info("RSS search: topic=%s", topic)
    all_items = []

    for feed_url in feeds:
        try:
            req = urllib.request.Request(
                feed_url, headers={'User-Agent': 'Maez/1.0 RSS Reader'}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = resp.read()

            root = ET.fromstring(content)
            source_name = feed_url.split('/')[2].replace('www.', '').replace('feeds.', '')

            # RSS 2.0 format
            items = root.findall('.//item')
            for item in items[:max_results]:
                title = (item.findtext('title') or '').strip()
                desc = (item.findtext('description') or '').strip()
                link = (item.findtext('link') or '').strip()
                pubdate = (item.findtext('pubDate') or '').strip()

                desc = re.sub(r'<[^>]+>', '', desc)[:300].strip()

                if title:
                    all_items.append({
                        'title': title,
                        'snippet': desc if desc else title,
                        'url': link,
                        'published': pubdate,
                        'source': source_name,
                    })

            # Atom format fallback
            if not items:
                ns = {'atom': 'http://www.w3.org/2005/Atom'}
                entries = root.findall('.//atom:entry', ns)
                for entry in entries[:max_results]:
                    title = (entry.findtext('atom:title', '', ns) or '').strip()
                    summary = (entry.findtext('atom:summary', '', ns) or
                               entry.findtext('atom:content', '', ns) or '').strip()
                    link_el = entry.find('atom:link', ns)
                    link = link_el.get('href', '') if link_el is not None else ''
                    published = (entry.findtext('atom:published', '', ns) or
                                 entry.findtext('atom:updated', '', ns) or '').strip()

                    summary = re.sub(r'<[^>]+>', '', summary)[:300].strip()

                    if title:
                        all_items.append({
                            'title': title,
                            'snippet': summary if summary else title,
                            'url': link,
                            'published': published,
                            'source': source_name,
                        })

            if len(all_items) >= max_results:
                break

        except Exception as e:
            logger.debug("RSS feed %s failed: %s", feed_url, e)
            continue

    result = {
        'query': topic,
        'results': all_items[:max_results],
        'result_count': len(all_items[:max_results]),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'success': len(all_items) > 0,
        'source_type': 'rss',
    }

    _cache[cache_key] = {'result': result, 'timestamp': time.time()}
    logger.info("RSS search: %d headlines for '%s'", len(all_items[:max_results]), topic)
    return result


def is_news_query(text: str) -> bool:
    """Detect if a message is asking for news specifically."""
    news_words = ['news', 'headlines', 'happening', 'developments',
                  'this week', 'breaking', 'latest news']
    return any(w in text.lower() for w in news_words)


def needs_web_search(text: str) -> bool:
    """Detect if a message needs live web data."""
    triggers = [
        'news', 'latest', 'current', 'today', 'now',
        'recent', 'what happened', 'who won', 'weather',
        'price', 'stock', 'search', 'look up', 'find out',
        'what is happening', 'tell me about', 'headlines',
        'update on', 'trending', 'breaking', 'score',
        'search the web', 'search for', 'google',
    ]
    text_lower = text.lower()
    return any(t in text_lower for t in triggers)


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO)
    query = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else "AI news today"
    result = search(query)
    print(format_for_context(result))
