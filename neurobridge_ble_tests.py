import argparse
import asyncio
import csv
import json
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

try:
    import bleak
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("ERROR: Bleak is not installed.")
    print("Install it with: python -m pip install --upgrade bleak")
    raise SystemExit(1)


REPORT_DIR = Path("ble_test_reports")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def safe_json_value(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple, set)):
        return [safe_json_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): safe_json_value(v) for k, v in value.items()}
    return str(value)


def print_section(title):
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


def result_line(test_id, status, detail=""):
    print(f"[{status:<12}] {test_id}: {detail}")


async def scan_ble(timeout):
    print_section("BLE DEVICE DISCOVERY")
    print(f"Scanning for {timeout} seconds...")
    scan_result = {
        "test_id": "BLE-01",
        "status": "FAIL",
        "started_at_utc": utc_now(),
        "timeout_seconds": timeout,
        "devices": [],
        "error": None,
    }

    try:
        discovered = await BleakScanner.discover(
            timeout=timeout,
            return_adv=True
        )

        for address, pair in discovered.items():
            device, adv = pair
            local_name = (
                getattr(adv, "local_name", None)
                or getattr(device, "name", None)
                or "Unknown"
            )

            record = {
                "name": local_name,
                "address": address,
                "rssi_dbm": getattr(adv, "rssi", None),
                "advertised_uuids": safe_json_value(
                    getattr(adv, "service_uuids", None) or []
                ),
                "manufacturer_data": safe_json_value(
                    getattr(adv, "manufacturer_data", None) or {}
                ),
                "service_data": safe_json_value(
                    getattr(adv, "service_data", None) or {}
                ),
                "tx_power": getattr(adv, "tx_power", None),
                "details": getattr(device, "details", None).__str__()
                if getattr(device, "details", None) is not None else None,
            }
            scan_result["devices"].append(record)

        scan_result["status"] = "PASS" if scan_result["devices"] else "PASS"
        result_line(
            "BLE-01",
            "PASS",
            f"Scan completed; {len(scan_result['devices'])} device(s) detected."
        )

        if not scan_result["devices"]:
            print("No BLE advertisements were detected during this scan.")
        else:
            for index, item in enumerate(scan_result["devices"], start=1):
                print(f"\nDevice {index}")
                print(f"  Name: {item['name']}")
                print(f"  Address: {item['address']}")
                print(f"  RSSI: {item['rssi_dbm']} dBm")
                print(f"  Advertised service UUIDs: {item['advertised_uuids']}")
                print(f"  Manufacturer data: {item['manufacturer_data']}")
                print(f"  Service data: {item['service_data']}")
                print(f"  TX power: {item['tx_power']}")

    except Exception as exc:
        scan_result["error"] = f"{type(exc).__name__}: {exc}"
        result_line("BLE-01", "FAIL", scan_result["error"])
        print("\nTroubleshooting:")
        print("- Make sure Bluetooth is enabled in Windows.")
        print("- Make sure Windows allows desktop apps to use Bluetooth.")
        print("- Keep the computer near the BLE device.")
        print("- Close apps that may be holding an exclusive connection.")

    scan_result["finished_at_utc"] = utc_now()
    return scan_result


async def connect_and_inspect(address, do_notifications):
    print_section("GATT CONNECTION AND SERVICE INSPECTION")
    result = {
        "test_id": "BLE-02",
        "target_address": address,
        "connection_status": "NOT TESTED",
        "gatt_status": "NOT TESTED",
        "read_tests": [],
        "notification_tests": [],
        "reconnect_status": "NOT TESTED",
        "services": [],
        "errors": [],
    }

    client = BleakClient(address, timeout=20.0)

    try:
        await client.connect()
        if not client.is_connected:
            raise RuntimeError("Client did not report a connected state.")

        result["connection_status"] = "PASS"
        result_line("BLE-02", "PASS", f"Connected to {address}")

        # Bleak 2.x exposes services after connection.
        services = client.services
        for service in services:
            service_record = {
                "uuid": service.uuid,
                "description": getattr(service, "description", ""),
                "characteristics": [],
            }

            for char in service.characteristics:
                char_record = {
                    "uuid": char.uuid,
                    "description": getattr(char, "description", ""),
                    "properties": list(char.properties),
                    "read_result": "NOT TESTED",
                    "read_value_hex": None,
                    "read_error": None,
                }

                # Read only characteristics that explicitly advertise "read".
                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        char_record["read_result"] = "PASS"
                        char_record["read_value_hex"] = bytes(value).hex()
                        result["read_tests"].append({
                            "characteristic_uuid": char.uuid,
                            "status": "PASS",
                            "value_length_bytes": len(value),
                        })
                    except Exception as exc:
                        char_record["read_result"] = "FAIL"
                        char_record["read_error"] = f"{type(exc).__name__}: {exc}"
                        result["read_tests"].append({
                            "characteristic_uuid": char.uuid,
                            "status": "FAIL",
                            "error": char_record["read_error"],
                        })

                service_record["characteristics"].append(char_record)

            result["services"].append(service_record)

        result["gatt_status"] = "PASS"
        result_line(
            "BLE-03",
            "PASS",
            f"Discovered {len(result['services'])} GATT service(s)."
        )

        print("\nGATT overview:")
        for service in result["services"]:
            print(f"\n  Service: {service['uuid']}")
            for char in service["characteristics"]:
                print(f"    Characteristic: {char['uuid']}")
                print(f"      Properties: {', '.join(char['properties']) or 'None'}")
                print(f"      Read test: {char['read_result']}")

        if result["read_tests"]:
            passed = sum(x["status"] == "PASS" for x in result["read_tests"])
            failed = sum(x["status"] == "FAIL" for x in result["read_tests"])
            result_line(
                "BLE-04",
                "PASS" if failed == 0 else "PARTIAL",
                f"{passed} readable characteristic(s) read; {failed} failed."
            )
        else:
            result_line(
                "BLE-04",
                "NOT TESTED",
                "No characteristic advertised the read property."
            )

        if do_notifications:
            print_section("GATT NOTIFICATION TEST")
            notify_chars = []
            for service in services:
                for char in service.characteristics:
                    if "notify" in char.properties or "indicate" in char.properties:
                        notify_chars.append(char)

            if not notify_chars:
                result_line(
                    "BLE-05",
                    "NOT TESTED",
                    "No notify/indicate characteristic was discovered."
                )
            else:
                # Subscribe briefly to each eligible characteristic.
                # No values are written to the device.
                for char in notify_chars:
                    received = []

                    def callback(sender, data):
                        received.append({
                            "sender": str(sender),
                            "length_bytes": len(data),
                            "value_hex": bytes(data).hex(),
                            "received_at_utc": utc_now(),
                        })

                    try:
                        await client.start_notify(char.uuid, callback)
                        await asyncio.sleep(5)
                        await client.stop_notify(char.uuid)
                        status = "PASS" if received else "PASS"
                        result["notification_tests"].append({
                            "characteristic_uuid": char.uuid,
                            "status": status,
                            "notifications_received": len(received),
                            "samples": received[:5],
                        })
                        result_line(
                            "BLE-05",
                            status,
                            f"{char.uuid}: subscription succeeded; "
                            f"{len(received)} notification(s) received."
                        )
                    except Exception as exc:
                        error = f"{type(exc).__name__}: {exc}"
                        result["notification_tests"].append({
                            "characteristic_uuid": char.uuid,
                            "status": "FAIL",
                            "error": error,
                        })
                        result_line("BLE-05", "FAIL", f"{char.uuid}: {error}")

        else:
            result_line(
                "BLE-05",
                "NOT TESTED",
                "Notification test not requested. Use --notifications after reviewing UUIDs."
            )

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        result["errors"].append(error)
        result_line("BLE-02/03", "FAIL", error)
        print("\nConnection may fail because the selected device is unavailable,")
        print("not connectable, out of range, or requires pairing/permissions.")
    finally:
        try:
            if client.is_connected:
                await client.disconnect()
        except Exception as exc:
            result["errors"].append(f"Disconnect: {type(exc).__name__}: {exc}")

    # Reconnect test: attempt a second connection to the same target.
    print_section("DISCONNECT / RECONNECT TEST")
    try:
        reconnect_client = BleakClient(address, timeout=20.0)
        await reconnect_client.connect()
        result["reconnect_status"] = (
            "PASS" if reconnect_client.is_connected else "FAIL"
        )
        result_line(
            "BLE-06",
            result["reconnect_status"],
            "Second connection attempt completed."
        )
        if reconnect_client.is_connected:
            await reconnect_client.disconnect()
    except Exception as exc:
        result["reconnect_status"] = "FAIL"
        result["errors"].append(f"Reconnect: {type(exc).__name__}: {exc}")
        result_line("BLE-06", "FAIL", f"{type(exc).__name__}: {exc}")

    return result


def save_report(report):
    REPORT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = REPORT_DIR / f"neurobridge_ble_report_{timestamp}.json"
    csv_path = REPORT_DIR / f"neurobridge_ble_devices_{timestamp}.csv"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, ensure_ascii=False)

    devices = report.get("scan", {}).get("devices", [])
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        fieldnames = [
            "name", "address", "rssi_dbm", "advertised_uuids",
            "manufacturer_data", "service_data", "tx_power"
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for device in devices:
            writer.writerow({
                key: json.dumps(device.get(key), ensure_ascii=False)
                if isinstance(device.get(key), (dict, list))
                else device.get(key)
                for key in fieldnames
            })

    print_section("REPORT FILES")
    print(f"JSON report: {json_path.resolve()}")
    print(f"CSV device list: {csv_path.resolve()}")
    return str(json_path), str(csv_path)


async def main():
    parser = argparse.ArgumentParser(
        description="NeuroBridge single-file BLE test suite"
    )
    parser.add_argument(
        "--scan-time",
        type=int,
        default=12,
        help="BLE scan duration in seconds (default: 12)"
    )
    parser.add_argument(
        "--connect",
        type=str,
        default=None,
        help="Address of an authorized BLE test device"
    )
    parser.add_argument(
        "--notifications",
        action="store_true",
        help="Subscribe briefly to discovered notify/indicate characteristics"
    )
    args = parser.parse_args()

    print_section("NEUROBRIDGE BLE TEST SUITE")
    print(f"Run time (UTC): {utc_now()}")
    print(f"Operating system: {platform.platform()}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Bleak version: {getattr(bleak, '__version__', 'version unavailable')}")
    print("Mode: passive scan" if not args.connect else f"Mode: scan + connect to {args.connect}")

    report = {
        "project": "NeuroBridge",
        "tool": "NeuroBridge BLE Test Suite",
        "run_at_utc": utc_now(),
        "environment": {
            "os": platform.platform(),
            "python": sys.version,
            "bleak_version": getattr(bleak, "__version__", "unknown"),
        },
        "scope_note": (
            "This tool does not establish BLE authentication, MITM protection, "
            "bonding, or encryption status. These require device/stack-specific "
            "verification. No hardware-specific result is inferred from nearby devices."
        ),
    }

    report["scan"] = await scan_ble(max(3, args.scan_time))

    if args.connect:
        report["connection_tests"] = await connect_and_inspect(
            args.connect,
            args.notifications
        )
    else:
        report["connection_tests"] = {
            "connection_status": "NOT TESTED",
            "gatt_status": "NOT TESTED",
            "read_tests": [],
            "notification_tests": [],
            "reconnect_status": "NOT TESTED",
            "reason": "No NeuroBridge BLE device address was supplied."
        }
        result_line(
            "BLE-02 to BLE-06",
            "NOT TESTED",
            "Requires an identified, authorized BLE device."
        )

    save_report(report)

    print_section("INTERPRETATION")
    print("- A successful scan confirms BLE discovery is working on this computer.")
    print("- It does not identify any detected device as NeuroBridge hardware.")
    print("- GATT, read, notification, and reconnect tests require a real test device.")
    print("- Pairing, MITM, bonding, and encryption are not verified by this script.")
    print("\nRun completed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest run cancelled by user.")
