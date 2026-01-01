
import logging
from serving.oms import LocalOrderManager
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL", "postgresql://crypto_user:crypto@localhost:5432/qlib_crypto")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestOMSShort")

def test_oms_short():
    oms = LocalOrderManager(DB_URL)
    
    # 1. Market Price
    prices = {"ETH/USDT": 3000.0}
    
    # 2. Open SHORT (Weight -50%)
    logger.info("--- Step 1: Open Short ETH ---")
    targets = {"ETH/USDT": -0.5}
    oms.execute_rebalance(targets, prices)
    
    # Check if we have negative position
    # (Assuming we run this fresh or clean DB, but let's just see logs)
    
    # 3. Market Drop (Profit for Short)
    prices["ETH/USDT"] = 2800.0 # Drop 200
    
    # 4. Close Short (Weight 0)
    logger.info("--- Step 2: Close Short ETH ---")
    targets_2 = {"ETH/USDT": 0.0}
    oms.execute_rebalance(targets_2, prices)
    
    # Expected: Realized PnL should be positive.
    # Entry ~3000. Exit ~2800.
    # Profit = (2997 - 2802) * qty... roughly +200 per ETH.

if __name__ == "__main__":
    test_oms_short()
