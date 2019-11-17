# coding: utf-8
from __future__ import print_function, unicode_literals

import os
import csv
import sys
import json
import codecs
import logging
import threading
from queue import Queue
from uuid import uuid4
from functools import partial
from logging.config import dictConfig
from collections import defaultdict, Counter

import yaml
import click
from flask import Flask, request
from requests_oauthlib import OAuth2Session

from inoreader import InoreaderClient
from inoreader.filter import get_filter
from inoreader.sim import sim_of, InvIndex
from inoreader.exception import NotLoginError
from inoreader.config import InoreaderConfigManager
from inoreader.consts import DEFAULT_APPID, DEFAULT_APPKEY


APPID_ENV_NAME = 'INOREADER_APP_ID'
APPKEY_ENV_NAME = 'INOREADER_APP_KEY'
TOKEN_ENV_NAME = 'INOREADER_AUTH_TOKEN'
ENV_NAMES = [APPID_ENV_NAME, APPKEY_ENV_NAME, TOKEN_ENV_NAME]

CONFIG_FILE = os.path.join(os.environ.get('HOME'), '.inoreader')
LOGGER = logging.getLogger(__name__)


dictConfig({
    'version': 1,
    'formatters': {
        'simple': {
            'format': '%(asctime)s - %(message)s',
        }
    },
    'handlers': {
        'default': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            "stream": "ext://sys.stdout",
        },
    },
    'loggers': {
        '__main__': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': False
        },
        'inoreader': {
            'handlers': ['default'],
            'level': 'DEBUG',
            'propagate': True
        },
    }
})


def get_client():
    config = InoreaderConfigManager(CONFIG_FILE)
    if not config.data:
        LOGGER.error("Please login first")
        sys.exit(1)

    client = InoreaderClient(
        config.app_id, config.app_key, config.access_token, config.refresh_token,
        config.expires_at, config_manager=config
    )
    return client


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
def main():
    pass


@main.command()
def login():
    """Login to your inoreader account with OAuth 2.0"""
    # run simple daemon http server to handle callback
    app = Flask(__name__)

    # disable flask output
    app.logger.disabled = True
    logger = logging.getLogger('werkzeug')
    logger.setLevel(logging.ERROR)
    logger.disabled = True
    sys.modules['flask.cli'].show_server_banner = lambda *x: None

    # use queue to pass data between threads
    queue = Queue()

    config = InoreaderConfigManager(CONFIG_FILE)
    app_id = config.app_id or DEFAULT_APPID
    app_key = config.app_key or DEFAULT_APPKEY
    state = str(uuid4())
    oauth = OAuth2Session(app_id,
                          redirect_uri='http://localhost:8080/oauth/redirect',
                          scope='read write',
                          state=state)

    @app.route('/oauth/redirect')
    def redirect():
        token = oauth.fetch_token('https://www.inoreader.com/oauth2/token',
                                  authorization_response=request.url,
                                  client_secret=app_key)
        queue.put(token)
        queue.task_done()
        return 'Done.'

    func = partial(app.run, port=8080, debug=False)
    threading.Thread(target=func, daemon=True).start()

    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    authorization_url, ret_state = oauth.authorization_url('https://www.inoreader.com/oauth2/auth')
    if state != ret_state:
        LOGGER.error("Server return bad state")
        sys.exit(1)

    token = None
    print('Open the link to authorize access:', authorization_url)
    while True:
        token = queue.get()
        if token:
            break

    queue.join()
    if token:
        config.app_id = app_id
        config.app_key = app_key
        config.access_token = token['access_token']
        config.refresh_token = token['refresh_token']
        config.expires_at = token['expires_at']
        config.save()
        print("Login successfully, tokens are saved in config file %s" % config.config_file)
    else:
        print("Login failed, please check your environment or try again later.")
        sys.exit(1)


@main.command("list-folders")
def list_folders():
    """List all folders"""
    client = get_client()
    res = client.get_folders()
    print("unread\tfolder")
    for item in res:
        print("{}\t{}".format(item['unread_count'], item['name']))


@main.command("list-tags")
def list_tags():
    """List all tags"""
    client = get_client()
    res = client.get_tags()
    for item in res:
        print("{}\t{}".format(item['unread_count'], item['name']))


@main.command("fetch-unread")
@click.option("-f", "--folder", required=True, help='Folder which articles belong to')
@click.option("-t", "--tags", help="Tag(s) for filtering, seprate with comma")
@click.option("-o", "--outfile", required=True, help="Filename to save articles")
@click.option("--out-format",
              type=click.Choice(['json', 'csv', 'plain', 'markdown', 'org-mode']),
              default='json',
              help='Format of output file, default: json')
def fetch_unread(folder, tags, outfile, out_format):
    """Fetch unread articles"""
    client = get_client()

    tag_list = [] if not tags else tags.split(',')
    fout = codecs.open(outfile, mode='w', encoding='utf-8')
    writer = csv.writer(fout, delimiter=',') if out_format == 'csv' else None
    for idx, article in enumerate(client.fetch_unread(folder=folder, tags=tag_list)):
        if idx > 0 and (idx % 10) == 0:
            LOGGER.info("fetched %d articles", idx)
        title = article.title
        text = article.text
        if out_format == 'json':
            print(json.dumps({'title': title, 'content': text}, ensure_ascii=False), file=fout)
        elif out_format == 'csv':
            writer.writerow([title, text])
        elif out_format == 'plain':
            print('TITLE: {}'.format(title), file=fout)
            print("CONTENT: {}".format(text), file=fout)
            print(file=fout)
        elif out_format == 'markdown':
            print('# {}\n'.format(title), file=fout)
            print(text + '\n', file=fout)
        elif out_format == 'org-mode':
            print('* {}\n'.format(title), file=fout)
            print(text + '\n', file=fout)

    LOGGER.info("fetched %d articles and saved them in %s", idx + 1, outfile)

    fout.close()


def apply_action(articles, client, action, tags):
    if action == 'tag':
        for tag in tags.split(','):
            client.add_tag(articles, tag)

        for article in articles:
            LOGGER.info("Add tags [%s] on article: %s", tags, article.title)
    elif action == 'mark_as_read':
        client.mark_as_read(articles)
        for article in articles:
            LOGGER.info("Mark article as read: %s", article.title)
    elif action == 'like':
        client.mark_as_liked(articles)
        for article in articles:
            LOGGER.info("Mark article as liked: %s", article.title)
    elif action == 'broadcast':
        client.broadcast(articles)
        for article in articles:
            LOGGER.info("Boradcast article: {}", article.title)
    elif action == 'star':
        client.mark_as_starred(articles)
        for article in articles:
            LOGGER.info("Starred article: {}", article.title)


@main.command("filter")
@click.option("-r", "--rules-file", required=True, help='YAML file with your rules')
def filter_articles(rules_file):
    """Select articles and do something"""
    client = get_client()
    filters = []
    for rule in yaml.load(open(rules_file)):
        name = rule.get('name')
        folders = rule['folders']

        fields = []
        # only 'title' or 'content' is supported now
        for field in rule.get('fields', ['title', 'content']):
            if field not in ('title', 'content'):
                continue
            fields.append(field)
        cur_filter = get_filter(rule['filter'])

        actions = []
        # only 'mark_as_read', 'like', 'star', 'broadcast', 'tag' is supported now
        for action in rule.get('actions', [{'type': 'mark_as_read'}]):
            if action['type'] not in ('mark_as_read', 'like', 'star', 'broadcast', 'tag'):
                continue
            actions.append(action)

        filters.append({
            'name': name,
            'folders': folders,
            'fields': fields,
            'filter': cur_filter,
            'actions': actions
        })

    articles_by_foler = {}      # folder -> articles
    matched_articles = defaultdict(list)       # action -> articles
    for rule in filters:
        articles = []
        for folder in rule['folders']:
            if folder not in articles_by_foler:
                articles_by_foler[folder] = list(client.fetch_unread(folder=folder))

            articles.extend(articles_by_foler[folder])

        # FIXME: deduplicate
        count = 0
        for article in articles:
            matched = False
            if 'title' in rule['fields'] and rule['filter'].validate(article.title):
                matched = True
            if 'content' in rule['fields'] and rule['filter'].validate(article.text):
                matched = True

            if matched:
                for action in rule['actions']:
                    matched_articles[action['type']].append((article, action))

                count += 1

        LOGGER.info(
            "matched %d articles in folder(s) %s with filter named '%s'",
            count, rule['folders'], rule['name']
        )

    for action_name in matched_articles:
        articles, actions = zip(*matched_articles[action_name])
        if action_name != 'tag':
            apply_action(articles, client, action_name, None)
        else:
            for article, action in zip(articles, actions):
                apply_action([article], client, 'tag', action['tags'])


@main.command("get-subscriptions")
@click.option("-o", "--outfile", help="Filename to save results")
@click.option("-f", "--folder", help='Folder which subscriptions belong to')
@click.option("--out-format",
              type=click.Choice(["json", "csv"]), default="csv",
              help="Format of output, default: csv")
def get_subscriptions(outfile, folder, out_format):
    """Get your subscriptions"""
    client = get_client()
    results = []
    for sub in client.get_subscription_list():
        sub_categories = set([category['label'] for category in sub.categories])
        if folder and folder not in sub_categories:
            continue

        results.append({
            'id': sub.id,
            'title': sub.title,
            'url': sub.url,
            'folders': ';'.join(sub_categories),
        })

    fout = open(outfile, 'w') if outfile else sys.stdout
    if out_format == 'csv':
        headers = ['id', 'title', 'url', 'folders']
        writer = csv.DictWriter(fout, headers, quoting=csv.QUOTE_ALL, delimiter="\t")
        writer.writeheader()
        for item in results:
            writer.writerow(item)
    elif out_format == 'json':
        json.dump(results, fout, ensure_ascii=False, indent=4)

    if outfile:
        fout.close()


@main.command("fetch-articles")
@click.option("-i", "--stream-id", required=True, help='Stream ID which you want to fetch')
@click.option("-o", "--outfile", required=True, help="Filename to save results")
@click.option("--out-format",
              type=click.Choice(["json", "csv", 'plain', 'markdown', 'org-mode']),
              default="json",
              help="Format of output, default: json")
def fetch_articles(outfile, stream_id, out_format):
    """Fetch articles by stream id"""
    client = get_client()

    fout = codecs.open(outfile, mode='w', encoding='utf-8')
    writer = None
    if out_format == 'csv':
        writer = csv.DictWriter(fout, ['title', 'content'], delimiter=',', quoting=csv.QUOTE_ALL)
        writer.writeheader()

    for idx, article in enumerate(client.get_stream_contents(stream_id)):
        if idx > 0 and (idx % 10) == 0:
            LOGGER.info("fetched %d articles", idx)

        title = article.title
        text = article.text
        if out_format == 'json':
            print(json.dumps({'title': title, 'content': text}, ensure_ascii=False), file=fout)
        elif out_format == 'csv':
            writer.writerow({'title': title, 'content': text})
        elif out_format == 'plain':
            print('TITLE: {}'.format(title), file=fout)
            print("CONTENT: {}".format(text), file=fout)
            print(file=fout)
        elif out_format == 'markdown':
            print('# {}\n'.format(title), file=fout)
            print(text + '\n', file=fout)
        elif out_format == 'org-mode':
            print('* {}\n'.format(title), file=fout)
            print(text + '\n', file=fout)

    LOGGER.info("fetched %d articles and saved them in %s", idx + 1, outfile)

    fout.close()


@main.command()
@click.option("-f", "--folder", help="Folder you want to deduplicate")
@click.option("-t", "--thresh", type=float, default=0.8,
              help="Minimum similarity score")
def dedupe(folder, thresh):
    """Deduplicate articles"""
    client = get_client()
    matched_articles, index = [], InvIndex()
    for idx, article in enumerate(client.fetch_unread(folder=folder)):
        if idx > 0 and (idx % 10) == 0:
            LOGGER.info("fetched %d articles and found %d duplicate", idx, len(matched_articles))

        related = index.retrieve(article.title, k=10)
        sims = Counter()
        for docid, doc, _ in related:
            if docid == article.id:
                continue
            sims[doc] = sim_of(doc, article.title, method='cosine', term='char', ngram_range=(2, 3))

        if sims and max(sims.values()) >= thresh:
            top_doc, top_score = sims.most_common()[0]
            print("article 「{}」 is duplicate with  -> 「{}」".format(
                article.title, top_doc
            ))
            matched_articles.append(article)
            continue

        index.add_doc(article)

    LOGGER.info("fetched %d articles and found %d duplicate", idx + 1, len(matched_articles))
    apply_action(matched_articles, client, 'mark_as_read', None)


if __name__ == '__main__':
    main()
