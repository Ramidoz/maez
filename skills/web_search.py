# Copyright © 2026 Rohit Ananthan
# Licensed under the GNU Affero General Public License v3.0 or later.
# See LICENSE for full text.
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
import urllib.parse

from core.egress import external_fetch
from core.policies.exceptions import SubjectBoundaryRefused
from core.policies.third_party_subject_gate import (
    SubjectKind,
    enforce_subject_boundary,
)
from core.search.sense_flag import sense_enabled

logger = logging.getLogger("maez")

_cache = {}
_cache_ttl = 300  # 5 minutes
_SENSE_BACKEND = None


def _sense_backend():
    """Lazy singleton so the flag-off path never imports/builds SearXNG."""
    global _SENSE_BACKEND
    if _SENSE_BACKEND is None:
        from core.search.searxng_client import SearxngBackend

        _SENSE_BACKEND = SearxngBackend()
    return _SENSE_BACKEND


class _SubjectQuery:
    """Adapter to the SubjectBoundaryQuery protocol for body-level checks."""

    def __init__(self, subject_kind, subject_ref=None):
        self.bond_id = "owner"
        self.subject_kind = subject_kind
        self.subject_ref = subject_ref


def search(
    query: str,
    max_results: int = 5,
    *,
    subject_kind=SubjectKind.PUBLIC_TOPIC,
) -> dict:
    """Search the web.

    SearXNG sense under ``MAEZ_SEARCH_AS_SENSE_ENABLED``; the legacy
    DuckDuckGo path is byte-identical when the flag is off. The subject
    boundary lives here, at the body, so every caller inherits it.
    """
    if not sense_enabled():
        return _ddg_search(query, max_results)

    try:
        enforce_subject_boundary(
            _SubjectQuery(subject_kind, subject_ref=(query or "")[:80])
        )
    except SubjectBoundaryRefused:
        logger.info("web search refused pre-egress: subject_boundary")
        return {
            "query": query,
            "success": False,
            "results": [],
            "source": "searxng",
            "refused": "subject_boundary",
        }

    cache_key = query.lower().strip()
    if cache_key in _cache:
        age = time.time() - _cache[cache_key]["timestamp"]
        if age < _cache_ttl:
            logger.debug("Web search cache hit: %s", query)
            return _cache[cache_key]["result"]

    logger.info("Web search (searxng sense): %s", query[:100])
    try:
        rows = _sense_backend().search(query, max_results=max_results)
    except Exception as e:
        logger.warning("searxng sense failed: %s", e)
        return {"query": query, "success": False, "results": [], "source": "searxng"}

    results = [
        {
            "title": r.get("title") or "",
            "url": r.get("url") or "",
            "snippet": r.get("content") or "",
        }
        for r in rows
    ]
    result = {
        "query": query,
        "success": bool(results),
        "results": results,
        "result_count": len(results),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "searxng",
    }
    if result["success"]:
        _cache[cache_key] = {"result": result, "timestamp": time.time()}
    return result


def _ddg_search(query: str, max_results: int = 5) -> dict:
    """Search the web using DuckDuckGo. Returns dict with results.

    Session 11x: made exception-handling resilient. Previously, if the
    DuckDuckGo Instant Answer API returned non-JSON (which it does for
    many technical/specific queries), the whole search gave up without
    trying the HTML fallback. Now the IA path is wrapped in its own
    try/except so a JSON parse failure there still drops through to
    _html_search() as intended.
    """
    cache_key = query.lower().strip()
    if cache_key in _cache:
        age = time.time() - _cache[cache_key]['timestamp']
        if age < _cache_ttl:
            logger.debug("Web search cache hit: %s", query)
            return _cache[cache_key]['result']

    logger.info("Web search: %s", query)
    results = []

    # --- Attempt 1: DuckDuckGo Instant Answer API ---
    # Best for well-known topics (Wikipedia-style summaries). Returns
    # empty or raises for most specific technical queries.
    try:
        params = urllib.parse.urlencode({
            'q': query, 'format': 'json',
            'no_html': '1', 'skip_disambig': '1',
        })
        url = f"https://api.duckduckgo.com/?{params}"
        fetched = external_fetch.fetch_text(
            fetch_type="web_search",
            url=url,
            caller="skills.web_search.search.instant_answer",
            timeout_s=10,
        )
        if not fetched.ok:
            raise RuntimeError(",".join(fetched.reason_codes))
        data = json.loads(fetched.text)

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
    except Exception as e:
        logger.debug("Instant Answer API failed for %r: %s — trying HTML fallback", query, e)
        # Fall through to HTML search

    # --- Attempt 2: HTML search (always try if Attempt 1 gave nothing) ---
    if not results:
        try:
            results = _html_search(query, max_results)
        except Exception as e:
            logger.error("HTML fallback also failed for %r: %s", query, e)
            results = []

    result = {
        'query': query,
        'results': results[:max_results] if results else [],
        'result_count': len(results[:max_results]) if results else 0,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'success': bool(results),
    }
    if not results:
        result['error'] = 'no results from either Instant Answer API or HTML search'

    _cache[cache_key] = {'result': result, 'timestamp': time.time()}
    logger.info("Web search: %d results for '%s'", len(results), query)
    return result


def _html_search(query: str, max_results: int = 5) -> list:
    """Fallback: scrape DuckDuckGo HTML search."""
    try:
        params = urllib.parse.urlencode({'q': query, 'kl': 'us-en'})
        url = f"https://html.duckduckgo.com/html/?{params}"
        fetched = external_fetch.fetch_text(
            fetch_type="web_search",
            url=url,
            caller="skills.web_search.html_search",
            timeout_s=10,
        )
        if not fetched.ok:
            raise RuntimeError(",".join(fetched.reason_codes))
        html = fetched.text

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
            fetched = external_fetch.fetch_text(
                fetch_type="search_rss",
                url=feed_url,
                caller="skills.web_search.search_rss",
                timeout_s=8,
            )
            if not fetched.ok:
                raise RuntimeError(",".join(fetched.reason_codes))

            root = ET.fromstring(fetched.text)
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


# Words that are 'news framing' / filler, not a subject. If a query is ONLY these,
# it is a generic 'give me the news' request and the category-feed RSS reader is fine.
# If anything else remains (a named subject like 'Elon'), it must go to a real keyword
# search — search_rss never searches for the subject, it just returns the top headlines
# of a category, so 'news about Elon' silently comes back as generic noise.
_NEWS_FILLER = frozenset({
    'news', 'headlines', 'headline', 'happening', 'happenings', 'developments',
    'development', 'breaking', 'latest', 'current', 'recent', 'today', 'todays',
    'tonight', 'now', 'this', 'week', 'weeks', 'day', 'days', 'the', 'a', 'an',
    'any', 'some', 'me', 'my', 'get', 'give', 'show', 'tell', 'find', 'search',
    'look', 'up', 'for', 'about', 'on', 'of', 'in', 'to', 'what', 'whats', 'is',
    'are', 's', 'please', 'maez', 'i', 'want', 'need', 'web', 'google', 'update',
    'updates', 'trending', 'story', 'stories', 'world', 'top',
})


def is_generic_news_query(text: str) -> bool:
    """True when a query is a bare 'give me the news/headlines' request with no
    specific subject. Topic-specific news ('news about Elon', 'Tesla news') returns
    False so the caller uses a real keyword search instead of the category-feed RSS
    reader (which ignores the subject and returns generic top headlines)."""
    tokens = [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
              if w not in _NEWS_FILLER]
    return len(tokens) == 0


def needs_web_search(text: str) -> bool:
    """Detect if a message needs live web data."""
    triggers = [
        'news', 'latest', 'current', 'today', 'now',
        'recent', 'what happened', 'who won', 'weather',
        'price', 'stock', 'search', 'look up', 'find out',
        'what is happening', 'tell me about', 'headlines',
        'update on', 'trending', 'breaking', 'score',
        'search the web', 'search for', 'google',
        'exchange rate', 'currency', 'convert', 'usd', 'inr',
        'eur', 'gbp', 'cad', 'aud', 'jpy', 'cny',
        'rupee', 'rupees', 'euro', 'euros', 'dollar', 'dollars',
        'pound', 'pounds', 'yen', '₹', '€', '£', '¥',
    ]
    text_lower = text.lower()
    return any(t in text_lower for t in triggers)


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO)
    query = ' '.join(sys.argv[1:]) if len(sys.argv) > 1 else "AI news today"
    result = search(query)
    print(format_for_context(result))
