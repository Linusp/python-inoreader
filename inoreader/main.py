# coding: utf-8
from __future__ import print_function, unicode_literals

import codecs
import csv
import json
import logging
import os
import re
import sys
import threading
from collections import Counter, defaultdict
from functools import partial, wraps
from logging.config import dictConfig
from operator import itemgetter
from queue import Queue
from uuid import uuid4

import click
import yaml
from flask import Flask, request
from requests_oauthlib import OAuth2Session
from tabulate import tabulate

from inoreader import InoreaderClient
from inoreader.config import InoreaderConfigManager
from inoreader.consts import DEFAULT_APPID, DEFAULT_APPKEY
from inoreader.exception import APIError, NotLoginError
from inoreader.filter import get_filter
from inoreader.sim import InvIndex, sim_of
from inoreader.utils import download_image

APPID_ENV_NAME = "INOREADER_APP_ID"
APPKEY_ENV_NAME = "INOREADER_APP_KEY"
TOKEN_ENV_NAME = "INOREADER_AUTH_TOKEN"
ENV_NAMES = [APPID_ENV_NAME, APPKEY_ENV_NAME, TOKEN_ENV_NAME]

CONFIG_FILE = os.path.join(os.environ.get("HOME"), ".inoreader")
LOGGER = logging.getLogger(__name__)


dictConfig(
    {
        "version": 1,
        "formatters": {
            "simple": {
                "format": "%(asctime)s - %(message)s",
            }
        },
        "handlers": {
            "default": {
                "level": "DEBUG",
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "__main__": {"handlers": ["default"], "level": "DEBUG", "propagate": False},
            "inoreader": {"handlers": ["default"], "level": "DEBUG", "propagate": True},
        },
    }
)


def get_client(config_file=CONFIG_FILE):
    config = InoreaderConfigManager(config_file)
    if not config.data:
        LOGGER.error("Please login first")
        sys.exit(1)

    client = InoreaderClient(
        config.app_id,
        config.app_key,
        config.access_token,
        config.refresh_token,
        config.expires_at,
        config_manager=config,
    )
    return client


def catch_error(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NotLoginError:
            print("Error: Please login first!")
            sys.exit(1)
        except APIError as exception:
            print("Error:", str(exception))
            sys.exit(1)

    return wrapper


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main():
    pass


@main.command()
def login():
    """Login to your inoreader account with OAuth 2.0"""
    # run simple daemon http server to handle callback
    app = Flask(__name__)

    # disable flask output
    app.logger.disabled = True
    logger = logging.getLogger("werkzeug")
    logger.setLevel(logging.ERROR)
    logger.disabled = True
    sys.modules["flask.cli"].show_server_banner = lambda *x: None

    # use queue to pass data between threads
    queue = Queue()

    config = InoreaderConfigManager(CONFIG_FILE)
    app_id = config.app_id or DEFAULT_APPID
    app_key = config.app_key or DEFAULT_APPKEY
    state = str(uuid4())
    oauth = OAuth2Session(
        app_id,
        redirect_uri="http://localhost:8080/oauth/redirect",
        scope="read write",
        state=state,
    )

    @app.route("/oauth/redirect")
    def redirect():
        token = oauth.fetch_token(
            "https://www.inoreader.com/oauth2/token",
            authorization_response=request.url,
            client_secret=app_key,
            proxies=config.proxies,
        )
        queue.put(token)
        queue.task_done()
        return "Done."

    func = partial(app.run, port=8080, debug=False)
    threading.Thread(target=func, daemon=True).start()

    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    authorization_url, ret_state = oauth.authorization_url("https://www.inoreader.com/oauth2/auth")
    if state != ret_state:
        LOGGER.error("Server return bad state")
        sys.exit(1)

    token = None
    print("Open the link to authorize access:", authorization_url)
    while True:
        token = queue.get()
        if token:
            break

    queue.join()
    if token:
        config.app_id = app_id
        config.app_key = app_key
        config.access_token = token["access_token"]
        config.refresh_token = token["refresh_token"]
        config.expires_at = token["expires_at"]
        config.save()
        LOGGER.info("Login successfully, tokens are saved in config file %s", config.config_file)
    else:
        LOGGER.warning("Login failed, please check your environment or try again later.")
        sys.exit(1)


@main.command("list-folders")
@catch_error
def list_folders():
    """List all folders"""
    client = get_client()
    res = client.get_folders()

    output_info = [["Folder", "Unread Count"]]
    for item in res:
        output_info.append([item["name"], item["unread_count"]])

    print(tabulate(output_info, headers="firstrow", tablefmt="github"))


@main.command("list-tags")
@catch_error
def list_tags():
    """List all tags"""
    client = get_client()
    res = client.get_tags()

    output_info = [["Tag", "Unread Count"]]
    for item in res:
        output_info.append([item["name"], item["unread_count"]])

    print(tabulate(output_info, headers="firstrow", tablefmt="github"))


@main.command("fetch-unread")
@click.option("-f", "--folder", required=True, help="Folder which articles belong to")
@click.option("-t", "--tags", help="Tag(s) for filtering, separate with comma")
@click.option("-o", "--outfile", required=True, help="Filename to save articles")
@click.option(
    "--out-format",
    type=click.Choice(["json", "csv", "plain", "markdown", "org-mode"]),
    default="json",
    help="Format of output file, default: json",
)
@catch_error
def fetch_unread(folder, tags, outfile, out_format):
    """Fetch unread articles"""
    client = get_client()

    tag_list = [] if not tags else tags.split(",")
    fout = codecs.open(outfile, mode="w", encoding="utf-8")
    writer = csv.writer(fout, delimiter=",") if out_format == "csv" else None
    for idx, article in enumerate(client.fetch_unread(folder=folder, tags=tag_list)):
        if idx > 0 and (idx % 10) == 0:
            LOGGER.info("fetched %d articles", idx)
        title = article.title
        text = article.text
        link = article.link
        if out_format == "json":
            print(
                json.dumps({"title": title, "content": text, "url": link}, ensure_ascii=False),
                file=fout,
            )
        elif out_format == "csv":
            writer.writerow([link, title, text])
        elif out_format == "plain":
            print("TITLE: {}".format(title), file=fout)
            print("LINK: {}".format(link), file=fout)
            print("CONTENT: {}".format(text), file=fout)
            print(file=fout)
        elif out_format == "markdown":
            if link:
                print("# [{}]({})\n".format(title, link), file=fout)
            else:
                print("# {}\n".format(title), file=fout)
            print(text + "\n", file=fout)
        elif out_format == "org-mode":
            if link:
                title = title.replace("[", "_").replace("]", "_")
                print("* [[{}][{}]]\n".format(link, title), file=fout)
            else:
                print("* {}\n".format(title), file=fout)
            print(text + "\n", file=fout)

    LOGGER.info("fetched %d articles and saved them in %s", idx + 1, outfile)

    fout.close()


def apply_action(articles, client, action, tags):
    if action == "tag":
        for tag in tags.split(","):
            client.add_tag(articles, tag)

        for article in articles:
            LOGGER.info("Add tags [%s] on article: %s", tags, article.title)
    elif action == "mark_as_read":
        client.mark_as_read(articles)
        for article in articles:
            LOGGER.info("Mark article as read: %s", article.title)
    elif action == "like":
        client.mark_as_liked(articles)
        for article in articles:
            LOGGER.info("Mark article as liked: %s", article.title)
    elif action == "broadcast":
        client.broadcast(articles)
        for article in articles:
            LOGGER.info("Broadcast article: %s", article.title)
    elif action == "star":
        client.mark_as_starred(articles)
        for article in articles:
            LOGGER.info("Starred article: %s", article.title)
    elif action == "unstar":
        client.remove_starred(articles)
        for article in articles:
            LOGGER.info("Unstarred article: %s", article.title)


@main.command("filter")
@click.option("-r", "--rules-file", required=True, help="YAML file with your rules")
@catch_error
def filter_articles(rules_file):
    """Select articles and do something"""
    client = get_client()
    matched_articles = defaultdict(list)
    for rule in yaml.load(open(rules_file), Loader=yaml.Loader):
        fields = [
            field
            for field in rule.get("fields", ["title", "content"])
            if field in ("title", "content")
        ]
        cur_filter = get_filter(rule["filter"])
        actions = []
        # only 'mark_as_read', 'like', 'star', 'broadcast', 'tag' is supported now
        for action in rule.get("actions", [{"type": "mark_as_read"}]):
            if action["type"] not in (
                "mark_as_read",
                "like",
                "star",
                "broadcast",
                "tag",
                "unstar",
            ):
                continue
            actions.append(action)

        articles = []
        if "folders" in rule:
            for folder in rule["folders"]:
                articles.extend(client.fetch_unread(folder=folder))
        else:
            for articles_info in rule.get("articles", []):
                articles.extend(client.fetch_articles(**articles_info))

        # FIXME: deduplicate
        count = 0
        for article in articles:
            matched = False
            if "title" in fields and cur_filter.validate(article.title):
                matched = True
            if "content" in fields and cur_filter.validate(article.text):
                matched = True

            if matched:
                for action in actions:
                    matched_articles[action["type"]].append((article, action))

                count += 1

        LOGGER.info(
            "matched %d articles with filter named '%s'",
            count,
            rule["name"],
        )

    for action_name in matched_articles:
        articles, actions = zip(*matched_articles[action_name])
        if action_name != "tag":
            apply_action(articles, client, action_name, None)
        else:
            for article, action in zip(articles, actions):
                apply_action([article], client, "tag", action["tags"])


@main.command("get-subscriptions")
@click.option("-o", "--outfile", help="Filename to save results")
@click.option("-f", "--folder", help="Folder which subscriptions belong to")
@click.option(
    "--out-format",
    type=click.Choice(["json", "csv"]),
    default="csv",
    help="Format of output, default: csv",
)
@catch_error
def get_subscriptions(outfile, folder, out_format):
    """Get your subscriptions"""
    client = get_client()
    results = []
    for sub in client.get_subscription_list():
        sub_categories = {category["label"] for category in sub.categories}
        if folder and folder not in sub_categories:
            continue

        results.append(
            {
                "id": sub.id,
                "title": sub.title,
                "url": sub.url,
                "folders": ";".join(sub_categories),
            }
        )

    fout = open(outfile, "w") if outfile else sys.stdout
    if out_format == "csv":
        headers = ["id", "title", "url", "folders"]
        writer = csv.DictWriter(fout, headers, quoting=csv.QUOTE_ALL, delimiter="\t")
        writer.writeheader()
        for item in results:
            writer.writerow(item)
    elif out_format == "json":
        json.dump(results, fout, ensure_ascii=False, indent=4)

    if outfile:
        fout.close()


@main.command("fetch-articles")
@click.option("-i", "--stream-id", required=True, help="Stream ID which you want to fetch")
@click.option("-o", "--outfile", required=True, help="Filename to save results")
@click.option(
    "--out-format",
    type=click.Choice(["json", "csv", "plain", "markdown", "org-mode"]),
    default="json",
    help="Format of output, default: json",
)
@catch_error
def fetch_articles(outfile, stream_id, out_format):
    """Fetch articles by stream id"""
    client = get_client()

    fout = codecs.open(outfile, mode="w", encoding="utf-8")
    writer = None
    if out_format == "csv":
        writer = csv.DictWriter(fout, ["title", "content"], delimiter=",", quoting=csv.QUOTE_ALL)
        writer.writeheader()

    for idx, article in enumerate(client.get_stream_contents(stream_id)):
        if idx > 0 and (idx % 10) == 0:
            LOGGER.info("fetched %d articles", idx)

        title = article.title
        text = article.text
        if out_format == "json":
            print(json.dumps({"title": title, "content": text}, ensure_ascii=False), file=fout)
        elif out_format == "csv":
            writer.writerow({"title": title, "content": text})
        elif out_format == "plain":
            print("TITLE: {}".format(title), file=fout)
            print("CONTENT: {}".format(text), file=fout)
            print(file=fout)
        elif out_format == "markdown":
            print("# {}\n".format(title), file=fout)
            print(text + "\n", file=fout)
        elif out_format == "org-mode":
            print("* {}\n".format(title), file=fout)
            print(text + "\n", file=fout)

    LOGGER.info("fetched %d articles and saved them in %s", idx + 1, outfile)

    fout.close()


@main.command()
@click.option("-f", "--folder", help="Folder you want to deduplicate")
@click.option("-t", "--thresh", type=float, default=0.8, help="Minimum similarity score")
@catch_error
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
            sims[doc] = sim_of(doc, article.title, method="cosine", term="char", ngram_range=(2, 3))

        if sims and max(sims.values()) >= thresh:
            top_doc, top_score = sims.most_common()[0]
            print("article 「{}」 is duplicate with  -> 「{}」".format(article.title, top_doc))
            matched_articles.append(article)
            continue

        index.add_doc(article)

    LOGGER.info("fetched %d articles and found %d duplicate", idx + 1, len(matched_articles))
    apply_action(matched_articles, client, "mark_as_read", None)


@main.command("fetch-starred")
@click.option("-f", "--folder", help="Folder which articles belong to")
@click.option("-t", "--tags", help="Tag(s) for filtering, separate with comma")
@click.option(
    "-o", "--outfile", help="Filename to save articles, required when output format is `csv`"
)
@click.option(
    "-d", "--outdir", help="Directory to save articles, required when output format is not `csv`"
)
@click.option("-l", "--limit", type=int)
@click.option("--save-image", is_flag=True)
@click.option(
    "--out-format",
    type=click.Choice(["json", "csv", "markdown", "org-mode"]),
    default="json",
    help="Format of output file, default: json",
)
@catch_error
def fetch_starred(folder, tags, outfile, outdir, limit, save_image, out_format):
    """Fetch starred articles"""
    client = get_client()

    if out_format == "csv" and not outfile:
        click.secho("`outfile` is required!", fg="red")
        return -1
    elif out_format != "csv" and not outdir:
        click.secho("`outdir` is required!", fg="red")
        return -1

    if out_format == "csv":
        fout = codecs.open(outfile, mode="w", encoding="utf-8")
        writer = (
            csv.writer(fout, delimiter=",", quoting=csv.QUOTE_ALL) if out_format == "csv" else None
        )
    elif not os.path.exists(outdir):
        os.makedirs(outdir)

    tag_list = [] if not tags else tags.split(",")
    url_to_image = {}
    fetched_count = 0
    for article in client.fetch_starred(folder=folder, tags=tag_list, limit=limit):
        if limit and fetched_count >= limit:
            break

        fetched_count += 1
        title = article.title
        text = article.text
        link = article.link
        if out_format == "csv":
            writer.writerow([link, title, text])
            continue

        filename = re.sub(r"\s+", "_", title)
        filename = re.sub(r"[\[\]\(\)（）：:，,/|]", "_", filename)
        filename = re.sub(r'[“”\'"]', "", filename)
        filename = re.sub(r"-+", "-", filename)
        filename = filename[:50]
        if out_format == "json":
            filename += ".json"
        elif out_format == "markdown":
            filename += ".md"
        elif out_format == "org-mode":
            filename += ".org"

        if save_image:
            image_contents = re.findall(r"!\[(?:[^\[\]]+)\]\((?:[^\(\)]+)\)", text)
            for image_content in image_contents:
                match = re.match(r"!\[(?P<alt>[^\[\]]+)\]\((?P<url>[^\(\)]+)\)", image_content)
                image_alt, image_url = itemgetter("alt", "url")(match.groupdict())
                if image_url in url_to_image:
                    text = text.replace(
                        image_content, "![{}]({})".format(image_alt, url_to_image[image_url])
                    )
                    continue

                image_filename = ""
                if not re.findall(r"[\?\!\/=\&]", image_alt):
                    image_filename = re.sub(r"\.[a-z]+$", "", image_alt)
                else:
                    image_filename = str(uuid4()).replace("-", "")

                return_image_file = download_image(
                    image_url, outdir, image_filename, proxies=client.proxies
                )
                if return_image_file:
                    LOGGER.info('Download image as "%s" from "%s"', return_image_file, image_url)
                    text = text.replace(
                        image_content, "![{}]({})".format(image_alt, return_image_file)
                    )
                    url_to_image[image_url] = return_image_file

        with open(os.path.join(outdir, filename), "w") as fout:
            if out_format == "json":
                json.dump(
                    {"title": title, "content": text, "url": link},
                    fout,
                    ensure_ascii=False,
                    indent=4,
                )
            elif out_format == "markdown":
                print(title + "\n=====\n\nLINK: " + link + "\n\n", file=fout)
                text = re.sub(r"!\[([^\[\]]+)\]\(([^\(\)]+)\)", r"\n![\1](\2)\n", text)
                print(text + "\n", file=fout)
            elif out_format == "org-mode":
                print("#+TITLE: " + title + "\n\nLINK: " + link + "\n\n", file=fout)
                text = re.sub(r"!\[([^\[\]]+)\]\(([^\(\)]+)\)", r"\n[[file:\2][\1]]\n", text)
                text = re.sub(r"\[([^\[\]]+)\]\(([^\(\)]+)\)", r"[[\2][\1]]", text)
                print(text + "\n", file=fout)

            LOGGER.info('saved article "%s" in directory "%s"', title, outdir)

    if out_format == "csv":
        fout.close()
        LOGGER.info("fetched %d articles and saved them in %s", fetched_count, outfile)
    else:
        LOGGER.info("fetched %d articles and saved them in %s", fetched_count, outdir)


@main.command("edit-subscription")
@click.option(
    "-a",
    "--action",
    required=True,
    type=click.Choice(["follow", "unfollow", "rename", "add-folder", "remove-folder"]),
    help="",
)
@click.option("-i", "--stream-id", required=True, help="Stream ID which you want to fetch")
@click.option("-n", "--name", help="The name of subscription, for action follow/rename(required)")
@click.option("-f", "--folder", help="Folder which subscription belong to")
@catch_error
def edit_subscriptions(action, stream_id, name, folder):
    """Get your subscriptions"""
    edit_action = action
    if action in ("rename", "add-folder", "remove-folder"):
        edit_action = "edit"
        if action == "rename" and not name:
            click.secho("`name` is required for action `rename`!", fg="red")
            return -1
        elif action in ("add-folder", "remove_starred") and not folder:
            click.secho(f"`folder` is required for action `{action}`", fg="red")
            return -1

    client = get_client()
    stream_id = "feed/" + stream_id if not stream_id.startswith("feed/") else stream_id
    if folder and not folder.startswith("user/-/label/"):
        folder = client.GENERAL_TAG_TEMPLATE.format(folder)

    add_folder = folder if action in ("follow", "add-folder") else None
    remove_folder = folder if action == "remove-folder" else None
    try:
        response = client.edit_subscription(
            stream_id, edit_action, title=name, add_folder=add_folder, remove_folder=remove_folder
        )
        click.secho(response, fg="green")
    except Exception as exception:
        print("Error:", str(exception))
        return -1


if __name__ == "__main__":
    main()
