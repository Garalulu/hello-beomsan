# Song Tournament - Development Commands

.PHONY: help install dev run test clean lint format migrate shell deploy

help:  ## Show this help message
	@echo "Song Tournament Development Commands"
	@echo "====================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	uv pip install -r requirements.txt

dev:  ## Install development dependencies
	uv pip install -r requirements.txt -r requirements-dev.txt

run:  ## Run development server
	python manage.py runserver

test:  ## Run tests
	pytest

test-cov:  ## Run tests with coverage
	pytest --cov=. --cov-report=html --cov-report=term-missing

lint:  ## Run linting (flake8)
	flake8 .

format:  ## Format code with black and isort
	black .
	isort .

format-check:  ## Check if code needs formatting
	black --check .
	isort --check-only .

migrate:  ## Run database migrations
	python manage.py makemigrations
	python manage.py migrate

shell:  ## Open Django shell
	python manage.py shell

admin:  ## Promote admin user
	python manage.py promote_admin

collectstatic:  ## Collect static files
	python manage.py collectstatic --noinput

clean:  ## Clean up cache and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage

deploy:  ## Deploy to production (via git push)
	git push origin master

logs:  ## View production logs
	fly logs --app hello-beomsan

ssh:  ## SSH into production machine
	fly ssh console --app hello-beomsan

status:  ## Check production app status
	fly status --app hello-beomsan