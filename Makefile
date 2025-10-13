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
	@echo "  make test-sharded   Run all test shards sequentially"
	@echo "  make test-qlib      Run qlib-heavy tests (models, backtests)"
	@echo "  make test-data      Run data pipeline tests"
	@echo "  make test-monitor   Run process monitor tests"
	@echo "  make test-api       Run API/WebSocket tests"
	@echo "  make test-mcp       Run MCP tests"
	@echo "  make test-e2e       Run integration/E2E tests"
	@echo "  make test-misc      Run miscellaneous tests"
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

# Sharded test execution to avoid CLI harness timeouts
test-qlib:
	@echo "Running qlib-heavy tests..."
	SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/test_backtest_costs.py tests/test_models.py tests/test_full_pipeline.py tests/test_qlib_debug.py tests/test_concurrent_qlib_init.py -v

test-data:
	@echo "Running data pipeline tests..."
	SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/test_data_pipeline.py tests/test_data_pipeline_validation.py tests/test_data_refresh.py tests/test_chunked_converter.py tests/test_investment_kpis.py -v

test-monitor:
	@echo "Running process monitor tests..."
	SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/test_process_monitor_api.py tests/test_process_monitor_comprehensive.py tests/test_process_monitor_edge_cases.py tests/test_process_monitor_integration.py tests/test_process_monitor_workflows.py tests/test_e2e_process_monitor.py -v

test-api:
	@echo "Running API/WebSocket tests..."
	SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/test_api_endpoints.py tests/test_api_validation.py tests/test_api.py tests/test_websocket_auth.py tests/test_websocket_edge_cases.py tests/test_websocket_ping_pong.py tests/test_websockets.py -v

test-mcp:
	@echo "Running MCP tests..."
	SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/test_mcp*.py -v

test-e2e:
	@echo "Running integration/E2E tests..."
	SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/test_e2e_workflows.py tests/test_e2e.py tests/test_integration_state_bleed.py tests/test_integration_workflows.py tests/test_state_bleed_direct.py tests/test_state_bleed_fix.py tests/test_state_persistence.py -v

test-misc:
	@echo "Running miscellaneous tests..."
	SETUPTOOLS_SCM_PRETEND_VERSION=0.9.8 venv/bin/python -m pytest tests/test_device_management.py tests/test_path_traversal_security.py tests/test_performance_optimizations.py tests/test_task_cancellation_fix.py tests/test_ux_improvements.py tests/comprehensive_test.py -v

test-sharded: test-data test-qlib test-monitor test-api test-mcp test-e2e test-misc
	@echo ""
	@echo "===================================="
	@echo "All sharded tests completed!"
	@echo "===================================="

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
