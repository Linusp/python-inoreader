lint: clean
	- pip install ruff codespell -q
	- ruff check inoreader/
	- codespell

format:
	- pip install ruff -q
	- ruff format inoreader/

clean:
	- find . -iname "*__pycache__" | xargs rm -rf
	- find . -iname "*.pyc" | xargs rm -rf
	- rm cobertura.xml -f
	- rm testresult.xml -f
	- rm .coverage -f
	- rm .pytest_cache -rf

venv:
	- virtualenv --python=$(shell which python3) --prompt '<venv:inoreader>' venv

deps:
	- pip install -U pip setuptools
	- pip install -r requirements.txt
