"""Investment KPI registry for tracking workflow performance against targets."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TARGET_FILE = PROJECT_ROOT / "config" / "investment_targets.json"
DEFAULT_LOG_DIR = Path(os.getenv("INVESTMENT_KPI_LOG_DIR", PROJECT_ROOT / "logs"))
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "investment_kpis.jsonl"
DEFAULT_LATEST_FILE = DEFAULT_LOG_DIR / "investment_kpis_latest.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logger.warning("Investment KPI target file missing at %s", path)
        return {}
    try:
        with open(path) as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        logger.error("Failed to parse %s: %s", path, exc)
        return {}


@dataclass
class EvaluationResult:
    """Result of comparing metrics to a stage's targets."""

    stage: str
    passed: bool
    breaches: List[Dict[str, Any]]
    evaluated_metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage,
            "passed": self.passed,
            "breaches": self.breaches,
            "metrics": self.evaluated_metrics,
        }


class InvestmentKPIRegistry:
    """Central store for investment KPI evaluations."""

    def __init__(
        self,
        targets_path: Path = DEFAULT_TARGET_FILE,
        log_file: Path = DEFAULT_LOG_FILE,
        latest_file: Path = DEFAULT_LATEST_FILE,
    ) -> None:
        self._targets_path = targets_path
        self._log_file = log_file
        self._latest_file = latest_file
        self._targets_cache: Optional[Dict[str, Any]] = None

        # Ensure log directory exists
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

    @property
    def targets(self) -> Dict[str, Any]:
        if self._targets_cache is None:
            self._targets_cache = _load_json(self._targets_path)
        return self._targets_cache

    def reload_targets(self) -> None:
        """Force reload of target configuration."""
        self._targets_cache = _load_json(self._targets_path)

    # Public API -----------------------------------------------------------------
    def evaluate(self, stage: str, metrics: Dict[str, Any]) -> EvaluationResult:
        stage_targets = self.targets.get(stage, {}).get("metrics", {})
        breaches: List[Dict[str, Any]] = []

        for metric_name, rules in stage_targets.items():
            if metric_name not in metrics or metrics[metric_name] is None:
                breaches.append(
                    {
                        "metric": metric_name,
                        "reason": "missing",
                        "expected": rules,
                        "actual": None,
                    }
                )
                continue

            value = metrics[metric_name]
            failed = False
            if "min" in rules and value < rules["min"]:
                failed = True
            if "max" in rules and value > rules["max"]:
                failed = True

            if failed:
                breaches.append(
                    {
                        "metric": metric_name,
                        "reason": "threshold",
                        "expected": rules,
                        "actual": value,
                    }
                )

        passed = not breaches
        return EvaluationResult(stage=stage, passed=passed, breaches=breaches, evaluated_metrics=metrics)

    def record(
        self,
        stage: str,
        run_metadata: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate metrics and persist the run."""
        evaluation = self.evaluate(stage, metrics)
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "stage": stage,
            "passed": evaluation.passed,
            "breaches": evaluation.breaches,
            "metrics": evaluation.evaluated_metrics,
            "metadata": run_metadata,
        }

        try:
            with open(self._log_file, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, default=str) + "\n")
            with open(self._latest_file, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, default=str)
        except OSError as exc:  # pragma: no cover - disk failures
            logger.error("Failed to persist KPI entry: %s", exc)

        if evaluation.breaches:
            logger.warning(
                "Investment KPI check failed for stage %s: %s",
                stage,
                evaluation.breaches,
            )
        else:
            logger.info("Investment KPI check passed for stage %s", stage)

        return evaluation


# Shared instance for application modules
kpi_registry = InvestmentKPIRegistry()
