"""Read-only BLE discovery and GATT checks for an authorized test device.

A successful scan is not proof that a discovered device belongs to NeuroBridge.
This script does not verify pairing method, MITM protection, bonding, or link
encryption. Those require device/firmware-specific verification.
"""
import argparse
import asyncio
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

REPORT_DIR = Path("ble_test_reports")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def address_fingerprint(address):
    if not address:
        return None
    return hashlib.sha256(address.encode("utf-8")).hexdigest()[:12]


def print_section(title):
    print("\n" + "=" * 68)
    print(title)
    print("=" * 68)


async def scan_ble(timeout):
    result = {
        "test_id": "BLE-01",
        "scan_status": "FAIL",
        "discovery_status": "NOT TESTED",
        "started_at_utc": utc_now(),
        "timeout_seconds": timeout,
        "device_count": 0,
        "devices": [],
        "error": None,
    }
    try:
        from bleak import BleakScanner
        discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
        result["scan_status"] = "PASS"
        for address, pair in discovered.items():
            device, advertisement = pair
            result["devices"].append({
                # Do not put stable device identifiers or raw advertisement
                # payloads in a report that may later be published.
                "address_fingerprint": address_fingerprint(address),
                "name_available": bool(
                    getattr(advertisement, "local_name", None)
                    or getattr(device, "name", None)
                ),
                "rssi_dbm": getattr(advertisement, "rssi", None),
                "advertised_service_count": len(
                    getattr(advertisement, "service_uuids", None) or []
                ),
            })
        result["device_count"] = len(result["devices"])
        result["discovery_status"] = "PASS" if result["device_count"] else "PARTIAL"
        print(
            f"Scan completed. Devices detected: {result['device_count']} "
            f"({result['discovery_status']})."
        )
        if not result["device_count"]:
            print("No advertisements were detected; this is not a scan failure.")
    except ImportError:
        result["error"] = "Bleak is not installed. Install with: python -m pip install bleak"
        print("FAIL:", result["error"])
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        print("FAIL:", result["error"])

    result["finished_at_utc"] = utc_now()
    return result


async def connect_and_inspect(address, do_notifications, notification_seconds):
    result = {
        "test_id": "BLE-02",
        "target_fingerprint": address_fingerprint(address),
        "connection_status": "NOT TESTED",
        "gatt_status": "NOT TESTED",
        "read_tests": [],
        "notification_tests": [],
        "reconnect_status": "NOT TESTED",
        "errors": [],
    }

    try:
        from bleak import BleakClient
    except ImportError:
        result["connection_status"] = "FAIL"
        result["errors"].append("Bleak is not installed.")
        return result

    client = BleakClient(address, timeout=20.0)
    connected_once = False

    try:
        await client.connect()
        if not client.is_connected:
            raise RuntimeError("Client did not report a connected state.")
        connected_once = True
        result["connection_status"] = "PASS"

        services = client.services
        characteristic_count = 0
        for service in services:
            for characteristic in service.characteristics:
                characteristic_count += 1
                properties = set(characteristic.properties)

                if "read" in properties:
                    try:
                        value = await client.read_gatt_char(characteristic.uuid)
                        result["read_tests"].append({
                            "characteristic_uuid": characteristic.uuid,
                            "status": "PASS",
                            "value_length_bytes": len(value),
                        })
                    except Exception as exc:
                        result["read_tests"].append({
                            "characteristic_uuid": characteristic.uuid,
                            "status": "FAIL",
                            "error": f"{type(exc).__name__}: {exc}",
                        })

                if do_notifications and ({"notify", "indicate"} & properties):
                    received_count = 0

                    def callback(sender, data):
                        nonlocal received_count
                        received_count += 1

                    subscribed = False
                    try:
                        await client.start_notify(characteristic.uuid, callback)
                        subscribed = True
                        await asyncio.sleep(notification_seconds)
                        status = "PASS" if received_count > 0 else "PARTIAL"
                        result["notification_tests"].append({
                            "characteristic_uuid": characteristic.uuid,
                            "subscription_status": "PASS",
                            "status": status,
                            "notifications_received": received_count,
                            "note": (
                                "No notifications arrived during the observation "
                                "window; the characteristic may be idle."
                                if received_count == 0 else "Notifications received."
                            ),
                        })
                    except Exception as exc:
                        result["notification_tests"].append({
                            "characteristic_uuid": characteristic.uuid,
                            "subscription_status": "FAIL",
                            "status": "FAIL",
                            "error": f"{type(exc).__name__}: {exc}",
                        })
                    finally:
                        if subscribed:
                            try:
                                await client.stop_notify(characteristic.uuid)
                            except Exception as exc:
                                result["errors"].append(
                                    f"stop_notify {characteristic.uuid}: "
                                    f"{type(exc).__name__}: {exc}"
                                )

        result["gatt_service_count"] = len(services)
        result["gatt_characteristic_count"] = characteristic_count
        result["gatt_status"] = (
            "PASS" if result["gatt_service_count"] > 0 and characteristic_count > 0
            else "PARTIAL"
        )

        failed_reads = any(item["status"] == "FAIL" for item in result["read_tests"])
        if failed_reads:
            result["gatt_status"] = "PARTIAL"

    except Exception as exc:
        result["connection_status"] = "FAIL"
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        if client.is_connected:
            try:
                await client.disconnect()
            except Exception as exc:
                result["errors"].append(f"Disconnect: {type(exc).__name__}: {exc}")

    if connected_once:
        reconnect_client = BleakClient(address, timeout=20.0)
        try:
            await reconnect_client.connect()
            result["reconnect_status"] = (
                "PASS" if reconnect_client.is_connected else "FAIL"
            )
        except Exception as exc:
            result["reconnect_status"] = "FAIL"
            result["errors"].append(f"Reconnect: {type(exc).__name__}: {exc}")
        finally:
            if reconnect_client.is_connected:
                try:
                    await reconnect_client.disconnect()
                except Exception as exc:
                    result["errors"].append(
                        f"Reconnect disconnect: {type(exc).__name__}: {exc}"
                    )

    return result


def save_report(report):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = REPORT_DIR / f"neurobridge_ble_report_{timestamp}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print_section("REPORT")
    print("Saved:", path)
    return path


async def async_main(argv=None):
    parser = argparse.ArgumentParser(description="NeuroBridge authorized BLE test suite")
    parser.add_argument("--scan-time", type=int, default=12)
    parser.add_argument("--connect", help="Address of an authorized test device")
    parser.add_argument("--notifications", action="store_true")
    parser.add_argument("--notification-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)

    if args.scan_time < 1 or args.notification_seconds <= 0:
        parser.error("Scan and notification durations must be positive.")

    print_section("NEUROBRIDGE BLE TEST SUITE")
    print("UTC:", utc_now())
    print("OS:", platform.platform())
    print("Python:", sys.version.split()[0])

    report = {
        "project": "NeuroBridge",
        "run_at_utc": utc_now(),
        "environment": {
            "os": platform.platform(),
            "python_version": sys.version.split()[0],
        },
        "scope_note": (
            "A scan or GATT inspection does not prove device identity, pairing "
            "security, MITM protection, bonding, or link encryption."
        ),
    }
    report["scan"] = await scan_ble(args.scan_time)

    if args.connect:
        report["connection_tests"] = await connect_and_inspect(
            args.connect, args.notifications, args.notification_seconds
        )
    else:
        report["connection_tests"] = {
            "connection_status": "NOT TESTED",
            "gatt_status": "NOT TESTED",
            "read_tests": [],
            "notification_tests": [],
            "reconnect_status": "NOT TESTED",
            "reason": "No authorized target device was supplied.",
        }

    save_report(report)

    statuses = [report["scan"]["scan_status"]]
    if args.connect:
        statuses.append(report["connection_tests"]["connection_status"])
        statuses.append(report["connection_tests"]["gatt_status"])
        statuses.extend(item["status"] for item in report["connection_tests"]["read_tests"])
        statuses.extend(
            item["status"] for item in report["connection_tests"]["notification_tests"]
        )
        if report["connection_tests"]["reconnect_status"] != "NOT TESTED":
            statuses.append(report["connection_tests"]["reconnect_status"])

    if "FAIL" in statuses:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(async_main()))
    except KeyboardInterrupt:
        print("\nTest run cancelled.")
        raise SystemExit(130)
