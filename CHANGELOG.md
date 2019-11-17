# CHANGELOG


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
