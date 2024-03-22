# coding: utf-8
from __future__ import print_function, unicode_literals

import codecs
import os
from configparser import ConfigParser


class InoreaderConfigManager:
    def __init__(self, config_file):
        self.config_file = config_file
        self.data = {}
        if os.path.exists(config_file):
            self.load()

    def load(self):
        config_parser = ConfigParser()
        config_parser.read(self.config_file)
        for section_name in config_parser.sections():
            self.data[section_name] = dict(config_parser[section_name])

    def save(self):
        with codecs.open(self.config_file, mode="w", encoding="utf-8") as f:
            config_parser = ConfigParser()
            config_parser.update(self.data)
            config_parser.write(f)

    @property
    def app_id(self):
        return self.data.get("auth", {}).get("appid")

    @app_id.setter
    def app_id(self, value):
        self.data.setdefault("auth", {})["appid"] = value

    @property
    def app_key(self):
        return self.data.get("auth", {}).get("appkey")

    @app_key.setter
    def app_key(self, value):
        self.data.setdefault("auth", {})["appkey"] = value

    @property
    def access_token(self):
        return self.data.get("auth", {}).get("access_token")

    @access_token.setter
    def access_token(self, value):
        self.data.setdefault("auth", {})["access_token"] = value

    @property
    def refresh_token(self):
        return self.data.get("auth", {}).get("refresh_token")

    @refresh_token.setter
    def refresh_token(self, value):
        self.data.setdefault("auth", {})["refresh_token"] = value

    @property
    def expires_at(self):
        return self.data.get("auth", {}).get("expires_at")

    @expires_at.setter
    def expires_at(self, value):
        self.data.setdefault("auth", {})["expires_at"] = value

    @property
    def proxies(self):
        return self.data.get("proxies", {})

    @proxies.setter
    def proxies(self, value):
        self.data["proxies"] = value
