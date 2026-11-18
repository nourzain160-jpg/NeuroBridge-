import hashlib
import csv
import argparse
from pathlib import Path
from datetime import datetime, timezone


def calculate_sha256(file_path):
    sha = hashlib.sha256()

    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(chunk)

    return sha.hexdigest()


def create_file_baseline(file_path, hash_file):
    file_hash = calculate_sha256(file_path)

    hash_file.write_text(
        file_hash + "\n",
        encoding="utf-8"
    )

    print("BASELINE CREATED")
    print("File:", file_path.name)
    print("SHA-256:", file_hash)


def verify_file(file_path, hash_file):
    if not hash_file.exists():
        print("ERROR: Baseline file not found.")
        return False

    expected_hash = hash_file.read_text(
        encoding="utf-8"
    ).strip()

    actual_hash = calculate_sha256(file_path)

    if actual_hash == expected_hash:
        print("PASS: File integrity verified.")
        return True

    print("FAIL: File modification detected.")
    print("Expected:", expected_hash)
    print("Actual:  ", actual_hash)
    return False


def create_dataset_manifest(dataset_path, manifest_path):
    files = sorted(
        p for p in dataset_path.rglob("*")
        if p.is_file()
    )

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    if manifest_path.exists():
        raise FileExistsError(
            "Manifest already exists. Refusing to overwrite baseline."
        )

    with manifest_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.writer(file)

        writer.writerow([
            "File_Name",
            "SHA256",
            "Size_Bytes",
            "Baseline_Date_UTC"
        ])

        for path in files:
            writer.writerow([
                path.relative_to(dataset_path).as_posix(),
                calculate_sha256(path),
                path.stat().st_size,
                datetime.now(timezone.utc).isoformat()
            ])

    print("DATASET BASELINE CREATED")
    print("Files recorded:", len(files))
    print("Manifest:", manifest_path)


def verify_dataset_manifest(dataset_path, manifest_path):
    if not manifest_path.exists():
        raise FileNotFoundError("Dataset manifest not found.")

    with manifest_path.open(
        newline="", encoding="utf-8"
    ) as file:
        records = {
            row["File_Name"]: row["SHA256"]
            for row in csv.DictReader(file)
        }

    current_files = {
        p.relative_to(dataset_path).as_posix(): p
        for p in dataset_path.rglob("*")
        if p.is_file()
    }

    problems = 0

    for name, expected_hash in records.items():
        path = current_files.pop(name, None)

        if path is None:
            print("MISSING:", name)
            problems += 1
            continue

        actual_hash = calculate_sha256(path)

        if actual_hash == expected_hash:
            print("PASS:", name)
        else:
            print("CHANGED:", name)
            problems += 1

    for name in current_files:
        print("NEW FILE:", name)
        problems += 1

    if problems:
        print("VERIFICATION FAILED")
        print("Issues detected:", problems)
        return False

    print("VERIFICATION PASSED")
    print("All baseline files match.")
    return True


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        required=True,
        choices=[
            "create-file",
            "verify-file",
            "create-dataset",
            "verify-dataset"
        ]
    )

    parser.add_argument("--file")
    parser.add_argument("--hash-file")
    parser.add_argument("--dataset")
    parser.add_argument("--manifest")

    args = parser.parse_args()

    if args.mode in ["create-file", "verify-file"]:
        if not args.file or not args.hash_file:
            parser.error("--file and --hash-file are required.")

        file_path = Path(args.file)
        hash_path = Path(args.hash_file)

        if not file_path.is_file():
            parser.error("Input file does not exist.")

        if args.mode == "create-file":
            create_file_baseline(file_path, hash_path)
        else:
            verify_file(file_path, hash_path)

    else:
        if not args.dataset or not args.manifest:
            parser.error("--dataset and --manifest are required.")

        dataset_path = Path(args.dataset)
        manifest_path = Path(args.manifest)

        if not dataset_path.is_dir():
            parser.error("Dataset directory does not exist.")

        if args.mode == "create-dataset":
            create_dataset_manifest(
                dataset_path, manifest_path
            )
        else:
            verify_dataset_manifest(
                dataset_path, manifest_path
            )


if __name__ == "__main__":
    main()