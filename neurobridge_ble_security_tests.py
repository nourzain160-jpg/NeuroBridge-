import asyncio
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import secrets
import sys
import traceback

from datetime import datetime, timezone
from pathlib import Path

# CONFIGURATION

SCAN_ROUNDS = 3
SCAN_DURATION_SECONDS = 10

# Leave empty unless you have an authorized BLE device address.
# Example: TARGET_DEVICE_ADDRESS = "AA:BB:CC:DD:EE:FF"
TARGET_DEVICE_ADDRESS = ""

REPORT_DIRECTORY = Path("ble_test_reports")

EXPECTED_SENSOR_COLUMNS = [
    "timestamp",
    "emg_value",
    "imu_acc_x",
    "imu_acc_y",
    "imu_acc_z",
    "imu_gyro_x",
    "imu_gyro_y",
    "imu_gyro_z",
]

# Optional sample CSV file.
# Place the file beside this script or provide its full path.
SAMPLE_CSV_FILE = Path("sample_session.csv")


# REPORTING

results = []


def add_result(test_id, test_name, status, details):
    result = {
        "test_id": test_id,
        "test_name": test_name,
        "status": status,
        "details": str(details),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    results.append(result)

    print(f"\n[{status}] {test_id} - {test_name}")
    print(f"    {details}")


def save_reports(metadata):
    REPORT_DIRECTORY.mkdir(parents = True, exist_ok = True)

    json_path = REPORT_DIRECTORY / "neurobridge_ble_test_report.json"
    csv_path = REPORT_DIRECTORY / "neurobridge_ble_test_summary.csv"

    report = {
        "project": "NeuroBridge",
        "report_generated_utc": datetime.now(timezone.utc).isoformat(),
        "system_information": metadata,
        "results": results,
        "summary": {
            "total_tests": len(results),
            "passed": sum(r["status"] == "PASS" for r in results),
            "partial": sum(r["status"] == "PARTIAL" for r in results),
            "failed": sum(r["status"] == "FAIL" for r in results),
            "not_tested": sum(
                r["status"] == "NOT TESTED" for r in results
            ),
            "skipped": sum(r["status"] == "SKIPPED" for r in results),
        },
    }

    with open(json_path, "w", encoding = "utf-8") as file:
        json.dump(report, file, indent = 4, ensure_ascii = False)

    with open(csv_path, "w", newline = "", encoding = "utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames = [
                "test_id",
                "test_name",
                "status",
                "details",
                "timestamp_utc",
            ],
        )

        writer.writeheader()
        writer.writerows(results)

    print("\n" + "=" * 60)
    print("REPORTS SAVED")
    print("=" * 60)
    print(f"JSON: {json_path.resolve()}")
    print(f"CSV : {csv_path.resolve()}")


# TEST 01 - SYSTEM ENVIRONMENT

def test_environment():
    metadata = {
        "operating_system": platform.platform(),
        "python_version": sys.version,
        "python_executable": sys.executable,
        "machine": platform.machine(),
    }

    try:
        bleak_version = importlib.metadata.version("bleak")
        metadata["bleak_version"] = bleak_version
    except importlib.metadata.PackageNotFoundError:
        metadata["bleak_version"] = "Not installed"

    try:
        crypto_version = importlib.metadata.version("cryptography")
        metadata["cryptography_version"] = crypto_version
    except importlib.metadata.PackageNotFoundError:
        metadata["cryptography_version"] = "Not installed"

    try:
        pandas_version = importlib.metadata.version("pandas")
        metadata["pandas_version"] = pandas_version

    except importlib.metadata.PackageNotFoundError:
        metadata["pandas_version"] = "Not installed"

    add_result(
        "ENV-01",
        "Python Environment",
        "PASS",
        f"Python {platform.python_version()} on {platform.system()}",
    )

    try:
        import bleak
        add_result(
            "ENV-02",
            "Bleak Package Availability",
            "PASS",
            f"Bleak is importable; version: {metadata['bleak_version']}",
        )

    except ImportError:
        add_result(
            "ENV-02",
            "Bleak Package Availability",
            "FAIL",
            "Bleak is not installed or cannot be imported.",
        )

    try:
        import cryptography
        add_result(
            "ENV-03",
            "Cryptography Package Availability",
            "PASS",
            f"Cryptography version: {metadata['cryptography_version']}",
        )

    except ImportError:
        add_result(
            "ENV-03",
            "Cryptography Package Availability",
            "SKIPPED",
            "Cryptography package is not installed.",
        )

    return metadata


# TEST 02 - BLE PASSIVE SCANNING

async def test_ble_scanning():
    try:
        from bleak import BleakScanner

    except ImportError:
        add_result(
            "BLE-01",
            "BLE Passive Scanning",
            "FAIL",
            "Bleak is unavailable.",
        )
        return []

    all_devices = {}

    try:
        for round_number in range(1, SCAN_ROUNDS + 1):
            print(
                f"\nStarting BLE scan "
                f"{round_number}/{SCAN_ROUNDS}..."
            )
            discovered = await BleakScanner.discover(
                timeout = SCAN_DURATION_SECONDS,
                return_adv = True,
            )

            for address, item in discovered.items():
                device, advertisement = item

                all_devices[address] = {
                    "name": device.name,
                    "address": address,
                    "rssi": advertisement.rssi,
                    "uuids": advertisement.service_uuids or [],
                    "manufacturer_data": {
                        str(k): v.hex()
                        for k, v in (
                            advertisement.manufacturer_data or {}
                        ).items()
                    },
                    "service_data": {
                        str(k): v.hex()
                        for k, v in (
                            advertisement.service_data or {}
                        ).items()
                    },
                    "tx_power": advertisement.tx_power,
                }

        add_result(
            "BLE-01",
            "BLE Passive Scanning",
            "PASS",
            (
                f"Completed {SCAN_ROUNDS} scan rounds. "
                f"Discovered {len(all_devices)} unique device(s)."
            ),
        )

        for address, device in all_devices.items():
            print("\nDiscovered BLE device:")
            print(f"  Address: {address}")
            print(f"  Name: {device['name']}")
            print(f"  RSSI: {device['rssi']}")
            print(f"  Service UUIDs: {device['uuids']}")
            print(f"  TX Power: {device['tx_power']}")
            print(
                f"  Manufacturer Data: "
                f"{device['manufacturer_data']}"
            )
            print(f"  Service Data: {device['service_data']}")

        if len(all_devices) == 0:
            add_result(
                "BLE-02",
                "BLE Device Discovery",
                "PARTIAL",
                (
                    "Scanning completed successfully, "
                    "but no BLE advertisements were discovered."
                ),
            )
        else:
            add_result(
                "BLE-02",
                "BLE Device Discovery",
                "PASS",
                f"{len(all_devices)} BLE device(s) discovered.",
            )

    except Exception as error:
        add_result(
            "BLE-01",
            "BLE Passive Scanning",
            "FAIL",
            f"{type(error).name}: {error}",
        )

    return list(all_devices.values())


# TEST 03 - ADVERTISEMENT STRUCTURE

def test_advertisement_structure(devices):
    if not devices:
        add_result(
            "BLE-03",
            "Advertisement Structure",
            "NOT TESTED",
            "No BLE devices were discovered.",
        )
        return

    valid_records = 0
    invalid_records = 0

    for device in devices:

        if (
            isinstance(device.get("address"), str)
            and isinstance(device.get("uuids"), list)
            and isinstance(device.get("manufacturer_data"), dict)
            and isinstance(device.get("service_data"), dict)
        ):
            valid_records += 1
        else:
            invalid_records += 1

    if invalid_records == 0:
        add_result(
            "BLE-03",
            "Advertisement Structure",
            "PASS",
            (
                f"{valid_records} advertisement record(s) "
                "contained the expected metadata fields."
            ),
        )
    else:
        add_result(
            "BLE-03",
            "Advertisement Structure",
            "FAIL",
            f"{invalid_records} invalid advertisement record(s).",
        )


# TEST 04 - SERVICE UUID FORMAT

def test_service_uuid_format(devices):
    if not devices:
        add_result(
            "BLE-04",
            "Service UUID Format",
            "NOT TESTED",
            "No advertisements available.",
        )
        return

    from uuid import UUID

    valid = 0
    invalid = 0

    for device in devices:
        for service_uuid in device.get("uuids", []):
            try:
                UUID(str(service_uuid))
                valid += 1
            except (ValueError, TypeError):
                invalid += 1

    if invalid == 0:
        add_result(
            "BLE-04",
            "Service UUID Format",
            "PASS",
            f"{valid} advertised service UUID(s) checked.",
        )
    else:
        add_result(
            "BLE-04",
            "Service UUID Format",
            "FAIL",
            f"{invalid} invalid UUID value(s) detected.",
        )


# TEST 05 - OPTIONAL READ-ONLY GATT INSPECTION

async def test_gatt_inspection():
    if not TARGET_DEVICE_ADDRESS.strip():
        add_result(
            "BLE-05",
            "Read-Only GATT Inspection",
            "NOT TESTED",
            (
                "No authorized target address was configured. "
                "No device was connected."
            ),
        )
        return

    try:
        from bleak import BleakClient

    except ImportError:
        add_result(
            "BLE-05",
            "Read-Only GATT Inspection",
            "FAIL",
            "Bleak is unavailable.",
        )
        return

    try:
        print("\nConnecting to the explicitly configured device...")
        async with BleakClient(TARGET_DEVICE_ADDRESS) as client:

            if not client.is_connected:
                add_result(
                    "BLE-05",
                    "Read-Only GATT Inspection",
                    "FAIL",
                    "Connection was not established.",
                )
                return

            services = client.services
            service_count = 0
            characteristic_count = 0

            for service in services:
                service_count += 1

                print("\nGATT Service:")
                print(f"  UUID: {service.uuid}")

                for characteristic in service.characteristics:
                    characteristic_count += 1
                    print("  Characteristic:")
                    print(f"    UUID: {characteristic.uuid}")
                    print(
                        f"    Properties: "
                        f"{characteristic.properties}"
                    )

            add_result(
                "BLE-05",
                "Read-Only GATT Inspection",
                "PASS",
                (
                    f"Connected and enumerated {service_count} "
                    f"service(s) and {characteristic_count} "
                    "characteristic(s)."
                ),
            )

            add_result(
                "BLE-06",
                "GATT Access Permission Verification",
                "NOT TESTED",
                (
                    "Enumerating characteristic properties does not "
                    "prove that unauthorized access is blocked. "
                    "A controlled firmware permission test is required."
                ),
            )

    except Exception as error:
        add_result(
            "BLE-05",
            "Read-Only GATT Inspection",
            "FAIL",
            f"{type(error).name}: {error}",
        )


# TEST 06 - SAMPLE SENSOR DATA VALIDATION

def test_sensor_data_validation():
    if not SAMPLE_CSV_FILE.exists():
        add_result(
            "DATA-01",
            "Sensor Data File Availability",
            "NOT TESTED",
            f"File not found: {SAMPLE_CSV_FILE}",
        )
        return

    try:
        with open(
            SAMPLE_CSV_FILE,
            "r",
            newline = "",
            encoding = "utf-8-sig",
        ) as file:
            reader = csv.DictReader(file)
            actual_columns = reader.fieldnames or []
            missing_columns = [
                column
                for column in EXPECTED_SENSOR_COLUMNS
                if column not in actual_columns
            ]

            if missing_columns:
                add_result(
                    "DATA-01",
                    "Sensor Data Schema Validation",
                    "FAIL",
                    f"Missing columns: {missing_columns}",
                )
                return

            rows = list(reader)

        if not rows:
            add_result(
                "DATA-01",
                "Sensor Data Schema Validation",
                "PARTIAL",
                "CSV contains the expected columns but no data rows.",
            )
            return
        
        add_result(
            "DATA-01",
            "Sensor Data Schema Validation",
            "PASS",
            (
                f"All {len(EXPECTED_SENSOR_COLUMNS)} expected "
                f"columns found. Rows: {len(rows)}."
            ),
        )

        invalid_values = []
        numeric_columns = EXPECTED_SENSOR_COLUMNS[1:]

        for row_index, row in enumerate(rows, start = 2):
            for column in numeric_columns:
                try:
                    value = float(row[column])

                    if not math.isfinite(value):
                        raise ValueError("Non-finite number")

                except (ValueError, TypeError, KeyError):
                    invalid_values.append(
                        f"Row {row_index}, column {column}"
                    )

        if invalid_values:
            add_result(
                "DATA-02",
                "Sensor Numeric Data Validation",
                "FAIL",
                (
                    f"{len(invalid_values)} invalid numeric value(s). "
                    f"Examples: {invalid_values[:10]}"
                ),
            )
        else:
            add_result(
                "DATA-02",
                "Sensor Numeric Data Validation",
                "PASS",
                (
                    f"All {len(rows)} rows contain finite numeric "
                    "values in the required sensor columns."
                ),
            )

    except Exception as error:
        add_result(
            "DATA-01",
            "Sensor Data Validation",
            "FAIL",
            f"{type(error).name}: {error}",
        )


# TEST 07 - TIMESTAMP VALIDATION

def test_timestamp_validation():

    if not SAMPLE_CSV_FILE.exists():

        add_result(
            "DATA-03",
            "Timestamp Validation",
            "NOT TESTED",
            "Sample CSV file is unavailable.",
        )
        return

    try:

        with open(
            SAMPLE_CSV_FILE,
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            reader = csv.DictReader(file)
            rows = list(reader)

        timestamps = [
            row["timestamp"].strip()
            for row in rows
        ]

        if not timestamps:

            add_result(
                "DATA-03",
                "Timestamp Validation",
                "PARTIAL",
                "No timestamps available.",
            )
            return

        parsed_timestamps = []

        # Determine whether timestamps are numeric or ISO dates.
        try:

            parsed_timestamps = [
                float(value)
                for value in timestamps
            ]

            timestamp_type = "Numeric"

            if not all(
                math.isfinite(value)
                for value in parsed_timestamps
            ):
                raise ValueError("Non-finite timestamp value")

        except ValueError:

            parsed_timestamps = [
                datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                )
                for value in timestamps
            ]

            timestamp_type = "ISO datetime"

        ordered = all(
            parsed_timestamps[index]
            <= parsed_timestamps[index + 1]
            for index in range(len(parsed_timestamps) - 1)
        )

        unique = (
            len(set(parsed_timestamps))
            == len(parsed_timestamps)
        )

        if ordered and unique:

            add_result(
                "DATA-03",
                "Timestamp Validation",
                "PASS",
                (
                    f"{len(timestamps)} {timestamp_type} timestamps "
                    "are valid, ordered, and unique."
                ),
            )

        else:

            add_result(
                "DATA-03",
                "Timestamp Validation",
                "FAIL",
                (
                    f"Type: {timestamp_type}; "
                    f"Ordered: {ordered}; "
                    f"Unique: {unique}."
                ),
            )

    except Exception as error:

        add_result(
            "DATA-03",
            "Timestamp Validation",
            "FAIL",
            f"{type(error).name}: {error}",
        )


# TEST 08 - SHA-256 FILE INTEGRITY SELF-TEST

def calculate_sha256(data):
    return hashlib.sha256(data).hexdigest()

def test_sha256_integrity():
    original_data = (
        b"NeuroBridge synthetic sensor data integrity test"
    )

    original_hash = calculate_sha256(original_data)
    unchanged_hash = calculate_sha256(original_data)
    modified_data = (
        b"NeuroBridge modified sensor data integrity test"
    )

    modified_hash = calculate_sha256(modified_data)
    unchanged_detected = original_hash == unchanged_hash
    modification_detected = original_hash != modified_hash

    if unchanged_detected and modification_detected:
        add_result(
            "SEC-01",
            "SHA-256 Integrity Self-Test",
            "PASS",
            (
                "Identical data produced matching hashes, "
                "and modified data produced a different hash. "
                f"Original SHA-256: {original_hash}"
            ),
        )
    else:
        add_result(
            "SEC-01",
            "SHA-256 Integrity Self-Test",
            "FAIL",
            "The hash comparison did not behave as expected.",
        )


# TEST 09 - AES-CCM SOFTWARE SELF-TEST

def test_aes_ccm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESCCM

    except ImportError:
        add_result(
            "SEC-02",
            "AES-CCM Software Self-Test",
            "SKIPPED",
            "Install cryptography to run this software test.",
        )
        return

    try:
        key = secrets.token_bytes(16)
        nonce = secrets.token_bytes(13)
        plaintext = (
            b"NeuroBridge synthetic test message"
        )

        associated_data = (
            b"NeuroBridge test metadata"
        )

        aes = AESCCM(key, tag_length = 16)
        ciphertext = aes.encrypt(
            nonce,
            plaintext,
            associated_data,
        )

        decrypted = aes.decrypt(
            nonce,
            ciphertext,
            associated_data,
        )

        if decrypted == plaintext:
            add_result(
                "SEC-02",
                "AES-CCM Software Self-Test",
                "PASS",
                (
                    "AES-CCM encryption and decryption succeeded "
                    "using a temporary software-generated key."
                ),
            )
        else:
            add_result(
                "SEC-02",
                "AES-CCM Software Self-Test",
                "FAIL",
                "Decrypted output did not match the original message.",
            )

    except Exception as error:
        add_result(
            "SEC-02",
            "AES-CCM Software Self-Test",
            "FAIL",
            f"{type(error).name}: {error}",
        )


# TEST 10 - AES-CCM AUTHENTICATION SELF-TEST

def test_aes_ccm_authentication():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESCCM

    except ImportError:
        add_result(
            "SEC-03",
            "AES-CCM Authentication Self-Test",
            "SKIPPED",
            "Cryptography package is unavailable.",
        )
        return

    try:
        key = secrets.token_bytes(16)
        nonce = secrets.token_bytes(13)
        plaintext = b"Original NeuroBridge test payload"
        associated_data = b"Test metadata"
        aes = AESCCM(key, tag_length = 16)
        ciphertext = aes.encrypt(
            nonce,
            plaintext,
            associated_data,
        )

        tampered_ciphertext = bytearray(ciphertext)
        tampered_ciphertext[0] ^= 1

        try:
            aes.decrypt(
                nonce,
                bytes(tampered_ciphertext),
                associated_data,
            )

            tampering_rejected = False

        except Exception:
            tampering_rejected = True

        if tampering_rejected:
            add_result(
                "SEC-03",
                "AES-CCM Authentication Self-Test",
                "PASS",
                (
                    "Modified ciphertext was rejected by the "
                    "software AES-CCM authentication check."
                ),
            )
        else:
            add_result(
                "SEC-03",
                "AES-CCM Authentication Self-Test",
                "FAIL",
                "Modified ciphertext was not rejected.",
            )

    except Exception as error:
        add_result(
            "SEC-03",
            "AES-CCM Authentication Self-Test",
            "FAIL",
            f"{type(error).name}: {error}",
        )


# TEST 11 - RANDOMNESS API AVAILABILITY

def test_python_randomness():
    try:
        first = secrets.token_bytes(32)
        second = secrets.token_bytes(32)
        valid_length = (
            len(first) == 32 and len(second) == 32
        )

        different_samples = first != second

        if valid_length and different_samples:
            add_result(
                "SEC-04",
                "Python Secure Randomness API",
                "PASS",
                (
                    "Python secrets API generated two "
                    "32-byte samples."
                ),
            )
        else:
            add_result(
                "SEC-04",
                "Python Secure Randomness API",
                "FAIL",
                "Unexpected output from Python secrets API.",
            )

    except Exception as error:
        add_result(
            "SEC-04",
            "Python Secure Randomness API",
            "FAIL",
            f"{type(error).name}: {error}",
        )


# TEST 12 - HARDWARE-DEPENDENT SECURITY TESTS

def record_hardware_tests():
    hardware_tests = [
        (
            "HW-01",
            "BLE Pairing Method Verification",
            "Requires the actual nRF52840 device and firmware."
        ),

        (
            "HW-02",
            "LE Secure Connections Verification",
            "Requires inspection of the actual pairing procedure."
        ),

        (
            "HW-03",
            "MITM Protection Verification",
            "Requires a controlled pairing test with the configured IO capabilities."
        ),

        (
            "HW-04",
            "BLE Link Encryption Verification",
            "Requires a real BLE connection and verification of its encryption state."
        ),

        (
            "HW-05",
            "Bonding and Persistent Key Verification",
            "Requires testing the actual device's bonding and key-storage behavior."
        ),

        (
            "HW-06",
            "Unauthorized Device Rejection",
            "Requires the actual firmware and an authorized test setup."
        ),

        (
            "HW-07",
            "GATT Permission Enforcement",
            "Requires testing configured read/write permissions on the real device."
        ),

        (
            "HW-08",
            "Connection Interruption and Recovery",
            "Requires a real BLE device and application-level reconnection testing."
        ),

        (
            "HW-09",
            "Sensor Data Continuity",
            "Requires real sensor streams and sequence/timestamp verification."
        ),

        (
            "HW-10",
            "Firmware Security Configuration",
            "Requires inspection of the actual firmware configuration and build."
        ),

        (
            "HW-11",
            "Hardware Key Management",
            "Requires verification of the actual device's key generation and storage."
        ),
    ]

    for test_id, name, reason in hardware_tests:
        add_result(
            test_id,
            name,
            "NOT TESTED",
            reason,
        )


# MAIN

async def main():

    print("=" * 65)
    print("NEUROBRIDGE - BLE SECURITY TEST SUITE")
    print("=" * 65)
    print(
        "\nThis suite performs defensive software-side tests. "
        "It does not certify the hardware or firmware."
    )

    metadata = test_environment()
    devices = await test_ble_scanning()
    test_advertisement_structure(devices)
    test_service_uuid_format(devices)
    await test_gatt_inspection()
    test_sensor_data_validation()
    test_timestamp_validation()
    test_sha256_integrity()
    test_aes_ccm()
    test_aes_ccm_authentication()
    test_python_randomness()
    record_hardware_tests()
    save_reports(metadata)
    print("\n" + "=" * 65)
    print("TEST EXECUTION COMPLETED")
    print("=" * 65)


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\nExecution interrupted by the user.")

    except Exception:
        print("\nUnexpected execution error:")
        traceback.print_exc()