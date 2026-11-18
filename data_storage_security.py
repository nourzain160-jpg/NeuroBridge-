"""Standalone AES-256-GCM file-encryption prototype for NeuroBridge.

The key-file helpers are for local demonstrations only. Production deployments
must use an OS credential store, hardware-backed keystore, or managed KMS.
"""
import os
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_LENGTH = 12
KEY_LENGTH = 32
TAG_LENGTH = 16


def _validate_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) != KEY_LENGTH:
        raise ValueError("AES-256-GCM requires a 32-byte key.")


def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary_path = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        try:
            path.chmod(mode)
        except OSError:
            # Windows may not support POSIX permission semantics.
            pass
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        temporary_path.unlink(missing_ok=True)
        raise


def generate_key() -> bytes:
    """Generate a cryptographically secure 256-bit AES key."""
    return AESGCM.generate_key(bit_length=256)


def save_key(key: bytes, key_path) -> None:
    """Save a demo key with restrictive permissions; refuse to overwrite it."""
    _validate_key(key)
    path = Path(key_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(key)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except Exception:
        path.unlink(missing_ok=True)
        raise


def load_key(key_path) -> bytes:
    """Load and validate a 32-byte demonstration key."""
    key = Path(key_path).read_bytes()
    _validate_key(key)
    return key


def encrypt_file(input_path, output_path, key: bytes, associated_data=None) -> bool:
    """Encrypt a file as nonce || AESGCM(ciphertext_and_tag)."""
    _validate_key(key)
    source = Path(input_path)
    destination = Path(output_path)

    if not source.is_file():
        raise FileNotFoundError(f"Input file not found: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output paths must be different.")

    plaintext = source.read_bytes()
    nonce = os.urandom(NONCE_LENGTH)
    encrypted = AESGCM(key).encrypt(nonce, plaintext, associated_data)
    _atomic_write(destination, nonce + encrypted)
    return True


def decrypt_file(input_path, output_path, key: bytes, associated_data=None) -> bool:
    """Authenticate and decrypt a file; never write plaintext before auth passes."""
    _validate_key(key)
    source = Path(input_path)
    destination = Path(output_path)

    if not source.is_file():
        raise FileNotFoundError(f"Encrypted file not found: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("Input and output paths must be different.")

    encrypted_data = source.read_bytes()
    minimum_length = NONCE_LENGTH + TAG_LENGTH
    if len(encrypted_data) < minimum_length:
        raise ValueError("Encrypted file is truncated or invalid.")

    nonce = encrypted_data[:NONCE_LENGTH]
    ciphertext_and_tag = encrypted_data[NONCE_LENGTH:]

    # AESGCM.decrypt raises InvalidTag for modified data, wrong keys, or AAD.
    plaintext = AESGCM(key).decrypt(nonce, ciphertext_and_tag, associated_data)
    _atomic_write(destination, plaintext)
    return True


if __name__ == "__main__":
    original_file = Path("sample_session.csv")
    encrypted_file = Path("sample_session.enc")
    decrypted_file = Path("sample_session_decrypted.csv")
    key_file = Path("keys") / "neurobridge_demo.key"

    if not original_file.is_file():
        raise SystemExit("ERROR: sample_session.csv was not found.")

    if key_file.exists():
        key = load_key(key_file)
    else:
        key = generate_key()
        save_key(key, key_file)

    encrypt_file(original_file, encrypted_file, key)
    decrypt_file(encrypted_file, decrypted_file, key)

    if original_file.read_bytes() != decrypted_file.read_bytes():
        raise SystemExit("FAIL: decrypted data does not match the original.")

    print("Encryption/decryption self-check: PASS")
    print(f"Encrypted file: {encrypted_file}")
    print(f"Decrypted file: {decrypted_file}")
    print("NOTE: The local key file is demonstration-only, not production key management.")
