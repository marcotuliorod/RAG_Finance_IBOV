import calendar
import html
import re
from datetime import datetime, timezone

import feedparser
import httpx

from rag_b3.ingestion.cvm_rss.models import CvmFeedItem

_HTML_TAG_RE = re.compile(r"<[^>]+>")

USER_AGENT = "rag-b3-cvm-poller/0.1 (+ingestao regulatoria interna, nao comercial)"


def _strip_html(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = html.unescape(_HTML_TAG_RE.sub(" ", text))
    cleaned = " ".join(cleaned.split())
    return cleaned or None


def fetch_feed_content(url: str, timeout: float = 10.0) -> str:
    response = httpx.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return response.text


def parse_entries(feed_key: str, content: str) -> tuple[list[CvmFeedItem], bool]:
    """Retorna (items, bozo). bozo=True indica XML malformado — feedparser é
    tolerante e ainda tenta extrair o que for possível; os itens recuperados
    são processados normalmente (RF-03 não se perde por causa de um feed com
    XML mal formado pontualmente)."""
    parsed = feedparser.parse(content)
    items: list[CvmFeedItem] = []
    for entry in parsed.entries:
        guid = entry.get("id") or entry.get("guid") or entry.get("link")
        if not guid:
            continue  # sem guid nem link não há como deduplicar — descarta
        published_at = None
        if getattr(entry, "published_parsed", None):
            published_at = datetime.fromtimestamp(
                calendar.timegm(entry.published_parsed), tz=timezone.utc
            )
        title_raw = entry.get("title", "")
        items.append(
            CvmFeedItem(
                feed_key=feed_key,
                guid=guid,
                link=entry.get("link"),
                title=_strip_html(title_raw) or title_raw,
                summary=_strip_html(entry.get("summary")),
                published_at=published_at,
                raw_entry=dict(entry),
            )
        )
    return items, bool(parsed.bozo)
