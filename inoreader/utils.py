# coding: utf-8
from __future__ import print_function, unicode_literals

import re

from lxml import html


def normalize_whitespace(text):
    text = re.sub(r'[\n\r\t]', ' ', text)
    text = re.sub(r' +', ' ', text)

    return text.strip()


def extract_text(html_content):
    if not html_content:
        return html_content

    content = html.fromstring(html_content)
    for img in content.iter('img'):
        img_src = img.get('src')
        img_alt = img.get('alt') or img_src
        if not img_src:
            continue

        img.text = '![%s](%s)' % (img_alt, img_src)

    for link in content.iter('a'):
        url = link.get('href')
        text = link.text or url
        if not url:
            continue

        link.text = '[%s](%s)' % (text, url)

    return content.text_content().replace('\xa0', '').strip()
