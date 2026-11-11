PY := ./.venv/bin/python

.PHONY: help setup build serve drafts clean post page

help:
	@echo "make setup   - create .venv and install deps"
	@echo "make serve   - build + serve on http://localhost:8000 with auto-rebuild"
	@echo "make drafts  - same as serve, but includes draft posts"
	@echo "make build   - one-off build into dist/"
	@echo "make clean   - rebuild dist/ from scratch"
	@echo 'make post t="My title"  - scaffold a new post'
	@echo 'make page t="About"     - scaffold a new page'

setup:
	python3 -m venv .venv && $(PY) -m pip -q install -r requirements.txt

build:
	$(PY) build.py

clean:
	$(PY) build.py --clean

serve:
	$(PY) serve.py

drafts:
	$(PY) serve.py --drafts

post:
	$(PY) new_post.py "$(t)"

page:
	$(PY) new_post.py "$(t)" --page
