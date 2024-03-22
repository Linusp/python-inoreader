# coding: utf-8
from __future__ import print_function, unicode_literals

import logging
from datetime import datetime
from operator import itemgetter
from uuid import uuid4

try:  # python2
    from urllib import quote_plus

    from urlparse import urljoin
except ImportError:  # python3
    from urllib.parse import urljoin, quote_plus

import requests

from .article import Article
from .consts import BASE_URL
from .exception import APIError, NotLoginError
from .subscription import Subscription

LOGGER = logging.getLogger(__name__)


class InoreaderClient(object):
    # paths
    TOKEN_PATH = "/oauth2/token"
    USER_INFO_PATH = "user-info"
    TAG_LIST_PATH = "tag/list"
    SUBSCRIPTION_LIST_PATH = "subscription/list"
    STREAM_CONTENTS_PATH = "stream/contents/"
    EDIT_TAG_PATH = "edit-tag"
    EDIT_SUBSCRIPTION_PATH = "subscription/edit"

    # tags
    GENERAL_TAG_TEMPLATE = "user/-/label/{}"
    READ_TAG = "user/-/state/com.google/read"
    STARRED_TAG = "user/-/state/com.google/starred"
    LIKED_TAG = "user/-/state/com.google/like"
    BROADCAST_TAG = "user/-/state/com.google/broadcast"

    def __init__(
        self, app_id, app_key, access_token, refresh_token, expires_at, config_manager=None
    ):
        self.app_id = app_id
        self.app_key = app_key
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = float(expires_at)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "AppId": self.app_id,
                "AppKey": self.app_key,
                "Authorization": "Bearer {}".format(self.access_token),
            }
        )
        self.config_manager = config_manager
        self.proxies = self.config_manager.proxies if config_manager else None

    def check_token(self):
        now = datetime.now().timestamp()
        if now >= self.expires_at:
            self.refresh_access_token()

    @staticmethod
    def parse_response(response, json_data=True):
        if response.status_code == 401:
            raise NotLoginError
        elif response.status_code != 200:
            raise APIError(response.text)

        return response.json() if json_data else response.text

    def refresh_access_token(self):
        url = urljoin(BASE_URL, self.TOKEN_PATH)
        payload = {
            "client_id": self.app_id,
            "client_secret": self.app_key,
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }
        response = self.parse_response(requests.post(url, json=payload, proxies=self.proxies))
        self.access_token = response["access_token"]
        self.refresh_token = response["refresh_token"]
        self.expires_at = datetime.now().timestamp() + response["expires_in"]
        self.session.headers["Authorization"] = "Bearer {}".format(self.access_token)

        if self.config_manager:
            self.config_manager.access_token = self.access_token
            self.config_manager.refresh_token = self.refresh_token
            self.config_manager.expires_at = self.expires_at
            self.config_manager.save()

    def userinfo(self):
        self.check_token()

        url = urljoin(BASE_URL, self.USER_INFO_PATH)
        return self.parse_response(self.session.post(url, proxies=self.proxies))

    def get_folders(self):
        self.check_token()

        url = urljoin(BASE_URL, self.TAG_LIST_PATH)
        params = {"types": 1, "counts": 1}
        response = self.parse_response(self.session.post(url, params=params, proxies=self.proxies))

        folders = []
        for item in response["tags"]:
            if item.get("type") != "folder":
                continue

            folder_name = item["id"].split("/")[-1]
            folders.append({"name": folder_name, "unread_count": item["unread_count"]})

        folders.sort(key=itemgetter("name"))
        return folders

    def get_tags(self):
        self.check_token()

        url = urljoin(BASE_URL, self.TAG_LIST_PATH)
        params = {"types": 1, "counts": 1}
        response = self.parse_response(self.session.post(url, params=params, proxies=self.proxies))

        tags = []
        for item in response["tags"]:
            if item.get("type") != "tag":
                continue

            folder_name = item["id"].split("/")[-1]
            tags.append({"name": folder_name, "unread_count": item["unread_count"]})

        tags.sort(key=itemgetter("name"))
        return tags

    def get_subscription_list(self):
        self.check_token()

        url = urljoin(BASE_URL, self.SUBSCRIPTION_LIST_PATH)
        response = self.parse_response(self.session.get(url, proxies=self.proxies))
        for item in response["subscriptions"]:
            yield Subscription.from_json(item)

    def get_stream_contents(self, stream_id, c="", limit=None):
        fetched_count = 0
        stop = False
        while not stop:
            articles, c = self.__get_stream_contents(stream_id, c)
            for a in articles:
                try:
                    yield Article.from_json(a)
                    fetched_count += 1
                except Exception as e:
                    print(e)
                    continue
                if limit and fetched_count >= limit:
                    stop = True
                    break
            if c is None:
                break

    def __get_stream_contents(self, stream_id, continuation=""):
        self.check_token()

        url = urljoin(BASE_URL, self.STREAM_CONTENTS_PATH + quote_plus(stream_id))
        params = {"n": 50, "r": "", "c": continuation, "output": "json"}  # default 20, max 1000
        response = self.parse_response(self.session.post(url, params=params, proxies=self.proxies))
        if "continuation" in response:
            return response["items"], response["continuation"]
        else:
            return response["items"], None

    def fetch_articles(self, folder=None, tags=None, unread=True, starred=False, limit=None):
        self.check_token()

        url = urljoin(BASE_URL, self.STREAM_CONTENTS_PATH)
        if folder:
            url = urljoin(url, quote_plus(self.GENERAL_TAG_TEMPLATE.format(folder)))

        params = {"c": str(uuid4())}
        if unread:
            params["xt"] = self.READ_TAG

        if starred:
            params["it"] = self.STARRED_TAG

        fetched_count = 0
        response = self.parse_response(self.session.post(url, params=params, proxies=self.proxies))
        for data in response["items"]:
            categories = {
                category.split("/")[-1]
                for category in data.get("categories", [])
                if category.find("label") > 0
            }
            if tags and not categories.issuperset(set(tags)):
                continue

            yield Article.from_json(data)
            fetched_count += 1
            if limit and fetched_count >= limit:
                break

        continuation = response.get("continuation")
        while continuation and (not limit or fetched_count < limit):
            params["c"] = continuation
            response = self.parse_response(
                self.session.post(url, params=params, proxies=self.proxies)
            )
            for data in response["items"]:
                categories = {
                    category.split("/")[-1]
                    for category in data.get("categories", [])
                    if category.find("label") > 0
                }
                if tags and not categories.issuperset(set(tags)):
                    continue
                yield Article.from_json(data)
                fetched_count += 1
                if limit and fetched_count >= limit:
                    break

            continuation = response.get("continuation")

    def fetch_unread(self, folder=None, tags=None, limit=None):
        for article in self.fetch_articles(folder=folder, tags=tags, unread=True):
            yield article

    def fetch_starred(self, folder=None, tags=None, limit=None):
        for article in self.fetch_articles(folder=folder, tags=tags, unread=False, starred=True):
            yield article

    def add_general_label(self, articles, label):
        self.check_token()

        url = urljoin(BASE_URL, self.EDIT_TAG_PATH)
        for start in range(0, len(articles), 10):
            end = min(start + 10, len(articles))
            params = {"a": label, "i": [articles[idx].id for idx in range(start, end)]}
            self.parse_response(
                self.session.post(url, params=params, proxies=self.proxies), json_data=False
            )

    def remove_general_label(self, articles, label):
        self.check_token()

        url = urljoin(BASE_URL, self.EDIT_TAG_PATH)
        for start in range(0, len(articles), 10):
            end = min(start + 10, len(articles))
            params = {"r": label, "i": [articles[idx].id for idx in range(start, end)]}
            self.parse_response(
                self.session.post(url, params=params, proxies=self.proxies), json_data=False
            )

    def add_tag(self, articles, tag):
        self.add_general_label(articles, self.GENERAL_TAG_TEMPLATE.format(tag))

    def mark_as_read(self, articles):
        self.add_general_label(articles, self.READ_TAG)

    def mark_as_starred(self, articles):
        self.add_general_label(articles, self.STARRED_TAG)

    def mark_as_liked(self, articles):
        self.add_general_label(articles, self.LIKED_TAG)

    def remove_tag(self, articles, tag):
        self.remove_general_label(articles, self.GENERAL_TAG_TEMPLATE.format(tag))

    def remove_read(self, articles):
        self.remove_general_label(articles, self.READ_TAG)

    def remove_starred(self, articles):
        self.remove_general_label(articles, self.STARRED_TAG)

    def remove_liked(self, articles):
        self.remove_general_label(articles, self.LIKED_TAG)

    def broadcast(self, articles):
        self.add_general_label(articles, self.BROADCAST_TAG)

    def edit_subscription(self, stream_id, action, title=None, add_folder=None, remove_folder=None):
        self.check_token()
        url = urljoin(BASE_URL, self.EDIT_SUBSCRIPTION_PATH)
        # https://us.inoreader.com/developers/edit-subscription
        # The documentation looks a bit outdated, `follow`/`unfollow` don't work
        action = {"follow": "subscribe", "unfollow": "unsubscribe"}.get(action) or action
        params = {"ac": action, "s": stream_id}
        if title:
            params["t"] = title

        if add_folder:
            params["a"] = add_folder

        if remove_folder:
            params["r"] = remove_folder

        r = self.session.post(url, params=params, proxies=self.proxies)
        response = self.parse_response(
            r,
            # self.session.post(url, params=params, proxies=self.proxies),
            json_data=False,
        )
        return response
