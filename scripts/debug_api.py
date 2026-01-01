
import sys
import os
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from serving.oms import LocalOrderManager
from serving.schema import OrderSide

def get_oms() -> LocalOrderManager:
    db_url = os.getenv("DATABASE_URL", "postgresql://crypto_user:crypto@localhost:5432/qlib_crypto")
    print(f"DB URL: {db_url}")
    return LocalOrderManager(db_url)

def test_account():
    print("Testing Account Fetch...")
    oms = get_oms()
    session = oms.Session()
    try:
        account = oms._get_account(session)
        if not account:
            print("Account Not Found")
        else:
            print(f"Found Account: {account.name}, Balance: {account.balance}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_account()
