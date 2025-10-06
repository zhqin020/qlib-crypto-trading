# Makefile for Qlib Crypto Trading Platform

.PHONY: help install setup download-data convert train test clean docker-up docker-down api mcp

help:
	@echo "Qlib Crypto Trading Platform - Make Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install Python dependencies"
	@echo "  make setup          Create directory structure"
	@echo ""
	@echo "Data Pipeline:"
	@echo "  make download-data  Download sample crypto data"
	@echo "  make convert        Convert CSV to Qlib format"
	@echo ""
	@echo "Training:"
	@echo "  make train          Train sample model"
	@echo ""
	@echo "Services:"
	@echo "  make api            Start REST API server"
	@echo "  make api-live       Start enhanced API with real-time UI"
	@echo "  make mcp            Start MCP server"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up      Start all services with Docker"
	@echo "  make docker-down    Stop all Docker services"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run test suite"
	@echo "  make test-cov       Run tests with coverage"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          Clean generated files"
	@echo "  make clean-all      Clean everything including data"

install:
	pip install -r requirements.txt

setup:
	mkdir -p data/{raw,qlib,processed}
	mkdir -p models/trained
	mkdir -p backtests predictions experiments schedules logs
	mkdir -p config/features
	@echo "Directory structure created"

download-data:
	python scripts/download_sample_data.py

convert:
	python scripts/convert_to_qlib.py

train:
	python scripts/train_sample_model.py

api:
	./scripts/start_server.sh

api-live:
	./scripts/start_server_enhanced.sh

mcp:
	./scripts/start_mcp_server.sh

docker-up:
	docker-compose up -d
	@echo "Services started. Access:"
	@echo "  API: http://localhost:5100"
	@echo "  Docs: http://localhost:5100/docs"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
	@echo "Cleaned Python cache files"

clean-all: clean
	rm -rf data/raw/* data/qlib/* data/processed/*
	rm -rf models/trained/* backtests/* predictions/* experiments/*
	rm -rf logs/*
	@echo "Cleaned all data and outputs"

format:
	black src/ tests/ scripts/
	@echo "Code formatted"

lint:
	flake8 src/ tests/
	mypy src/
	@echo "Linting complete"

.DEFAULT_GOAL := help
