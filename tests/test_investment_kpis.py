import json

import pytest

from src.analytics.investment_kpis import InvestmentKPIRegistry
from src.models.trainer import _extract_training_kpis


def test_investment_kpi_registry_pass_fail(tmp_path):
    target_file = tmp_path / "targets.json"
    log_file = tmp_path / "log.jsonl"
    latest_file = tmp_path / "latest.json"

    with target_file.open("w") as handle:
        json.dump(
            {
                "backtest": {
                    "metrics": {
                        "sharpe_ratio": {"min": 1.0},
                        "max_drawdown": {"max": 0.2},
                    }
                }
            },
            handle,
        )

    registry = InvestmentKPIRegistry(target_file, log_file, latest_file)

    evaluation = registry.record(
        "backtest",
        {"model_id": "model-1"},
        {"sharpe_ratio": 1.4, "max_drawdown": 0.15},
    )

    assert evaluation.passed is True
    assert evaluation.breaches == []

    # Should write a single JSON line to log file
    log_lines = log_file.read_text().strip().splitlines()
    assert len(log_lines) == 1

    evaluation_fail = registry.record(
        "backtest",
        {"model_id": "model-2"},
        {"sharpe_ratio": 0.5, "max_drawdown": 0.25},
    )

    assert evaluation_fail.passed is False
    assert any(breach["metric"] == "sharpe_ratio" for breach in evaluation_fail.breaches)


def test_extract_training_kpis_prefers_validation():
    metrics = [
        {"name": "IC", "value": 0.01, "step": "train"},
        {"name": "IC", "value": 0.03, "step": "valid"},
        {"name": "IC_IR", "value": 1.2, "step": "valid"},
        {"name": "loss", "value": 0.015, "step": "valid"},
    ]

    extracted = _extract_training_kpis(metrics)

    assert pytest.approx(extracted["ic"], rel=1e-6) == 0.03
    assert pytest.approx(extracted["ic_ir"], rel=1e-6) == 1.2
    assert pytest.approx(extracted["loss"], rel=1e-6) == 0.015
