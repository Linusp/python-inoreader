#!/usr/bin/env python
# -*- coding: utf-8 -*-


class Subscription(object):
    def __init__(self, id, title, categories, sortid, firstitemmsec, url, htmlUrl, iconUrl):
        self.id = id
        self.title = title
        self.categories = categories
        self.sortid = sortid
        self.firstitemmsec = firstitemmsec
        self.url = url
        self.htmlUrl = htmlUrl
        self.iconUrl = iconUrl

    @classmethod
    def from_json(cls, data):
        subscription_info = {
            "id": data["id"],
            "title": data["title"],
            "categories": list(data["categories"]),
            "sortid": data["sortid"],
            "firstitemmsec": data["firstitemmsec"],
            "url": data["url"],
            "htmlUrl": data["htmlUrl"],
            "iconUrl": data["iconUrl"],
        }
        return cls(**subscription_info)
