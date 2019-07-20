Inoreader
=========

![](https://api.travis-ci.org/Linusp/python-inoreader.png?branch=master)

Python wrapper of Inoreader API.

## Installation

1. Clone this repository and install it with `setup.py`

```shell
python setup.py install
```

2. Install with `pip` directly

```shell
pip install git+https://github.com/Linusp/python-inoreader.git
```

## Usage

1. [Register your application](https://www.inoreader.com/developers/register-app)

2. Set `appid` and `appkey` in your system, you can set them with environment variables like

   ```shell
   export INOREADER_APP_ID = 'your-app-id'
   export INOREADER_APP_KEY = 'your-app-key'
   ```

   or write them in `$HOME/.inoreader`, e.g.:
   ```shell
   [auth]
   appid = your-app-id
   appkey = your-app-key
   ```

3. Login to your Inoreader account

   ```shell
   inoreader login
   ```

3. Use the command line tool `inoreader` to do something, run `inoreader --help` for details
