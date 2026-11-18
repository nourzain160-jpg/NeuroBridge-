
import pandas as pd
import numpy as np

FILE = "/content/Dataset/S01/S01_EEG_01.csv"

def validate_timestamps(file_path):
    df = pd.read_csv(file_path)

    if "Time" not in df.columns:
        print("FAIL: Time column is missing.")
        return

    time = pd.to_numeric(df["Time"], errors="coerce")

    missing = int(time.isna().sum())
    non_finite = int((~np.isfinite(time.dropna())).sum())

    valid_time = time.dropna()
    differences = valid_time.diff().dropna()

    duplicates = int(valid_time.duplicated().sum())
    out_of_order = int((differences < 0).sum())
    equal_intervals = int((differences == 0).sum())

    print("Total records:", len(df))
    print("Missing/non-numeric timestamps:", missing)
    print("Non-finite timestamps:", non_finite)
    print("Duplicate timestamps:", duplicates)
    print("Out-of-order intervals:", out_of_order)
    print("Equal consecutive timestamps:", equal_intervals)

    if missing or non_finite or out_of_order:
        print("\nFAIL: Invalid timestamp values or ordering detected.")
    elif duplicates:
        print("\nREVIEW: Timestamps are ordered but contain duplicates.")
    else:
        print("\nPASS: Timestamps are valid and strictly increasing.")


if __name__ == "__main__":
    validate_timestamps(FILE)
