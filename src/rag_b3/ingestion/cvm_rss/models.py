from datetime import datetime

from pydantic import BaseModel


class CvmFeedItem(BaseModel):
    feed_key: str
    guid: str
    link: str | None = None
    title: str
    summary: str | None = None
    published_at: datetime | None = None
    raw_entry: dict
