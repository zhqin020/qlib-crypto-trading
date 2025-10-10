"""Pytest fixtures and shared test configuration."""
from __future__ import annotations

import os

os.environ.setdefault("SETUPTOOLS_SCM_PRETEND_VERSION", "0.9.8")

import pytest

from src.utils.torch_stub import ensure_torch_available

# Ensure optional torch dependency can be patched in unit tests without
# requiring the heavy PyTorch installation in CI/local environments.
ensure_torch_available()


@pytest.fixture(scope="module")
def report(request):
    """Provide the integration TestReport helper expected by legacy suites."""
    from tests.test_integration_workflows import TestReport

    integration_report = TestReport()
    yield integration_report
    # Emit the formatted summary so debugging remains intact for humans.
    integration_report.print_report()
