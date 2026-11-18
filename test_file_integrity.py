"""SHA-256 file and dataset integrity utilities for NeuroBridge."""
import argparse
import csv
import hashlib
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CHUNK_SIZE = 1024 * 1024


def calculate_sha256(file_path):
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_file_baseline(file_path, hash_file):
    file_path = Path(file_path)
    hash_file = Path(hash_file)
    if not file_path.is_file():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    digest = calculate_sha256(file_path)
    hash_file.write_text(digest + "\n", encoding="utf-8")
    print("BASELINE CREATED")
    print("File:", file_path.name)
    print("SHA-256:", digest)
    return True


def verify_file(file_path, hash_file):
    file_path = Path(file_path)
    hash_file = Path(hash_file)
    if not file_path.is_file():
        print(f"ERROR: Input file not found: {file_path}")
        return False
    if not hash_file.is_file():
        print("ERROR: Baseline file not found.")
        return False

    expected = hash_file.read_text(encoding="utf-8").strip().lower()
    if not SHA256_RE.fullmatch(expected):
        print("ERROR: Baseline does not contain a valid SHA-256 digest.")
        return False

    actual = calculate_sha256(file_path)
    if actual == expected:
        print("PASS: File integrity verified.")
        return True

    print("FAIL: File modification detected.")
    print("Expected:", expected)
    print("Actual:  ", actual)
    return False


def _dataset_files(dataset_path, manifest_path):
    manifest_resolved = manifest_path.resolve()
    for path in sorted(dataset_path.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        if path.resolve() == manifest_resolved:
            continue
        yield path


def create_dataset_manifest(dataset_path, manifest_path):
    dataset_path = Path(dataset_path).resolve()
    manifest_path = Path(manifest_path)
    if not dataset_path.is_dir():
        raise NotADirectoryError(f"Dataset directory not found: {dataset_path}")
    if manifest_path.exists():
        raise FileExistsError(
            "Manifest already exists. Refusing to overwrite the integrity baseline."
        )

    paths = list(_dataset_files(dataset_path, manifest_path))
    if not paths:
        raise ValueError("No regular dataset files were found.")

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    with manifest_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["File_Name", "SHA256", "Size_Bytes", "Baseline_Date_UTC"])
        for path in paths:
            writer.writerow([
                path.relative_to(dataset_path).as_posix(),
                calculate_sha256(path),
                path.stat().st_size,
                timestamp,
            ])

    print("DATASET BASELINE CREATED")
    print("Files recorded:", len(paths))
    print("Manifest:", manifest_path)
    return True


def verify_dataset_manifest(dataset_path, manifest_path):
    dataset_path = Path(dataset_path).resolve()
    manifest_path = Path(manifest_path)
    if not dataset_path.is_dir():
        raise NotADirectoryError(f"Dataset directory not found: {dataset_path}")
    if not manifest_path.is_file():
        raise FileNotFoundError("Dataset manifest not found.")

    records = {}
    with manifest_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        required = {"File_Name", "SHA256"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Manifest is missing required columns.")
        for row in reader:
            name = (row.get("File_Name") or "").strip()
            digest = (row.get("SHA256") or "").strip().lower()
            if not name or name in records:
                raise ValueError("Manifest contains an empty or duplicate file path.")
            if not SHA256_RE.fullmatch(digest):
                raise ValueError(f"Invalid SHA-256 value for manifest entry: {name}")
            records[name] = digest

    current_files = {
        path.relative_to(dataset_path).as_posix(): path
        for path in _dataset_files(dataset_path, manifest_path)
    }

    problems = 0
    for name, expected in records.items():
        path = current_files.pop(name, None)
        if path is None:
            print("MISSING:", name)
            problems += 1
            continue
        actual = calculate_sha256(path)
        if actual == expected:
            print("PASS:", name)
        else:
            print("CHANGED:", name)
            problems += 1

    for name in sorted(current_files):
        print("NEW FILE:", name)
        problems += 1

    if problems:
        print("VERIFICATION FAILED")
        print("Issues detected:", problems)
        return False

    print("VERIFICATION PASSED")
    print(f"All {len(records)} baseline files match.")
    return True


def build_parser():
    parser = argparse.ArgumentParser(description="NeuroBridge SHA-256 integrity checker")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["create-file", "verify-file", "create-dataset", "verify-dataset"],
    )
    parser.add_argument("--file")
    parser.add_argument("--hash-file")
    parser.add_argument("--dataset")
    parser.add_argument("--manifest")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.mode in {"create-file", "verify-file"}:
            if not args.file or not args.hash_file:
                parser.error("--file and --hash-file are required for file modes.")
            if args.mode == "create-file":
                create_file_baseline(args.file, args.hash_file)
                return 0
            return 0 if verify_file(args.file, args.hash_file) else 1

        if not args.dataset or not args.manifest:
            parser.error("--dataset and --manifest are required for dataset modes.")
        if args.mode == "create-dataset":
            create_dataset_manifest(args.dataset, args.manifest)
            return 0
        return 0 if verify_dataset_manifest(args.dataset, args.manifest) else 1

    except (OSError, ValueError, csv.Error) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
