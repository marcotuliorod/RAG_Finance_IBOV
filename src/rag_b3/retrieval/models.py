from datetime import datetime

from pydantic import BaseModel


class CvmFeedResult(BaseModel):
    feed_key: str
    title: str
    summary: str | None
    link: str | None
    published_at: datetime | None
