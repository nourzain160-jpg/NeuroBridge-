import tempfile
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidTag

from data_storage_security import (
    generate_key,
    encrypt_file,
    decrypt_file,
)


class DataStorageSecurityTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)

        self.original = self.folder / "sample.csv"
        self.encrypted = self.folder / "sample.enc"
        self.decrypted = self.folder / "decrypted.csv"

        self.original.write_text(
            "timestamp,emg_value,imu_acc_x\n"
            "1000,0.45,0.12\n"
            "1200,0.51,0.18\n",
            encoding ="utf-8",
        )

        self.key = generate_key()

    def tearDown(self):
        self.temp.cleanup()

    def test_key_generation(self):
        self.assertEqual(len(self.key), 32)

    def test_file_encryption(self):
        encrypt_file(
            self.original,
            self.encrypted,
            self.key,
        )

        self.assertTrue(self.encrypted.exists())
        self.assertNotEqual(
            self.original.read_bytes(),
            self.encrypted.read_bytes(),
        )

    def test_successful_decryption(self):
        encrypt_file(
            self.original,
            self.encrypted,
            self.key,
        )

        decrypt_file(
            self.encrypted,
            self.decrypted,
            self.key,
        )

        self.assertEqual(
            self.original.read_bytes(),
            self.decrypted.read_bytes(),
        )

    def test_modified_ciphertext_is_rejected(self):
        encrypt_file(
            self.original,
            self.encrypted,
            self.key,
        )

        content = bytearray(self.encrypted.read_bytes())
        content[-1] ^= 1
        self.encrypted.write_bytes(content)

        with self.assertRaises(InvalidTag):
            decrypt_file(
                self.encrypted,
                self.decrypted,
                self.key,
            )

    def test_wrong_key_is_rejected(self):
        encrypt_file(
            self.original,
            self.encrypted,
            self.key,
        )

        wrong_key = generate_key()

        with self.assertRaises(InvalidTag):
            decrypt_file(
                self.encrypted,
                self.decrypted,
                wrong_key,
            )


if __name__ == "__main__":
    unittest.main(verbosity = 2)