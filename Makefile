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

lock-requirements:
	- pip install pip-tools -q
	- pip-compile -o requirements.txt

deps: lock-requirements
	- pip-sync

build: lint test
	- python -m build
