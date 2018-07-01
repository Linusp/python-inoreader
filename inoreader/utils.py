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
    return content.text_content().replace('\xa0', '').strip()
