.PHONY: install dev run seed test lint fmt clean

install:        ## runtime deps
	pip install -r requirements.txt

dev:            ## runtime + dev deps
	pip install -r requirements-dev.txt

run:            ## launch the terminal
	streamlit run streamlit_app.py

seed:           ## regenerate the offline sample snapshot
	python scripts/seed_samples.py

test:           ## engine golden-masters + page smoke tests (offline)
	DATA_MODE=demo pytest -q

lint:           ## ruff check
	ruff check .

fmt:            ## ruff autofix (imports, simple fixes)
	ruff check --fix .

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache
