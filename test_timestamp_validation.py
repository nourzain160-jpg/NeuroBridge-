"""Validate timestamp values, ordering, and duplicates in a NeuroBridge CSV."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def validate_timestamps(file_path, column="Time"):
    file_path = Path(file_path)
    result = {
        "status": "FAIL",
        "total_records": 0,
        "missing_or_non_numeric": 0,
        "non_finite": 0,
        "duplicates": 0,
        "out_of_order": 0,
        "equal_consecutive": 0,
        "errors": [],
    }

    if not file_path.is_file():
        result["errors"].append(f"Input file not found: {file_path}")
        return result

    try:
        df = pd.read_csv(file_path)
    except Exception as exc:
        result["errors"].append(f"Could not read CSV: {type(exc).__name__}: {exc}")
        return result

    result["total_records"] = len(df)
    if column not in df.columns:
        result["errors"].append(f"{column} column is missing.")
        return result

    raw = df[column]
    numeric = pd.to_numeric(raw, errors="coerce")
    result["missing_or_non_numeric"] = int((raw.isna() | numeric.isna()).sum())

    valid_numeric = numeric[numeric.notna()]
    if not valid_numeric.empty:
        finite_mask = np.isfinite(valid_numeric.to_numpy(dtype=float))
        result["non_finite"] = int((~finite_mask).sum())
        finite_values = valid_numeric[finite_mask].to_numpy(dtype=float)
    else:
        finite_values = np.array([], dtype=float)

    if finite_values.size > 1:
        differences = np.diff(finite_values)
        result["duplicates"] = int(pd.Series(finite_values).duplicated().sum())
        result["out_of_order"] = int((differences < 0).sum())
        result["equal_consecutive"] = int((differences == 0).sum())
    elif finite_values.size == 1:
        result["duplicates"] = 0

    if result["missing_or_non_numeric"] or result["non_finite"] or result["out_of_order"]:
        result["status"] = "FAIL"
    elif result["duplicates"]:
        result["status"] = "REVIEW"
    else:
        result["status"] = "PASS"

    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="NeuroBridge timestamp validation")
    parser.add_argument("file", type=Path, help="Path to the dataset CSV")
    parser.add_argument("--column", default="Time", help="Timestamp column (default: Time)")
    args = parser.parse_args(argv)

    result = validate_timestamps(args.file, args.column)
    print("Total records:", result["total_records"])
    print("Missing/non-numeric timestamps:", result["missing_or_non_numeric"])
    print("Non-finite timestamps:", result["non_finite"])
    print("Duplicate timestamps:", result["duplicates"])
    print("Out-of-order intervals:", result["out_of_order"])
    print("Equal consecutive timestamps:", result["equal_consecutive"])
    for error in result["errors"]:
        print("ERROR:", error)

    print(f"\n{result['status']}: Timestamp validation {result['status'].lower()}.")
    if result["status"] == "FAIL":
        return 1
    if result["status"] == "REVIEW":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
