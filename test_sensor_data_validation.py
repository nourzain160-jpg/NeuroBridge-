"""Validate the structure and numeric contents of a NeuroBridge EEG CSV."""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

EEG_CHANNELS = [
    "F3", "Fz", "FC3", "FC1", "C5", "C3", "CP3", "CP1",
    "P3", "Pz", "PO3", "O1", "P4", "PO4", "Oz", "O2",
    "C4", "C6", "CP2", "CP4", "C1", "Cz", "C2", "CPz",
    "F4", "FCz", "FC2", "FC4",
]
EOG_CHANNELS = ["EOG1", "EOG2", "EOG3", "EOG4"]
ACC_CHANNELS = ["AccX", "AccY", "AccZ"]
REQUIRED = ["Time"] + EEG_CHANNELS + EOG_CHANNELS + ACC_CHANNELS + ["Class"]
VALID_CLASSES = {-1, 0, 1, 2}


def validate_sensor_data(file_path):
    file_path = Path(file_path)
    errors = []

    if not file_path.is_file():
        return [f"Input file not found: {file_path}"]

    try:
        df = pd.read_csv(file_path)
    except Exception as exc:
        return [f"Could not read CSV: {type(exc).__name__}: {exc}"]

    if df.empty:
        return ["Dataset contains no records."]

    missing_columns = [column for column in REQUIRED if column not in df.columns]
    if missing_columns:
        return [f"Missing columns: {missing_columns}"]

    for column in REQUIRED:
        raw = df[column]
        numeric = pd.to_numeric(raw, errors="coerce")

        missing_or_non_numeric = raw.isna() | numeric.isna()
        missing_count = int(missing_or_non_numeric.sum())
        if missing_count:
            errors.append(
                f"{column}: {missing_count} missing or non-numeric value(s)."
            )

        # Check finite values independently; do not hide Inf/-Inf when NaNs exist.
        finite_candidates = numeric[numeric.notna()]
        if not finite_candidates.empty:
            finite_mask = np.isfinite(finite_candidates.to_numpy(dtype=float))
            non_finite_count = int((~finite_mask).sum())
            if non_finite_count:
                errors.append(
                    f"{column}: {non_finite_count} non-finite value(s) detected."
                )

    class_values = pd.to_numeric(df["Class"], errors="coerce")
    valid_class_values = class_values.dropna()
    unexpected = sorted(set(valid_class_values.unique()) - VALID_CLASSES)
    if unexpected:
        errors.append(f"Unexpected class labels: {unexpected}")

    print("Rows:", len(df))
    print("Columns:", len(df.columns))
    print("EEG channels:", len(EEG_CHANNELS))
    print("EOG channels:", len(EOG_CHANNELS))
    print("Accelerometer channels:", len(ACC_CHANNELS))
    print("Valid class labels found:", sorted(valid_class_values.unique().tolist()))

    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="NeuroBridge sensor CSV validation")
    parser.add_argument("file", type=Path, help="Path to the EEG CSV file")
    args = parser.parse_args(argv)

    errors = validate_sensor_data(args.file)
    if errors:
        print("\nFAIL: Sensor data validation found issues.")
        for error in errors:
            print("-", error)
        return 1

    print("\nPASS: Sensor data validation successful.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
