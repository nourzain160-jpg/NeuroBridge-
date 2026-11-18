
import pandas as pd
import numpy as np
import sys

FILE = "/content/Dataset/S01/S01_EEG_01.csv"

EEG_CHANNELS = [
    "F3", "Fz", "FC3", "FC1", "C5", "C3", "CP3", "CP1",
    "P3", "Pz", "PO3", "O1", "P4", "PO4", "Oz", "O2",
    "C4", "C6", "CP2", "CP4", "C1", "Cz", "C2", "CPz",
    "F4", "FCz", "FC2", "FC4"
]

EOG_CHANNELS = ["EOG1", "EOG2", "EOG3", "EOG4"]
ACC_CHANNELS = ["AccX", "AccY", "AccZ"]
REQUIRED = ["Time"] + EEG_CHANNELS + EOG_CHANNELS + ACC_CHANNELS + ["Class"]
VALID_CLASSES = {-1, 0, 1, 2}

def validate_sensor_data(file_path):
    df = pd.read_csv(file_path)
    errors = []

    missing_columns = [c for c in REQUIRED if c not in df.columns]

    if missing_columns:
        errors.append(f"Missing columns: {missing_columns}")
        return errors

    if df.empty:
        errors.append("Dataset contains no records.")
        return errors

    numeric_columns = REQUIRED

    for column in numeric_columns:
        values = pd.to_numeric(df[column], errors="coerce")

        if values.isna().any():
            errors.append(
                f"{column}: {values.isna().sum()} missing or non-numeric values."
            )
        elif not np.isfinite(values).all():
            errors.append(f"{column}: non-finite values detected.")

    if "Class" in df.columns:
        labels = pd.to_numeric(df["Class"], errors="coerce").dropna()
        unexpected = sorted(set(labels.unique()) - VALID_CLASSES)

        if unexpected:
            errors.append(f"Unexpected class labels: {unexpected}")

    print("Rows:", len(df))
    print("Columns:", len(df.columns))
    print("EEG channels:", len(EEG_CHANNELS))
    print("EOG channels:", len(EOG_CHANNELS))
    print("Accelerometer channels:", len(ACC_CHANNELS))
    print("Class labels:", sorted(df["Class"].dropna().unique()))

    return errors


if __name__ == "__main__":
    errors = validate_sensor_data(FILE)

    if errors:
        print("\nFAIL: Sensor data validation found issues.")
        for error in errors:
            print("-", error)
    else:
        print("\nPASS: Sensor data validation successful.")
