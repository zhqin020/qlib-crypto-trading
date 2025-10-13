#!/usr/bin/env python
"""
Collect and analyze KPI data from historical backtests.

This script runs multiple backtests across different time periods, market regimes,
and asset classes to build a statistical distribution of performance metrics.
The results are used to refine KPI targets from industry baselines to data-driven thresholds.

Usage:
    python scripts/collect_kpi_data.py --start-date 2020-01-01 --end-date 2024-12-31 --min-backtests 50
    python scripts/collect_kpi_data.py --analyze  # Analyze existing backtest results
"""

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class KPIDataCollector:
    """Collect and analyze KPI data from backtests."""

    def __init__(self, backtest_dir: Path = None):
        self.backtest_dir = backtest_dir or PROJECT_ROOT / "backtests"
        self.output_dir = PROJECT_ROOT / "analytics" / "kpi_analysis"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def collect_existing_results(self) -> List[Dict[str, Any]]:
        """Collect metrics from existing backtest JSON files."""
        results = []

        if not self.backtest_dir.exists():
            logger.warning(f"Backtest directory not found: {self.backtest_dir}")
            return results

        for backtest_file in self.backtest_dir.glob("*.json"):
            try:
                with open(backtest_file) as f:
                    data = json.load(f)

                # Extract relevant metrics
                if "metrics" in data:
                    result = {
                        "model_id": data.get("model_id", "unknown"),
                        "dataset": data.get("dataset", "unknown"),
                        "backtest_file": backtest_file.name,
                        "metrics": data["metrics"],
                        "config": data.get("config", {}),
                        "backtest_period": data.get("backtest_period", {})
                    }
                    results.append(result)
                    logger.info(f"Loaded: {backtest_file.name}")
            except Exception as e:
                logger.error(f"Failed to load {backtest_file}: {e}")

        logger.info(f"Collected {len(results)} backtest results")
        return results

    def calculate_percentiles(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """Calculate percentile distributions for each metric."""
        import numpy as np

        # Collect all metrics
        metric_values: Dict[str, List[float]] = {}

        for result in results:
            for metric, value in result["metrics"].items():
                if isinstance(value, (int, float)) and not np.isnan(value) and not np.isinf(value):
                    if metric not in metric_values:
                        metric_values[metric] = []
                    metric_values[metric].append(value)

        # Calculate percentiles
        percentiles = {}
        for metric, values in metric_values.items():
            if len(values) < 2:
                logger.warning(f"Insufficient data for {metric}: {len(values)} values")
                continue

            percentiles[metric] = {
                "count": len(values),
                "min": float(np.min(values)),
                "10th": float(np.percentile(values, 10)),
                "25th": float(np.percentile(values, 25)),
                "50th": float(np.percentile(values, 50)),  # median
                "75th": float(np.percentile(values, 75)),
                "90th": float(np.percentile(values, 90)),
                "max": float(np.max(values)),
                "mean": float(np.mean(values)),
                "std": float(np.std(values))
            }

        return percentiles

    def generate_target_recommendations(self, percentiles: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """Generate recommended targets based on percentile distributions."""
        recommendations = {}

        # Sharpe Ratio
        if "sharpe_ratio" in percentiles:
            p = percentiles["sharpe_ratio"]
            recommendations["sharpe_ratio"] = {
                "current_target": 1.0,
                "recommended_minimum": round(p["25th"], 2),  # Bottom quarter
                "recommended_deployment": round(p["50th"], 2),  # Median
                "recommended_excellence": round(p["75th"], 2),  # Top quarter
                "data_support": f"{p['count']} backtests"
            }

        # Max Drawdown
        if "max_drawdown" in percentiles:
            p = percentiles["max_drawdown"]
            recommendations["max_drawdown"] = {
                "current_target": 0.20,
                "recommended_maximum": round(p["75th"], 3),  # Allow some room
                "recommended_excellent": round(p["25th"], 3),  # Stricter target
                "data_support": f"{p['count']} backtests"
            }

        # Annualized Return
        if "annualized_return" in percentiles:
            p = percentiles["annualized_return"]
            recommendations["annualized_return"] = {
                "current_target": 0.15,
                "recommended_minimum": round(p["25th"], 3),
                "recommended_deployment": round(p["50th"], 3),
                "recommended_excellence": round(p["75th"], 3),
                "data_support": f"{p['count']} backtests"
            }

        return recommendations

    def analyze_and_report(self):
        """Analyze existing backtest results and generate recommendations."""
        logger.info("=== KPI Data Analysis ===")

        # Collect results
        results = self.collect_existing_results()

        if len(results) < 5:
            logger.warning(f"⚠️  Only {len(results)} backtests found. Minimum 50 recommended for statistical validity.")
            logger.info("Run more backtests to build a robust distribution.")

        # Calculate percentiles
        percentiles = self.calculate_percentiles(results)

        # Generate recommendations
        recommendations = self.generate_target_recommendations(percentiles)

        # Create report
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "sample_size": len(results),
            "status": "sufficient" if len(results) >= 50 else "insufficient",
            "percentile_distributions": percentiles,
            "target_recommendations": recommendations,
            "next_steps": self._get_next_steps(len(results))
        }

        # Save report
        report_file = self.output_dir / f"kpi_analysis_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"✅ Report saved: {report_file}")

        # Print summary
        self._print_summary(report)

        return report

    def _get_next_steps(self, sample_size: int) -> List[str]:
        """Generate next steps based on current sample size."""
        if sample_size < 10:
            return [
                "Run at least 10 backtests to establish initial trends",
                "Vary time periods (2020-2024) to capture different market regimes",
                "Test multiple model types (LightGBM, LSTM, Transformer)"
            ]
        elif sample_size < 50:
            return [
                f"Run {50 - sample_size} more backtests to reach minimum statistical threshold",
                "Ensure coverage of all market regimes (bull, bear, sideways)",
                "Include multiple asset classes (BTC, ETH, altcoins)"
            ]
        else:
            return [
                "✅ Sufficient sample size for target refinement",
                "Update config/investment_targets.json with data-driven thresholds",
                "Validate new targets on out-of-sample period (2025)",
                "Consider asset-specific target stratification"
            ]

    def _print_summary(self, report: Dict[str, Any]):
        """Print human-readable summary of the analysis."""
        print("\n" + "=" * 60)
        print("KPI ANALYSIS SUMMARY")
        print("=" * 60)

        print(f"\nSample Size: {report['sample_size']} backtests")
        print(f"Status: {'✅ Sufficient' if report['status'] == 'sufficient' else '⚠️  Insufficient'}")

        if report["percentile_distributions"]:
            print("\n--- Percentile Distributions ---")
            for metric, dist in report["percentile_distributions"].items():
                print(f"\n{metric}:")
                print(f"  25th: {dist['25th']:.3f}  |  50th: {dist['50th']:.3f}  |  75th: {dist['75th']:.3f}")
                print(f"  Mean: {dist['mean']:.3f} ± {dist['std']:.3f}")

        if report["target_recommendations"]:
            print("\n--- Target Recommendations ---")
            for metric, rec in report["target_recommendations"].items():
                print(f"\n{metric}:")
                print(f"  Current: {rec['current_target']}")
                if "recommended_minimum" in rec:
                    print(f"  Recommended Minimum: {rec['recommended_minimum']}")
                if "recommended_deployment" in rec:
                    print(f"  Recommended Deployment: {rec['recommended_deployment']}")
                if "recommended_maximum" in rec:
                    print(f"  Recommended Maximum: {rec['recommended_maximum']}")

        print("\n--- Next Steps ---")
        for i, step in enumerate(report["next_steps"], 1):
            print(f"{i}. {step}")

        print("\n" + "=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Collect and analyze KPI data from backtests")
    parser.add_argument("--analyze", action="store_true", help="Analyze existing backtest results")
    parser.add_argument("--backtest-dir", type=Path, help="Directory containing backtest JSON files")
    parser.add_argument("--output-dir", type=Path, help="Directory for analysis reports")

    # Future: Add options for running new backtests
    parser.add_argument("--start-date", help="Start date for backtest period (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date for backtest period (YYYY-MM-DD)")
    parser.add_argument("--min-backtests", type=int, default=50, help="Minimum number of backtests to run")

    args = parser.parse_args()

    collector = KPIDataCollector(backtest_dir=args.backtest_dir)

    if args.analyze:
        # Analyze existing results
        collector.analyze_and_report()
    else:
        print("Error: --analyze is currently the only supported mode")
        print("Future: Add support for running new backtests with --start-date, --end-date, --min-backtests")
        sys.exit(1)


if __name__ == "__main__":
    main()
