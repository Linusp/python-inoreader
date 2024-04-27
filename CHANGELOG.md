# CHANGELOG

## v0.7.0

Removed

- Removed `InoreaderClient.get_stream_contents`.

Changed

- Add param `n` to `InoreaderClient.fetch_articles` to reduce the number of API calls, thanks to [tosborne-slalom](https://github.com/tosborne-slalom)
- Supported `--batch-size` option in commands `fetch-articles`/`fetch-unread`/`fetch-starred`

## v0.6.0

Publish to pypi!

## v0.5.0

Added

- New method: `Inoreader.edit_subscription`
- New command `edit-subscription`, now  you can do these with this command:

  - Subscribe a new feed
  - Unsubscribe a subscription
  - Rename a subscription
  - Add a subscription to a folder or remove it from a folder

Thanks to [Robért](https://github.com/rsguhr) for his [advice](https://github.com/Linusp/python-inoreader/issues/25).

## v0.4.6

Added

- New methods:

  - `InoreaderClient.remove_general_label`
  - `InoreaderClient.remove_tag`
  - `InoreaderClient.remove_read`
  - `InoreaderClient.remove_starred`
  - `InoreaderClient.remove_liked`

  thanks to [tianchen zhong](https://github.com/cczhong11)

Changed

- Add param to `inoreader.main.get_client` for customizing the config file path, thanks to [tianchen zhong](https://github.com/cczhong11)
- Command filter supported a new action `unstar`

Fixed

- Fix token in refresh_access_token method, thanks to [Torikova](https://github.com/Torikova)

## v0.4.5

Changed

- Fix `InoreaderClient.__get_stream_contents`, thanks to [BeautyYuYanli](https://github.com/BeautyYuYanli)

## v0.4.4

Changed

- Disable default app id and key due to abusion

## v0.4.3

Fixed

- Fix endless loop bug in `InoreaderClient.fetch_articles`

## v0.4.2

Added

- New functions:

  - `inoreader.utils.download_image`

- New methods:

  - `InoreaderClient.fetch_articles`
  - `InoreaderClient.fetch_starred`

- New command: `fetch-starred`

Changed

- Optimized article content parsing

## v0.4.1

Added

- New config `proxies`

## v0.4.0

Added

- New Class: `InoreaderConfigManager` for config management

Changed

- Use OAuth2.0 authentication instead of user authentication with password
- Optimized code of `InoreaderClient`
- Optimized results of commands

## v0.3.0

Added

- New Class: `Subscription` in `inoreader.subscription`
- New methods:
  - `InoreaderClient.get_subscription_list`
  - `InoreaderClient.get_stream_contents`

- New commands: `get-subscriptions`, `fetch-articles`, `dedupe`


Changed

- Supported new output formats in command `fetch-unread`: `markdown` and `org-mode`
- Changed command `filter`, see `example/rules.example.yaml` for details
- Use `logging` instead of `print` in cli


## v0.2.1

Changed

- Supported new output formats in command `fetch-unread`: `markdown` and `org-mode`
- Changed command `filter`, see `example/rules.example.yaml` for details

## v0.2.0

Added

- New methods:
  - `InoreaderClient.add_tag`
  - `InoreaderClient.mark_as_read`
  - `InoreaderClient.mark_as_starred`
  - `InoreaderClient.mark_as_liked`
  - `InoreaderClient.broadcast`

- New command `filter`

Changed

- add `userid` parameter to init method of `InoreaderClient`
- update command line tool: save `userid` after login and use it in other commands

## v0.1.0

Initialize this project

- Implemented `InoreaderClient` with methods below:
  - `InoreaderClient.get_folders`
  - `InoreaderClient.get_tags`
  - `InoreaderClient.fetch_unread`

- Implemented command line tool with commands below:
  - `login`
  - `list-folders`
  - `list-tags`
  - `fetch-unread`
