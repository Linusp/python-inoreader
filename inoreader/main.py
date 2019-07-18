# coding: utf-8
from __future__ import print_function, unicode_literals

import os
import csv
import sys
import json
import codecs
import argparse
from datetime import datetime
from configparser import ConfigParser

import yaml
from inoreader import InoreaderClient
from inoreader.filter import Filter


APPID_ENV_NAME = 'INOREADER_APP_ID'
APPKEY_ENV_NAME = 'INOREADER_APP_KEY'
TOKEN_ENV_NAME = 'INOREADER_AUTH_TOKEN'
ENV_NAMES = [APPID_ENV_NAME, APPKEY_ENV_NAME, TOKEN_ENV_NAME]

CONFIG_FILE = os.path.join(os.environ.get('HOME'), '.inoreader')


def read_config():
    config = ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)

    return config


def get_appid_key(config):
    # 先尝试从配置文件中读取 appid 和 appkey
    appid = config.get('auth', 'appid') if config.has_section('auth') else None
    appkey = config.get('auth', 'appkey') if config.has_section('auth') else None
    if not appid:
        appid = os.environ.get(APPID_ENV_NAME)
    if not appkey:
        appkey = os.environ.get(APPKEY_ENV_NAME)

    return appid, appkey


def get_client():
    config = read_config()
    appid, appkey = get_appid_key(config)
    if not appid or not appkey:
        print("'appid' or 'appkey' is missing")
        sys.exit(1)

    token = None
    if config.has_section('auth'):
        token = config.get('auth', 'token')
        token = token or os.environ.get(TOKEN_ENV_NAME)
    if not token:
        print("Please login first")
        sys.exit(1)

    userid = None
    if config.has_section('user'):
        userid = config.get('user', 'id')

    client = InoreaderClient(appid, appkey, userid=userid, auth_token=token)
    return client


class SubcommandHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action(self, action):
        parts = super(argparse.RawDescriptionHelpFormatter, self)._format_action(action)
        if action.nargs == argparse.PARSER:
            parts = "\n".join(parts.split("\n")[1:])
        return parts


class CmdParser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write('error: %s\n\n' % message)
        self.print_help()
        sys.exit(1)


def add_login_parser(subparsers):
    subparsers.add_parser('login', help="Login to Inoreader")


def login():
    client = InoreaderClient(None, None)

    username = input("EMAIL: ").strip()
    password = input("PASSWORD: ").strip()
    status = client.login(username, password)
    if status:
        print("Login as '{}'".format(username))
        auth_token = client.auth_token
        config = read_config()
        if 'auth' in config:
            config['auth']['token'] = auth_token
        else:
            config['auth'] = {'token': auth_token}

        appid, appkey = get_appid_key(config)
        client = InoreaderClient(appid, appkey, auth_token=auth_token)
        config['user'] = {'email': username, 'id': client.userinfo()['userId']}
        with codecs.open(CONFIG_FILE, mode='w', encoding='utf-8') as fconfig:
            config.write(fconfig)
        print("save token in {}, ".format(username, CONFIG_FILE))
    else:
        print("Login failed: Wrong username or password")
        sys.exit(1)


def add_folders_list_parser(subparsers):
    subparsers.add_parser('list-folders', help="List all folders")


def list_folders():
    client = get_client()
    res = client.get_folders()
    print("unread\tfolder")
    for item in res:
        print("{}\t{}".format(item['unread_count'], item['name']))


def get_subscription_list():
    client = get_client()
    for item in client.get_subscription_list():
        print(item.__dict__)


def get_stream_contents(stream_id):
    client = get_client()
    for item in client.get_stream_contents(stream_id):
        print(item.__dict__)


def add_tags_list_parser(subparsers):
    subparsers.add_parser('list-tags', help="List all tags")


def list_tags():
    client = get_client()
    res = client.get_tags()
    for item in res:
        print("{}\t{}".format(item['unread_count'], item['name']))


def add_unread_fetch_parser(subparsers):
    parser = subparsers.add_parser('fetch-unread', help='Fetch unread articles')
    parser.add_argument("-f", "--folder", required=True, help='Folder which articles belong to')
    parser.add_argument("-t", "--tags", help="Tag(s) for filtering, seprate with comma")
    parser.add_argument("-o", "--outfile", required=True, help="Filename to save articles")
    parser.add_argument(
        "--out-format",
        choices=['json', 'csv', 'plain'],
        default='json',
        help='Format of output file, default: json'
    )


def fetch_unread(folder, tags, outfile, out_format):
    client = get_client()

    tag_list = [] if not tags else tags.split(',')
    fout = codecs.open(outfile, mode='w', encoding='utf-8')
    writer = csv.writer(fout, delimiter=',') if out_format == 'csv' else None
    for idx, article in enumerate(client.fetch_unread(folder=folder, tags=tag_list)):
        if idx > 0 and (idx % 10) == 0:
            print("[{}] fetched {} articles".format(datetime.now(), idx))
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

    print("[{}] fetched {} articles and saved them in {}".format(datetime.now(), idx + 1, outfile))

    fout.close()


def add_filter_parser(subparsers):
    parser = subparsers.add_parser('filter', help='Select articles and do something')
    parser.add_argument("-f", "--folder", required=True, help='Folder which articles belong to')
    parser.add_argument("-r", "--rules", required=True, help='YAML file with your rules')
    parser.add_argument("-a", "--action", default='read',
                        choices=['read', 'like', 'tag', 'broadcast', 'star'],
                        help='Action you want to perform, default: read')
    parser.add_argument("-t", "--tags",
                        help="Tag(s) to be used when action is 'tag', seprate with comma")


def apply_action(articles, client, action, tags):
    if action == 'tag':
        for tag in tags.split(','):
            client.add_tag(articles, tag)

        for article in articles:
            print("Add tags [{}] on article: {}".format(tags, article.title))
    elif action == 'read':
        client.mark_as_read(articles)
        for article in articles:
            print("Mark article as read: {}".format(article.title))
    elif action == 'like':
        client.mark_as_liked(articles)
        for article in articles:
            print("Mark article as liked: {}".format(article.title))
    elif action == 'broadcast':
        client.broadcast(articles)
        for article in articles:
            print("Boradcast article: {}".format(article.title))
    elif action == 'star':
        client.mark_as_starred(articles)
        for article in articles:
            print("Starred article: {}".format(article.title))


def filter_articles(folder, rules_file, action, tags):
    client = get_client()
    filters = []
    for rule in yaml.load(open(rules_file)):
        filters.append({
            'field': rule.get('field', 'title'),
            'filter': Filter.from_config(rule),
        })

    matched_articles = []
    for idx, article in enumerate(client.fetch_unread(folder=folder)):
        matched = False
        for article_filter in filters:
            if article_filter['field'] in ('title', 'title_or_content') and \
               article_filter['filter'].validate(article.title):
                matched = True
                break
            if article_filter['field'] in ('content', 'title_or_content') and \
               article_filter['filter'].validate(article.text):
                matched = True
                break
        if matched:
            matched_articles.append(article)
            if len(matched_articles) == 10:
                apply_action(matched_articles, client, action, tags)
                matched_articles = []

    if matched_articles:
        apply_action(matched_articles, client, action, tags)


def main():
    parser = CmdParser(
        usage="inoreader [-h] <command> ...",
        formatter_class=SubcommandHelpFormatter
    )
    subparsers = parser.add_subparsers(title="commands", dest='command')
    subparsers.required = True

    add_login_parser(subparsers)
    add_folders_list_parser(subparsers)
    add_tags_list_parser(subparsers)
    add_unread_fetch_parser(subparsers)
    add_filter_parser(subparsers)

    args = parser.parse_args()
    if args.command == 'login':
        login()
    elif args.command == 'list-folders':
        list_folders()
    elif args.command == 'list-tags':
        list_tags()
    elif args.command == 'fetch-unread':
        fetch_unread(args.folder, args.tags, args.outfile, args.out_format)
    elif args.command == 'filter':
        if args.action == 'tag' and not args.tags:
            print("Need at least one tag when action is 'tag'!")
            sys.exit(1)

        filter_articles(args.folder, args.rules, args.action, args.tags)


if __name__ == '__main__':
    main()
