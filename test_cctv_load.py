import pandas as pd
from safety_algorithms import load_public_data

try:
    data = load_public_data("CCTV정보_서울특별시.csv")
    print(f"SUCCESS: Loaded {len(data)} records.")
    if len(data) > 0:
        print(f"Sample record: {data[0]}")
except Exception as e:
    print(f"FAILED: {e}")
