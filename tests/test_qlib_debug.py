"""
Debug script to understand why Qlib returns empty data
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import pytest

qlib = pytest.importorskip("qlib", reason="qlib not installed")
from qlib.data import D
from qlib.data.data import Cal, Inst
import struct
import tempfile
import shutil

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.qlib_state import init_qlib_clean


def create_test_data():
    """Create minimal test dataset"""
    temp_dir = Path(tempfile.mkdtemp())
    csv_dir = temp_dir / "csv"
    qlib_dir = temp_dir / "qlib"
    csv_dir.mkdir()

    # Create sample CSV
    dates = pd.date_range('2024-01-01', periods=10, freq='D')
    data = {
        'datetime': dates,
        'open': [100.0] * 10,
        'high': [110.0] * 10,
        'low': [90.0] * 10,
        'close': [105.0] * 10,
        'volume': [1000.0] * 10,
    }
    df = pd.DataFrame(data)
    csv_path = csv_dir / "TEST.csv"
    df.to_csv(csv_path, index=False)

    return temp_dir, csv_dir, qlib_dir, df


def convert_and_debug():
    """Convert data and debug each step"""
    from src.data_pipeline.official_qlib_converter import convert_crypto_data_official as convert_crypto_data

    temp_dir, csv_dir, qlib_dir, original_df = create_test_data()

    print("=" * 60)
    print("STEP 1: Convert CSV to Qlib format")
    print("=" * 60)
    result = convert_crypto_data(str(csv_dir), str(qlib_dir), "1d")
    print(f"✓ Conversion result: {result}")

    print("\n" + "=" * 60)
    print("STEP 2: Verify binary file format")
    print("=" * 60)
    bin_file = qlib_dir / "features" / "TEST" / "close.bin"
    with open(bin_file, 'rb') as f:
        version = struct.unpack('B', f.read(1))[0]
        start_index = struct.unpack('I', f.read(4))[0]
        f.seek(0, 2)
        file_size = f.tell()
        data_size = (file_size - 5) // 4

        print(f"✓ Version: {version}")
        print(f"✓ Start index: {start_index}")
        print(f"✓ File size: {file_size} bytes")
        print(f"✓ Data points: {data_size}")

        f.seek(5)
        data = np.fromfile(f, dtype=np.float32)
        print(f"✓ First 5 values: {data[:5]}")
        print(f"✓ All values same (105.0): {np.allclose(data, 105.0)}")

    print("\n" + "=" * 60)
    print("STEP 3: Check calendar")
    print("=" * 60)
    cal_file = qlib_dir / "calendars" / "day.txt"
    with open(cal_file) as f:
        cal_lines = f.readlines()
    print(f"✓ Calendar entries: {len(cal_lines)}")
    print(f"✓ First entry: {cal_lines[0].strip()}")
    print(f"✓ Last entry: {cal_lines[-1].strip()}")

    # Find 2024-01-01 in calendar
    target_date = "2024-01-01"
    for i, line in enumerate(cal_lines):
        if target_date in line:
            print(f"✓ {target_date} found at line {i}")
            break

    print("\n" + "=" * 60)
    print("STEP 4: Check instruments file")
    print("=" * 60)
    inst_file = qlib_dir / "instruments" / "all.txt"
    inst_content = inst_file.read_text()
    print(f"✓ Instruments file content:\n{inst_content}")

    print("\n" + "=" * 60)
    print("STEP 5: Initialize Qlib and check what it sees")
    print("=" * 60)
    success = init_qlib_clean(
        provider_uri={'day': str(qlib_dir)},
        region="cn"
    )
    assert success, "Failed to initialize qlib"

    # Check calendar
    cal = Cal.calendar(freq='day')
    print(f"✓ Qlib calendar entries: {len(cal)}")
    print(f"✓ Qlib calendar range: {cal[0]} to {cal[-1]}")

    target_ts = pd.Timestamp('2024-01-01')
    if target_ts in cal:
        idx = list(cal).index(target_ts)
        print(f"✓ 2024-01-01 is at index {idx} in Qlib calendar")
        print(f"  (Binary start_index was {start_index}, {'MATCH!' if idx == start_index else 'MISMATCH!'})")
    else:
        print("✗ 2024-01-01 NOT in Qlib calendar!")

    # Check instruments
    try:
        all_instruments = Inst.list_instruments(instruments='TEST', freq='day')
        print(f"✓ Qlib sees instrument TEST: {all_instruments}")
    except Exception as e:
        print(f"✗ Error listing instruments: {e}")

    print("\n" + "=" * 60)
    print("STEP 6: Try to read data with Qlib")
    print("=" * 60)

    # Try various approaches
    print("\nAttempt 1: D.features with date range")
    df1 = D.features(['TEST'], ['$close'], start_time='2024-01-01', end_time='2024-01-10')
    print(f"  Result: {len(df1)} rows")
    if len(df1) > 0:
        print(f"  Data: {df1.head()}")

    print("\nAttempt 2: D.features without date range")
    df2 = D.features(['TEST'], ['$close'])
    print(f"  Result: {len(df2)} rows")
    if len(df2) > 0:
        print(f"  Data: {df2.head()}")

    print("\nAttempt 3: Using Ref/Eref expressions")
    try:
        df3 = D.features(['TEST'], ['Ref($close, 0)'], start_time='2024-01-01', end_time='2024-01-10')
        print(f"  Result: {len(df3)} rows")
        if len(df3) > 0:
            print(f"  Data: {df3.head()}")
    except Exception as e:
        print(f"  Error: {e}")

    print("\n" + "=" * 60)
    print("STEP 7: Manual binary read vs Qlib read comparison")
    print("=" * 60)

    # Read binary manually
    with open(bin_file, 'rb') as f:
        f.seek(1)  # Skip version
        start_idx = struct.unpack('I', f.read(4))[0]
        data_manual = np.fromfile(f, dtype=np.float32)

    print(f"Manual read:")
    print(f"  start_index: {start_idx}")
    print(f"  data length: {len(data_manual)}")
    print(f"  data values: {data_manual}")

    print(f"\nQlib read:")
    print(f"  returned rows: {len(df1)}")
    print(f"  Expected: If start_index={start_idx}, data should start at calendar[{start_idx}]")
    print(f"  Calendar[{start_idx}] = {cal[start_idx] if start_idx < len(cal) else 'OUT OF RANGE'}")

    # Cleanup
    shutil.rmtree(temp_dir)

    return start_idx, len(cal), len(df1)


if __name__ == '__main__':
    start_idx, cal_len, result_rows = convert_and_debug()

    print("\n" + "=" * 60)
    print("DIAGNOSIS")
    print("=" * 60)

    if result_rows > 0:
        print("✓ SUCCESS! Qlib can read the data correctly")
    else:
        print("✗ FAILURE! Qlib returns empty data")
        print("\nPossible causes:")
        print(f"  1. start_index ({start_idx}) doesn't match calendar position")
        print(f"  2. Instruments file format incorrect")
        print(f"  3. Calendar provider mismatch")
        print(f"  4. Qlib version incompatibility")
        print("\nRecommended action:")
        print("  Use Qlib's official dump_bin.py script instead of custom converter")
