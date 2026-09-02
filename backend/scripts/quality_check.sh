#!/bin/bash
# Quality check script for Falcon backend
# Runs linting, formatting, and type checking

set -e

echo "Running quality checks..."

echo "1. Running Black formatter..."
black --check app/ tests/

echo "2. Running isort..."
isort --check-only app/ tests/

echo "3. Running flake8 linter..."
flake8 app/ tests/

echo "4. Running mypy type checker..."
mypy app/

echo "5. Running pytest..."
pytest tests/ -v

echo "All quality checks passed!"