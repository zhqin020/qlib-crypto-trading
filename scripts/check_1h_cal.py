
import qlib
from qlib.data import D
import os

os.environ['SETUPTOOLS_SCM_PRETEND_VERSION'] = '0.9.8'

def check():
    qlib.init(provider_uri='/home/watson/work/qlib-crypto/data/qlib/crypto_1h')
    print("1h (60min) Calendar samples:")
    try:
        cal = D.calendar(freq='60min')
        print(f"Total points: {len(cal)}")
        print(cal[:5])
        print(cal[-5:])
    except Exception as e:
        print(f"Error loading 60min calendar: {e}")

if __name__ == "__main__":
    check()
