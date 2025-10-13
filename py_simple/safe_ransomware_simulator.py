# safe_ransomware_simulator.py
import os
import base64
from typing import List
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SafeRansomwareSimulator:
    """
    Safe simulation using symmetric AES-GCM over a sandbox directory.
    Non-destructive by default: creates .encrypted files alongside originals.
    """

    def __init__(self, sandbox_dir: str = None):
        # Default to a clearly sandboxed path instead of a user data folder
        self.test_directory = sandbox_dir or "C:\\Users\\user\\test\\"
        # 256-bit AES key
        self._key = AESGCM.generate_key(bit_length=256)
        self._aesgcm = AESGCM(self._key)

    def get_key(self) -> str:
        """Return the base64-encoded AES key as string (for analysis UI)."""
        return base64.b64encode(self._key).decode()

    def _encrypt_bytes(self, data: bytes) -> bytes:
        nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
        ct = self._aesgcm.encrypt(nonce, data, None)
        # Store nonce + ciphertext in the file
        return nonce + ct

    def _decrypt_bytes(self, data: bytes) -> bytes:
        if len(data) < 12:
            raise ValueError("Invalid encrypted data")
        nonce, ct = data[:12], data[12:]
        return self._aesgcm.decrypt(nonce, ct, None)

    def simulate_encryption(self, destructive: bool = False) -> List[str]:
        """
        Encrypt files in the sandbox directory.
        - When destructive=False (default), keep originals and write alongside .encrypted files.
        - When destructive=True, move originals to a backup subfolder instead of deleting.
        """
        encrypted_files: List[str] = []
        if not os.path.exists(self.test_directory):
            return encrypted_files

        backup_dir = os.path.join(self.test_directory, "_originals_backup")
        if destructive:
            os.makedirs(backup_dir, exist_ok=True)

        for filename in os.listdir(self.test_directory):
            filepath = os.path.join(self.test_directory, filename)
            if not os.path.isfile(filepath):
                continue
            if filepath.endswith(".encrypted"):
                continue

            with open(filepath, 'rb') as f:
                original_data = f.read()

            encrypted_data = self._encrypt_bytes(original_data)

            encrypted_path = filepath + ".encrypted"
            with open(encrypted_path, 'wb') as f:
                f.write(encrypted_data)

            if destructive:
                # Move original to backup to avoid data loss
                os.replace(filepath, os.path.join(backup_dir, filename))

            encrypted_files.append(encrypted_path)

        return encrypted_files

    def simulate_decryption(self) -> None:
        """Decrypt .encrypted files back to their original form (non-destructive)."""
        if not os.path.exists(self.test_directory):
            return

        for filename in os.listdir(self.test_directory):
            if not filename.endswith(".encrypted"):
                continue

            filepath = os.path.join(self.test_directory, filename)
            if not os.path.isfile(filepath):
                continue

            with open(filepath, 'rb') as f:
                encrypted_data = f.read()

            try:
                decrypted_data = self._decrypt_bytes(encrypted_data)
                original_path = filepath[:-10]  # remove .encrypted
                with open(original_path, 'wb') as f:
                    f.write(decrypted_data)
                # Keep encrypted file as artifact; remove if you prefer cleanup
                # os.remove(filepath)
            except Exception as e:
                print(f"Decryption failed for {filename}: {e}")


if __name__ == "__main__":
    sim = SafeRansomwareSimulator()
    print("Encrypting (non-destructive)...")
    sim.simulate_encryption(destructive=False)
    print("Encryption complete. To decrypt, use the backend API (POST /decrypt) or click the Decrypt button in the site.")
