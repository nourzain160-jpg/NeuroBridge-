import csv
import hashlib
import hmac
import io
import tempfile
import unittest
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
TEST_DATA_DIR = BASE_DIR / "Test Data"
TEST_RESULTS_DIR = BASE_DIR / "Test Results"

SAMPLE_FILE = TEST_DATA_DIR / "privacy_sample_input.csv"
RESULT_FILE = TEST_RESULTS_DIR / "privacy_data_management_results.txt"

# Synthetic test key only. Production keys must be managed separately.
TEST_KEY = b"NeuroBridge-Synthetic-Test-Key-2026"

REQUIRED_COLUMNS = {
    "participant_id",
    "timestamp",
    "emg_biceps",
    "emg_triceps",
    "imu_angle",
    "class",
}

ALLOWED_FEATURE_COLUMNS = [
    "timestamp",
    "emg_biceps",
    "emg_triceps",
    "imu_angle",
    "class",
]

OUTPUT_COLUMNS = ["participant_code"] + ALLOWED_FEATURE_COLUMNS


def create_sample_file():
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)

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

    with SAMPLE_FILE.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def generate_participant_code(participant_id, key):
    digest = hmac.new(
        key,
        participant_id.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return digest[:16]


def process_dataset(input_file, output_file, mapping_file, key):
    if len(key) < 16:
        raise ValueError("The encryption/pseudonymization key is too short.")

    if output_file.parent.resolve() == mapping_file.parent.resolve():
        raise ValueError(
            "The identity mapping must be stored in a separate directory."
        )

    with input_file.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError("The input file is empty.")

        missing_columns = REQUIRED_COLUMNS - set(reader.fieldnames)

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {sorted(missing_columns)}"
            )

        rows = list(reader)

    if not rows:
        raise ValueError("The dataset contains no records.")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    mapping_file.parent.mkdir(parents=True, exist_ok=True)

    identity_mapping = {}
    processed_rows = []

    for row in rows:
        participant_id = row["participant_id"].strip()

        if not participant_id:
            raise ValueError("A participant ID is missing.")

        participant_code = generate_participant_code(
            participant_id,
            key
        )

        identity_mapping[participant_code] = participant_id

        processed_row = {
            "participant_code": participant_code
        }

        for column in ALLOWED_FEATURE_COLUMNS:
            processed_row[column] = row[column]

        processed_rows.append(processed_row)
        with output_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(processed_rows)

        with mapping_file.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["participant_code", "participant_id"]
            )
            writer.writeheader()

            for code, participant_id in identity_mapping.items():
                writer.writerow({
                    "participant_code": code,
                    "participant_id": participant_id,
                })


class PrivacyDataManagementTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.processed_dir = self.root / "Processed"
        self.restricted_dir = self.root / "Restricted"

        self.output_file = self.processed_dir / "processed_data.csv"
        self.mapping_file = self.restricted_dir / "identity_mapping.csv"

        process_dataset(
            SAMPLE_FILE,
            self.output_file,
            self.mapping_file,
            TEST_KEY
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_data_minimization(self):
        with self.output_file.open(
            "r", newline="", encoding="utf-8"
        ) as file:
            reader = csv.DictReader(file)
            self.assertEqual(reader.fieldnames, OUTPUT_COLUMNS)

    def test_direct_identifiers_removed(self):
        content = self.output_file.read_text(encoding="utf-8")

        forbidden_values = [
            "SUBJECT001",
            "SUBJECT002",
            "Synthetic Person A",
            "Synthetic Person B",
            "personA@example.test",
            "personB@example.test",
            "000000001",
            "000000002",
        ]

        for value in forbidden_values:
            self.assertNotIn(value, content)

    def test_identity_mapping_separation(self):
        self.assertTrue(self.output_file.exists())
        self.assertTrue(self.mapping_file.exists())

        self.assertNotEqual(
            self.output_file.parent.resolve(),
            self.mapping_file.parent.resolve()
        )

    def test_pseudonymization_consistency(self):
        code_1 = generate_participant_code("SUBJECT001", TEST_KEY)
        code_2 = generate_participant_code("SUBJECT001", TEST_KEY)
        code_3 = generate_participant_code("SUBJECT002", TEST_KEY)

        self.assertEqual(code_1, code_2)
        self.assertNotEqual(code_1, code_3)
        self.assertNotEqual(code_1, "SUBJECT001")

    def test_identity_mapping_contents(self):
        with self.mapping_file.open(
            "r", newline="", encoding="utf-8"
        ) as file:
            reader = csv.DictReader(file)
            mapping_rows = list(reader)

        self.assertEqual(
            reader.fieldnames,
            ["participant_code", "participant_id"]
        )
        self.assertEqual(len(mapping_rows), 2)

    def test_missing_required_column_rejected(self):
        invalid_file = self.root / "invalid_input.csv"

        with invalid_file.open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.writer(file)
            writer.writerow(["participant_id", "timestamp"])
            writer.writerow(["SUBJECT001", "0.010"])

        with self.assertRaises(ValueError):
            process_dataset(
                invalid_file,
                self.root / "invalid_output" / "data.csv",
                self.root / "invalid_restricted" / "mapping.csv",
                TEST_KEY
            )


def main():
    create_sample_file()

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        PrivacyDataManagementTests
    )

    output = io.StringIO()
    runner = unittest.TextTestRunner(
        stream=output,
        verbosity=2
    )

    result = runner.run(suite)

    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    report = [
        "PRIVACY AND DATA MANAGEMENT TEST RESULTS",
        "========================================",
        "Test data: Synthetic sample data only",
        "Tests executed: 6",
        "",
        output.getvalue(),
        f"Tests passed: {result.testsRun - len(result.failures) - len(result.errors)}",
        f"Tests failed: {len(result.failures)}",
        f"Tests with errors: {len(result.errors)}",
        "",
    ]

    if result.wasSuccessful():
        report.append("OVERALL STATUS: PASS")
    else:
        report.append("OVERALL STATUS: FAIL")

    report.extend([
        "",
        "SCOPE NOTE:",
        "These tests demonstrate a standalone pseudonymization and",
        "data minimization workflow using synthetic data.",
        "They do not establish integration into the complete NeuroBridge system.",
        "They do not test encryption, access-control integration,",
        "automated retention, or automated deletion.",
    ])

    report_text = "\n".join(report)
    RESULT_FILE.write_text(report_text, encoding="utf-8")

    print(report_text)

    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()