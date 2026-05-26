.PHONY: install lint format type test cov serve docker clean help

PYTHON ?= python
OUT ?= ./work

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Install package + dev dependencies into the active env.
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

lint: ## Ruff lint.
	ruff check .

format: ## Ruff format in place.
	ruff format .

type: ## Mypy strict.
	mypy

test: ## Run the test suite quietly.
	pytest -q

cov: ## Run tests with branch coverage.
	pytest -q --cov=aerosynthx --cov-branch --cov-report=term-missing

serve: ## Start the local FastAPI server at http://127.0.0.1:8000/.
	aerosynthx serve --out $(OUT)

docker: ## Build the container image as aerosynthx:dev.
	docker build -t aerosynthx:dev .

clean: ## Remove caches and build artefacts.
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
