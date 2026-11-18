"""Synthetic-data privacy and pseudonymization tests for NeuroBridge."""
import csv
import hashlib
import hmac
import io
import tempfile
import unittest
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TEST_DATA_DIR = BASE_DIR / "Test Data"
TEST_RESULTS_DIR = BASE_DIR / "Test Results"
SAMPLE_FILE = BASE_DIR / "privacy_sample_input.csv"
RESULT_FILE = TEST_RESULTS_DIR / "privacy_data_management_results.txt"

# Synthetic test key only. Never use this key for real participant data.
TEST_KEY = b"NeuroBridge-Synthetic-Test-Key-2026"
REQUIRED_COLUMNS = {
    "participant_id", "timestamp", "emg_biceps",
    "emg_triceps", "imu_angle", "class",
}
ALLOWED_FEATURE_COLUMNS = [
    "timestamp", "emg_biceps", "emg_triceps", "imu_angle", "class",
]
OUTPUT_COLUMNS = ["participant_code"] + ALLOWED_FEATURE_COLUMNS
MAPPING_COLUMNS = ["participant_code", "participant_id"]


def create_sample_file(path=SAMPLE_FILE):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "participant_id": "SUBJECT001",
            "name": "Synthetic Person A",
            "email": "personA@example.test",
            "phone": "000000001",
            "timestamp": "0.010",
            "emg_biceps": "0.45",
            "emg_triceps": "0.20",
            "imu_angle": "13.1",
            "class": "0",
        },
        {
            "participant_id": "SUBJECT001",
            "name": "Synthetic Person A",
            "email": "personA@example.test",
            "phone": "000000001",
            "timestamp": "0.020",
            "emg_biceps": "0.51",
            "emg_triceps": "0.23",
            "imu_angle": "14.0",
            "class": "1",
        },
        {
            "participant_id": "SUBJECT002",
            "name": "Synthetic Person B",
            "email": "personB@example.test",
            "phone": "000000002",
            "timestamp": "0.030",
            "emg_biceps": "0.63",
            "emg_triceps": "0.28",
            "imu_angle": "15.2",
            "class": "1",
        },
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def generate_participant_code(participant_id, key):
    if not isinstance(participant_id, str) or not participant_id.strip():
        raise ValueError("Participant ID must be a non-empty string.")
    if not isinstance(key, bytes) or len(key) < 16:
        raise ValueError("Pseudonymization key must contain at least 16 bytes.")

    # Full SHA-256 HMAC digest (64 hex characters); no unnecessary truncation.
    return hmac.new(
        key, participant_id.strip().encode("utf-8"), hashlib.sha256
    ).hexdigest()


def _atomic_write_csv(path, fieldnames, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", newline="", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as stream:
        temporary_path = Path(stream.name)
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        stream.flush()

    try:
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def process_dataset(input_file, output_file, mapping_file, key):
    input_file = Path(input_file)
    output_file = Path(output_file)
    mapping_file = Path(mapping_file)

    if len(key) < 16:
        raise ValueError("The pseudonymization key is too short.")
    if not input_file.is_file():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    if output_file.resolve() == mapping_file.resolve():
        raise ValueError("Processed data and identity mapping must be different files.")
    if output_file.parent.resolve() == mapping_file.parent.resolve():
        raise ValueError("Identity mapping must be stored in a separate directory.")

    with input_file.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("The input CSV is empty or has no header.")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        rows = list(reader)

    if not rows:
        raise ValueError("The dataset contains no records.")

    identity_mapping = {}
    processed_rows = []

    for row_number, row in enumerate(rows, start=2):
        participant_id = (row.get("participant_id") or "").strip()
        if not participant_id:
            raise ValueError(f"Participant ID is missing at CSV row {row_number}.")

        code = generate_participant_code(participant_id, key)
        identity_mapping[code] = participant_id

        processed_row = {"participant_code": code}
        for column in ALLOWED_FEATURE_COLUMNS:
            processed_row[column] = row.get(column, "")
        processed_rows.append(processed_row)

    mapping_rows = [
        {"participant_code": code, "participant_id": participant_id}
        for code, participant_id in sorted(identity_mapping.items())
    ]

    # Build both outputs fully before replacing either destination.
    _atomic_write_csv(output_file, OUTPUT_COLUMNS, processed_rows)
    _atomic_write_csv(mapping_file, MAPPING_COLUMNS, mapping_rows)
    return len(processed_rows)


class PrivacyDataManagementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.input_file = create_sample_file(self.root / "input.csv")
        self.output_file = self.root / "Processed" / "processed_data.csv"
        self.mapping_file = self.root / "Restricted" / "identity_mapping.csv"
        process_dataset(self.input_file, self.output_file, self.mapping_file, TEST_KEY)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_data_minimization(self):
        with self.output_file.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames, OUTPUT_COLUMNS)

    def test_direct_identifiers_removed(self):
        content = self.output_file.read_text(encoding="utf-8")
        for value in (
            "SUBJECT001", "SUBJECT002", "Synthetic Person A",
            "Synthetic Person B", "personA@example.test",
            "personB@example.test", "000000001", "000000002",
        ):
            self.assertNotIn(value, content)

    def test_identity_mapping_separation(self):
        self.assertTrue(self.output_file.is_file())
        self.assertTrue(self.mapping_file.is_file())
        self.assertNotEqual(self.output_file.parent.resolve(), self.mapping_file.parent.resolve())

    def test_pseudonymization_consistency(self):
        first = generate_participant_code("SUBJECT001", TEST_KEY)
        second = generate_participant_code("SUBJECT001", TEST_KEY)
        other = generate_participant_code("SUBJECT002", TEST_KEY)
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(len(first), 64)

    def test_identity_mapping_contents(self):
        with self.mapping_file.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            rows = list(reader)
            self.assertEqual(reader.fieldnames, MAPPING_COLUMNS)
        self.assertEqual(len(rows), 2)

    def test_missing_required_column_rejected(self):
        invalid = self.root / "invalid.csv"
        invalid.write_text("participant_id,timestamp\nSUBJECT001,0.010\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            process_dataset(
                invalid, self.root / "out" / "data.csv",
                self.root / "restricted" / "map.csv", TEST_KEY
            )

    def test_empty_participant_id_rejected(self):
        invalid = self.root / "empty_id.csv"
        invalid.write_text(
            "participant_id,timestamp,emg_biceps,emg_triceps,imu_angle,class\n"
            ",0.1,0.2,0.3,1.0,0\n",
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            process_dataset(
                invalid, self.root / "out2" / "data.csv",
                self.root / "restricted2" / "map.csv", TEST_KEY
            )

    def test_same_output_and_mapping_directory_rejected(self):
        same = self.root / "same"
        with self.assertRaises(ValueError):
            process_dataset(
                self.input_file, same / "data.csv", same / "map.csv", TEST_KEY
            )


def main():
    if not SAMPLE_FILE.exists():
        create_sample_file(SAMPLE_FILE)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PrivacyDataManagementTests)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)

    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = [
        "PRIVACY AND DATA MANAGEMENT TEST RESULTS",
        "========================================",
        "Test data: Synthetic sample data only",
        "",
        output.getvalue(),
        f"Tests executed: {result.testsRun}",
        f"Tests passed: {result.testsRun - len(result.failures) - len(result.errors)}",
        f"Tests failed: {len(result.failures)}",
        f"Tests with errors: {len(result.errors)}",
        f"OVERALL STATUS: {'PASS' if result.wasSuccessful() else 'FAIL'}",
        "",
        "SCOPE: Standalone pseudonymization and data-minimization tests.",
        "These tests do not establish system integration, production key management,",
        "automated retention/deletion, or encryption of real participant records.",
    ]
    report_text = "\n".join(report)
    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(report_text, encoding="utf-8")
    print(report_text)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
