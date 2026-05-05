from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class ImageRef(BaseModel):
    """Reference to an image extracted during crawling."""
    src: str
    alt: str
    local_path: str


class PageData(BaseModel):
    """Data extracted from a single crawled page."""
    url: str
    tab_name: str
    raw_text: str
    images: list[ImageRef]
    crawled_at: datetime
