# coding: utf-8
from __future__ import print_function, unicode_literals

import logging
from uuid import uuid4
from datetime import datetime
from operator import itemgetter
try:                            # python2
    from urlparse import urljoin
    from urllib import quote_plus
except ImportError:             # python3
    from urllib.parse import urljoin, quote_plus

import requests

from .consts import BASE_URL
from .exception import NotLoginError, APIError
from .article import Article
from .subscription import Subscription


LOGGER = logging.getLogger(__name__)


class InoreaderClient(object):

    # paths
    TOKEN_PATH = '/oauth2/token'

    def __init__(self, app_id, app_key, access_token, refresh_token,
                 expires_at, userid=None, config_manager=None):
        self.app_id = app_id
        self.app_key = app_key
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = float(expires_at)
        self.session = requests.Session()
        self.session.headers.update({
            'AppId': self.app_id,
            'AppKey': self.app_key,
            'Authorization': 'Bearer {}'.format(self.access_token)
        })
        self.userid = userid or self.userinfo()['userId']
        self.config_manager = config_manager
        if self.userid and self.config_manager and not self.config_manager.user_id:
            self.config_manager.user_id = self.userid
            self.config_manager.save()

    def check_token(self):
        now = datetime.now().timestamp()
        if now >= self.expires_at:
            self.refresh_access_token()

    def refresh_access_token(self):
        url = urljoin(BASE_URL, self.TOKEN_PATH)
        payload = {
            'client_id': self.app_id,
            'client_secret': self.app_key,
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
        }
        resp = requests.post(url, json=payload)
        response = resp.json()
        self.access_token = response['access_token']
        self.refresh_token = response['refresh_token']
        self.expires_at = datetime.now().timestamp() + response['expires_in']
        self.session.headers['Authorization'] = 'Bear {}'.format(self.access_token)

        if self.config_manager:
            self.config_manager.access_token = self.access_token
            self.config_manager.refresh_token = self.refresh_token
            self.config_manager.expires_at = self.expires_at
            self.config_manager.save()

    def userinfo(self):
        self.check_token()

        url = urljoin(BASE_URL, 'user-info')
        resp = self.session.post(url)
        if resp.status_code != 200:
            raise APIError(resp.text)

        return resp.json()

    def get_folders(self):
        self.check_token()

        url = urljoin(BASE_URL, 'tag/list')
        params = {'types': 1, 'counts': 1}
        resp = self.session.post(url, params=params)
        if resp.status_code != 200:
            raise APIError(resp.text)

        folders = []
        for item in resp.json()['tags']:
            if item.get('type') != 'folder':
                continue

            folder_name = item['id'].split('/')[-1]
            folders.append({'name': folder_name, 'unread_count': item['unread_count']})

        folders.sort(key=itemgetter('name'))
        return folders

    def get_tags(self):
        self.check_token()

        url = urljoin(BASE_URL, 'tag/list')
        params = {'types': 1, 'counts': 1}
        resp = self.session.post(url, params=params)
        if resp.status_code != 200:
            raise APIError(resp.text)

        tags = []
        for item in resp.json()['tags']:
            if item.get('type') != 'tag':
                continue

            folder_name = item['id'].split('/')[-1]
            tags.append({'name': folder_name, 'unread_count': item['unread_count']})

        tags.sort(key=itemgetter('name'))
        return tags

    def get_subscription_list(self):
        self.check_token()

        url = urljoin(BASE_URL, 'subscription/list')
        resp = self.session.get(url)
        if resp.status_code != 200:
            raise APIError(resp.text)

        for item in resp.json()['subscriptions']:
            yield Subscription.from_json(item)

    def get_stream_contents(self, stream_id, c=''):
        while True:
            articles, c = self.__get_stream_contents(stream_id, c)
            for a in articles:
                yield Article.from_json(a)
            if c is None:
                break

    def __get_stream_contents(self, stream_id, continuation=''):
        self.check_token()

        url = urljoin(BASE_URL, 'stream/contents/' + quote_plus(stream_id))
        params = {
            'n': 50,            # default 20, max 1000
            'r': '',
            'c': continuation,
            'output': 'json'
        }
        resp = self.session.post(url, params=params)
        if resp.status_code != 200:
            raise APIError(resp.text)

        if 'continuation' in resp.json():
            return resp.json()['items'], resp.json()['continuation']
        else:
            return resp.json()['items'], None

    def fetch_unread(self, folder=None, tags=None):
        self.check_token()

        url = urljoin(BASE_URL, 'stream/contents/')
        if folder:
            url = urljoin(
                url,
                quote_plus('user/{}/label/{}'.format(self.userid, folder))
            )
        params = {
            'xt': 'user/{}/state/com.google/read'.format(self.userid),
            'c': str(uuid4())
        }

        resp = self.session.post(url, params=params)
        if resp.status_code != 200:
            raise APIError(resp.text)

        for data in resp.json()['items']:
            categories = set([
                category.split('/')[-1] for category in data.get('categories', [])
                if category.find('label') > 0
            ])
            if tags and not categories.issuperset(set(tags)):
                continue
            yield Article.from_json(data)

        continuation = resp.json().get('continuation')
        while continuation:
            params['c'] = continuation
            resp = self.session.post(url, params=params)
            if resp.status_code != 200:
                raise APIError(resp.text)
            for data in resp.json()['items']:
                categories = set([
                    category.split('/')[-1] for category in data.get('categories', [])
                    if category.find('label') > 0
                ])
                if tags and not categories.issuperset(set(tags)):
                    continue
                yield Article.from_json(data)
            continuation = resp.json().get('continuation')

    def add_general_label(self, articles, label):
        self.check_token()

        url = urljoin(BASE_URL, 'edit-tag')
        for start in range(0, len(articles), 10):
            end = min(start + 10, len(articles))
            params = {
                'a': label,
                'i': [articles[idx].id for idx in range(start, end)]
            }
            resp = self.session.post(url, params=params)
            if resp.status_code != 200:
                raise APIError(resp.text)

    def add_tag(self, articles, tag):
        self.add_general_label(articles, 'user/-/label/{}'.format(tag))

    def mark_as_read(self, articles):
        self.add_general_label(articles, 'user/-/state/com.google/read')

    def mark_as_starred(self, articles):
        self.add_general_label(articles, 'user/-/state/com.google/starred')

    def mark_as_liked(self, articles):
        self.add_general_label(articles, 'user/-/state/com.google/like')

    def broadcast(self, articles):
        self.add_general_label(articles, 'user/-/state/com.google/broadcast')
