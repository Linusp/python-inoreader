# coding: utf-8
from __future__ import print_function, unicode_literals

from .utils import extract_text, normalize_whitespace


class Article(object):
    def __init__(
        self,
        id,
        title,
        categories,
        link,
        published=None,
        content=None,
        author=None,
        feed_id=None,
        feed_title=None,
        feed_link=None,
    ):
        self.id = id
        self.title = normalize_whitespace(title)
        self.categories = categories
        self.link = link
        self.published = published
        self.content = content.strip() if content else ""
        self.text = extract_text(self.content)
        self.author = author
        self.feed_id = feed_id
        self.feed_title = feed_title.strip()
        self.feed_link = feed_link

    @classmethod
    def from_json(cls, data):
        article_data = {
            "id": data["id"],
            "title": data["title"],
            "categories": data["categories"],
            "published": data["published"],
            "content": data.get("summary", {}).get("content"),
            "author": data.get("author"),
        }
        links = [item["href"] for item in data["canonical"]]
        article_data["link"] = links[0] if links else ""

        # feed info
        article_data.update(
            {
                "feed_id": data["origin"]["streamId"],
                "feed_title": normalize_whitespace(data["origin"]["title"]),
                "feed_link": data["origin"]["htmlUrl"],
            }
        )

        return cls(**article_data)
