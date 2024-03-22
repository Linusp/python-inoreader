# coding: utf-8
import os

BASE_URL = "https://www.inoreader.com/reader/api/0/"
LOGIN_URL = "https://www.inoreader.com/accounts/ClientLogin"

DEFAULT_APPID = "your_app_id"
DEFAULT_APPKEY = "your_app_key"

CONFIG_FILE = os.path.join(os.environ.get("HOME"), ".inoreader")
