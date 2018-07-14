# CHANGELOG

## v0.2.0

Added

- New methods:
  - `InoreaderClient.add_tag`
  - `InoreaderClient.mark_as_read`
  - `InoreaderClient.mark_as_starred`
  - `InoreaderClient.mark_as_liked`
  - `InoreaderClient.boradcast`

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
