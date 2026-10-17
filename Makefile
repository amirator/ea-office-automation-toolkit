# EA Office Automation Toolkit. Run `make help` for targets.
VENV   ?= .venv
PYTHON := $(VENV)/bin/python

.PHONY: help venv demo test screenshots clean

help:
	@echo "make venv         create .venv and install pinned dependencies"
	@echo "make demo         run all three tools on the bundled SAMPLE data -> outputs/"
	@echo "make test         run the pytest suite"
	@echo "make screenshots  render PNGs of the real outputs into docs/ (needs LibreOffice + poppler)"
	@echo "make clean        remove outputs/ and caches"

$(PYTHON):
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip -q
	$(VENV)/bin/pip install -q -r requirements-dev.txt -c constraints.txt

venv: $(PYTHON)

demo: $(PYTHON)
	$(PYTHON) -m toolkit demo

test: $(PYTHON)
	$(PYTHON) -m pytest -q

screenshots: demo
	$(PYTHON) scripts/make_screenshots.py

clean:
	rm -rf outputs .pytest_cache **/__pycache__
