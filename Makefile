lint: clean
	flake8 inoreader --format=pylint || true

clean:
	- find . -iname "*__pycache__" | xargs rm -rf
	- find . -iname "*.pyc" | xargs rm -rf
	- rm cobertura.xml -f
	- rm testresult.xml -f
	- rm .coverage -f

venv:
	- virtualenv --python=$(shell which python3) --prompt '<venv:inoreader>' venv

deps: venv
	- venv/bin/pip install -U pip setuptools
	- venv/bin/pip install -r requirements.txt
