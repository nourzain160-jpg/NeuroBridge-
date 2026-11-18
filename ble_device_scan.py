import asyncio
from bleak import BleakScanner


async def scan_ble_devices():
    print("Scanning for nearby BLE devices...")
    print("Please wait for 10 seconds.\n")

    try:
        devices = await BleakScanner.discover(
            timeout = 10,
            return_adv = True
        )

        if not devices:
            print("No BLE devices detected.")
            return

        print("BLE devices detected:\n")

        for address, (device, advertisement) in devices.items():
            name = (
                advertisement.local_name
                or device.name
                or "Unknown"
            )

            print(f"Name: {name}")
            print(f"Address: {address}")
            print(f"RSSI: {advertisement.rssi} dBm")
            print("-" * 40)

    except Exception as error:
        print("BLE scanning failed.")
        print(f"Error: {error}")


if __name__ == "__main__":
    asyncio.run(scan_ble_devices())