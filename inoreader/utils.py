# coding: utf-8
from __future__ import print_function, unicode_literals

import os
import re
import shutil

import requests
from lxml import html


def normalize_whitespace(text):
    text = re.sub(r"[\n\r\t]", " ", text)
    text = re.sub(r" +", " ", text)

    return text.strip()


def extract_text(html_content):
    if not html_content:
        return html_content

    content = html.fromstring(html_content)
    for img in content.iter("img"):
        img_src = img.get("src")
        img_alt = img.get("alt") or img_src
        if not img_src:
            continue

        img.text = "![%s](%s)" % (img_alt, img_src)

    for link in content.iter("a"):
        url = link.get("href")
        text = link.text or url
        if not url:
            continue

        link.text = "[%s](%s)" % (text, url)
    try:
        return content.text_content().replace("\xa0", "").strip()
    except Exception:
        return ""


def download_image(url, path, filename, proxies=None):
    response = requests.get(url, stream=True, proxies=proxies)
    if response.status_code not in (200, 201):
        return None

    content_type = response.headers.get("Content-Type", "")
    if not content_type or not content_type.startswith("image/"):
        return None

    content_length = int(response.headers.get("Content-Length") or "0")
    if content_length <= 0:
        return None

    suffix = content_type.replace("image/", "")
    if suffix == "svg+xml":
        suffix = "svg"

    image_filename = filename + "." + suffix
    with open(os.path.join(path, image_filename), "wb") as f:
        response.raw.decode_content = True
        shutil.copyfileobj(response.raw, f)

    return image_filename
