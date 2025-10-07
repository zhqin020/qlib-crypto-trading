"""
Test suite for validating backtest cost model implementation.

Tests that the corrected exchange_kwargs are properly applied and
that costs reduce returns as expected.
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.backtesting.engine import run_backtest, get_exchange_config


class TestExchangeConfig:
    """Test get_exchange_config() returns correct parameters"""

    def test_low_cost_config(self):
        """Test low cost configuration"""
        config = get_exchange_config("low")

        assert config["open_cost"] == 0.0002, "Low open_cost should be 0.02%"
        assert config["close_cost"] == 0.0005, "Low close_cost should be 0.05%"
        assert config["min_cost"] == 0, "Crypto should have no minimum cost"
        assert config["impact_cost"] == 0.00005, "Low impact_cost should be 0.005%"
        assert config["limit_threshold"] is None, "Crypto should have no price limits"
        assert config["deal_price"] == "close"
        assert config["freq"] == "day"

    def test_medium_cost_config(self):
        """Test medium cost configuration"""
        config = get_exchange_config("medium")

        assert config["open_cost"] == 0.0005, "Medium open_cost should be 0.05%"
        assert config["close_cost"] == 0.001, "Medium close_cost should be 0.1%"
        assert config["min_cost"] == 0
        assert config["impact_cost"] == 0.0001, "Medium impact_cost should be 0.01%"

    def test_high_cost_config(self):
        """Test high cost configuration"""
        config = get_exchange_config("high")

        assert config["open_cost"] == 0.001, "High open_cost should be 0.1%"
        assert config["close_cost"] == 0.002, "High close_cost should be 0.2%"
        assert config["min_cost"] == 0
        assert config["impact_cost"] == 0.0005, "High impact_cost should be 0.05%"

    def test_default_cost_level(self):
        """Test that invalid cost level defaults to medium"""
        config = get_exchange_config("invalid_level")
        medium_config = get_exchange_config("medium")

        assert config == medium_config, "Invalid cost level should default to medium"

    def test_no_wrong_parameters(self):
        """Test that old incorrect parameters are NOT present"""
        config = get_exchange_config("medium")

        # These parameters should NOT exist (they were wrong)
        assert "trade_cost" not in config, "trade_cost is not a valid Qlib parameter"
        assert "slippage" not in config, "slippage is not a valid Qlib parameter"
        assert "funding_rate" not in config, "funding_rate is not a valid Qlib parameter"
        assert "trade_exchange" not in config, "trade_exchange should not be nested"

    def test_funding_rate_warning(self, caplog):
        """Test that funding=True logs a warning"""
        import logging
        caplog.set_level(logging.WARNING)

        config = get_exchange_config("medium", funding=True)

        # Should log warning but not add funding_rate to config
        assert "funding rate" in caplog.text.lower()
        assert "not natively supported" in caplog.text.lower()
        assert "funding_rate" not in config

    def test_cost_increases_across_levels(self):
        """Test that costs increase from low -> medium -> high"""
        low = get_exchange_config("low")
        medium = get_exchange_config("medium")
        high = get_exchange_config("high")

        # Open costs should increase
        assert low["open_cost"] < medium["open_cost"] < high["open_cost"]

        # Close costs should increase
        assert low["close_cost"] < medium["close_cost"] < high["close_cost"]

        # Impact costs should increase
        assert low["impact_cost"] < medium["impact_cost"] < high["impact_cost"]


class TestBacktestCostIntegration:
    """Integration tests for backtest cost application"""

    @pytest.fixture
    def model_setup(self):
        """Setup test model and dataset"""
        # This would need a real trained model to run
        # For now, document what needs to exist
        model_id = "test_model_for_costs"
        dataset = "crypto_btc_test"

        return {
            "model_id": model_id,
            "dataset": dataset,
            "exists": False  # Set to True if test model exists
        }

    @pytest.mark.skipif(True, reason="Requires trained model - manual test only")
    @pytest.mark.asyncio
    async def test_cost_impact_on_returns(self, model_setup):
        """Test that higher costs result in lower returns"""
        if not model_setup["exists"]:
            pytest.skip("Test model not available")

        # Run backtest with different cost levels
        result_low = await run_backtest(
            model_id=model_setup["model_id"],
            dataset_ref=model_setup["dataset"],
            costs="low",
            rebalance="weekly",
            funding=False
        )

        result_medium = await run_backtest(
            model_id=model_setup["model_id"],
            dataset_ref=model_setup["dataset"],
            costs="medium",
            rebalance="weekly",
            funding=False
        )

        result_high = await run_backtest(
            model_id=model_setup["model_id"],
            dataset_ref=model_setup["dataset"],
            costs="high",
            rebalance="weekly",
            funding=False
        )

        # Extract returns
        return_low = result_low["metrics"]["annualized_return"]
        return_medium = result_medium["metrics"]["annualized_return"]
        return_high = result_high["metrics"]["annualized_return"]

        # Verify returns decrease with higher costs
        assert return_low > return_medium > return_high, \
            f"Returns should decrease with higher costs: low={return_low}, med={return_medium}, high={return_high}"

        # Verify cost impact is realistic (not too small, not too large)
        cost_impact_med = return_low - return_medium
        cost_impact_high = return_low - return_high

        assert 0.01 < cost_impact_med < 0.15, \
            f"Medium cost impact should be 1-15%: {cost_impact_med:.3%}"
        assert 0.03 < cost_impact_high < 0.25, \
            f"High cost impact should be 3-25%: {cost_impact_high:.3%}"

    @pytest.mark.skipif(True, reason="Requires trained model - manual test only")
    @pytest.mark.asyncio
    async def test_portfolio_metrics_divergence(self, model_setup):
        """Test that with_cost and without_cost metrics diverge"""
        if not model_setup["exists"]:
            pytest.skip("Test model not available")

        result = await run_backtest(
            model_id=model_setup["model_id"],
            dataset_ref=model_setup["dataset"],
            costs="medium",
            rebalance="weekly",
            funding=False
        )

        # Check portfolio curve exists
        assert "portfolio_curve" in result
        portfolio_curve = result["portfolio_curve"]

        # Should have both with and without cost metrics
        # Note: The exact key names depend on Qlib's output
        # This test documents the expected behavior
        assert len(portfolio_curve) > 0, "Portfolio curve should not be empty"

        # The curve should show the impact of costs over time
        # Final return with costs should be lower than without costs


class TestCostRealism:
    """Test that cost values are realistic for crypto trading"""

    def test_cost_rates_within_realistic_bounds(self):
        """Test that all cost rates are realistic for crypto"""
        configs = {
            "low": get_exchange_config("low"),
            "medium": get_exchange_config("medium"),
            "high": get_exchange_config("high"),
        }

        for level, config in configs.items():
            # Open/close costs should be between 0.01% and 0.5%
            assert 0.0001 <= config["open_cost"] <= 0.005, \
                f"{level} open_cost out of realistic range: {config['open_cost']}"
            assert 0.0001 <= config["close_cost"] <= 0.005, \
                f"{level} close_cost out of realistic range: {config['close_cost']}"

            # Impact cost should be small (0.001% to 0.1%)
            assert 0.00001 <= config["impact_cost"] <= 0.001, \
                f"{level} impact_cost out of realistic range: {config['impact_cost']}"

            # Total round-trip cost should be less than 1%
            round_trip_cost = config["open_cost"] + config["close_cost"] + config["impact_cost"]
            assert round_trip_cost < 0.01, \
                f"{level} total round-trip cost too high: {round_trip_cost:.4%}"

    def test_vip_vs_standard_fees(self):
        """Test that VIP (low) fees are lower than standard (medium)"""
        low = get_exchange_config("low")
        medium = get_exchange_config("medium")

        # Low should represent VIP tier with maker-taker spread
        assert low["open_cost"] < low["close_cost"], \
            "Maker fees (open) should be lower than taker fees (close)"

        # VIP fees should be significantly lower than standard
        vip_total = low["open_cost"] + low["close_cost"]
        standard_total = medium["open_cost"] + medium["close_cost"]

        # VIP should be at least 40% cheaper
        assert vip_total < standard_total * 0.6, \
            f"VIP fees should be significantly lower than standard"


def test_documentation_completeness():
    """Test that get_exchange_config has complete documentation"""
    import inspect

    func = get_exchange_config
    doc = inspect.getdoc(func)

    assert doc is not None, "Function should have documentation"
    assert "open_cost" in doc, "Should document open_cost parameter"
    assert "close_cost" in doc, "Should document close_cost parameter"
    assert "min_cost" in doc, "Should document min_cost parameter"
    assert "impact_cost" in doc, "Should document impact_cost parameter"
    assert "exchange_kwargs" in doc, "Should mention exchange_kwargs usage"

    # Verify function signature
    sig = inspect.signature(func)
    assert "costs" in sig.parameters
    assert "funding" in sig.parameters
    assert sig.parameters["funding"].default is False


if __name__ == "__main__":
    print("=" * 60)
    print("Backtest Cost Model Test Suite")
    print("=" * 60)
    print()

    # Run basic config tests
    print("Testing exchange configuration...")
    test = TestExchangeConfig()

    try:
        test.test_low_cost_config()
        print("✓ Low cost config correct")
    except AssertionError as e:
        print(f"✗ Low cost config failed: {e}")

    try:
        test.test_medium_cost_config()
        print("✓ Medium cost config correct")
    except AssertionError as e:
        print(f"✗ Medium cost config failed: {e}")

    try:
        test.test_high_cost_config()
        print("✓ High cost config correct")
    except AssertionError as e:
        print(f"✗ High cost config failed: {e}")

    try:
        test.test_no_wrong_parameters()
        print("✓ No incorrect parameters present")
    except AssertionError as e:
        print(f"✗ Incorrect parameters found: {e}")

    try:
        test.test_cost_increases_across_levels()
        print("✓ Costs increase across levels correctly")
    except AssertionError as e:
        print(f"✗ Cost progression failed: {e}")

    print()
    print("Testing cost realism...")
    realism = TestCostRealism()

    try:
        realism.test_cost_rates_within_realistic_bounds()
        print("✓ All cost rates are realistic")
    except AssertionError as e:
        print(f"✗ Cost realism check failed: {e}")

    try:
        realism.test_vip_vs_standard_fees()
        print("✓ VIP fees correctly lower than standard")
    except AssertionError as e:
        print(f"✗ VIP fee structure failed: {e}")

    try:
        test_documentation_completeness()
        print("✓ Documentation is complete")
    except AssertionError as e:
        print(f"✗ Documentation incomplete: {e}")

    print()
    print("=" * 60)
    print("Unit tests complete!")
    print()
    print("NOTE: Integration tests require a trained model.")
    print("To run full test suite with pytest:")
    print("  pytest tests/test_backtest_costs.py -v")
    print("=" * 60)
