# data_storage_security.py

import os
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_key():
    """Generate a cryptographically secure 256-bit key."""
    return AESGCM.generate_key(bit_length = 256)


def save_key(key, key_path):
    """Save the demonstration key separately from encrypted data."""
    key_path = Path(key_path)
    key_path.parent.mkdir(parents = True, exist_ok = True)
    key_path.write_bytes(key)


def load_key(key_path):
    """Load the demonstration encryption key."""
    return Path(key_path).read_bytes()


def encrypt_file(input_path, output_path, key):
    """Encrypt a file using AES-256-GCM."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    plaintext = input_path.read_bytes()

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)

    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    output_path.parent.mkdir(parents = True, exist_ok = True)
    output_path.write_bytes(nonce + ciphertext)

    return True


def decrypt_file(input_path, output_path, key):
    """Decrypt and authenticate an AES-GCM encrypted file."""
    input_path = Path(input_path)
    output_path = Path(output_path)

    encrypted_data = input_path.read_bytes()

    if len(encrypted_data) < 13:
        raise ValueError("Invalid encrypted file.")

    nonce = encrypted_data[:12]
    ciphertext = encrypted_data[12:]

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    output_path.parent.mkdir(parents = True, exist_ok = True)
    output_path.write_bytes(plaintext)

    return True


if __name__ == "__main__":
    original_file = Path("sample_session.csv")
    encrypted_file = Path("sample_session.enc")
    decrypted_file = Path("sample_session_decrypted.csv")

    # Keep this key outside the data folder.
    key_file = Path("keys") / "neurobridge_demo.key"

    if not original_file.exists():
        raise FileNotFoundError(
            "sample_session.csv was not found."
        )

    if key_file.exists():
        key = load_key(key_file)
    else:
        key = generate_key()
        save_key(key, key_file)

    encrypt_file(original_file, encrypted_file, key)

    print("Encryption completed.")
    print("Encrypted file:", encrypted_file)

    decrypt_file(encrypted_file, decrypted_file, key)

    print("Decryption completed.")
    print("Decrypted file:", decrypted_file)

    if original_file.read_bytes() == decrypted_file.read_bytes():
        print("Integrity verification: PASS")
    else:
        print("Integrity verification: FAIL")