import os
import json
import socket
import platform
from datetime import datetime

try:
    import winreg  # Windows registry API (standard library on Windows)
except ImportError:  # Not on Windows
    winreg = None


class BehaviorSimulator:
    """Simulate additional benign indicators for analysis tooling.

    All actions are safe and confined to a sandbox directory or a test registry
    path under HKCU that can be cleaned up.
    """

    def __init__(self, sandbox_dir: str):
        self.sandbox_dir = sandbox_dir
        self.indicator_log = os.path.join(sandbox_dir, "indicators.json")
        os.makedirs(self.sandbox_dir, exist_ok=True)

    def _append_indicator(self, kind: str, details: dict):
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "kind": kind,
            "details": details,
        }
        existing = []
        try:
            if os.path.exists(self.indicator_log):
                with open(self.indicator_log, "r", encoding="utf-8") as f:
                    existing = json.load(f)
        except Exception:
            existing = []
        existing.append(entry)
        with open(self.indicator_log, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2)

    def drop_ransom_notes(self) -> list:
        notes = [
            os.path.join(self.sandbox_dir, "READ_THIS_TEST.txt"),
            os.path.join(self.sandbox_dir, "DECRYPT_INSTRUCTIONS_TEST.html"),
            os.path.join(self.sandbox_dir, "RECOVERY_TEST.txt"),
        ]
        content = (
            "=== RANSOMWARE SIMULATION ===\n"
            "This is a benign test note for analysis tooling.\n"
            "No payment is required; use the provided server-side decrypt.\n"
        )
        for p in notes:
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
        self._append_indicator("ransom_notes", {"files": notes})
        return notes

    def simulate_registry_changes(self) -> dict:
        if platform.system() != "Windows" or winreg is None:
            details = {"status": "skipped", "reason": "non-Windows platform"}
            self._append_indicator("registry", details)
            return details

        # HKCU\Software\RansomSimTest
        created = []
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\RansomSimTest")
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "RansomSim")
            winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, "1.0")
            winreg.SetValueEx(key, "SandboxDir", 0, winreg.REG_SZ, self.sandbox_dir)
            winreg.CloseKey(key)
            created.append(r"HKCU\\Software\\RansomSimTest")
            details = {"status": "ok", "created_keys": created}
        except Exception as e:
            details = {"status": "error", "error": str(e)}

        self._append_indicator("registry", details)
        return details

    def cleanup_registry(self) -> dict:
        if platform.system() != "Windows" or winreg is None:
            details = {"status": "skipped", "reason": "non-Windows platform"}
            self._append_indicator("registry_cleanup", details)
            return details

        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\RansomSimTest")
            details = {"status": "ok", "removed": r"HKCU\\Software\\RansomSimTest"}
        except FileNotFoundError:
            details = {"status": "ok", "removed": "none"}
        except Exception as e:
            details = {"status": "error", "error": str(e)}

        self._append_indicator("registry_cleanup", details)
        return details

    def simulate_network_activity(self) -> dict:
        # Attempt a benign localhost connection that will likely fail quickly
        host, port = "127.0.0.1", 65500
        result = {"target": f"{host}:{port}", "connected": False}
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.25)
                s.connect((host, port))
                result["connected"] = True
        except Exception as e:
            result["error"] = str(e)
        self._append_indicator("network", result)
        return result

    def simulate_discovery(self) -> dict:
        file_count = 0
        by_ext = {}
        if not os.path.exists(self.sandbox_dir):
            details = {"status": "skip", "reason": "sandbox missing"}
            self._append_indicator("discovery", details)
            return details

        for root, _, files in os.walk(self.sandbox_dir):
            for name in files:
                file_count += 1
                ext = os.path.splitext(name)[1].lower() or "(none)"
                by_ext[ext] = by_ext.get(ext, 0) + 1

        inventory_path = os.path.join(self.sandbox_dir, "inventory.json")
        with open(inventory_path, "w", encoding="utf-8") as f:
            json.dump({"total": file_count, "by_ext": by_ext}, f, indent=2)

        details = {"status": "ok", "total": file_count, "by_ext": by_ext, "inventory": inventory_path}
        self._append_indicator("discovery", details)
        return details

    def simulate_command_strings(self) -> str:
        commands = [
            "vssadmin delete shadows /all /quiet",
            "wbadmin delete catalog -quiet",
            "bcdedit /set {default} recoveryenabled No",
            "bcdedit /set {default} bootstatuspolicy ignoreallfailures",
        ]
        path = os.path.join(self.sandbox_dir, "commands_attempted.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(commands) + "\n")
        self._append_indicator("commands", {"file": path, "count": len(commands)})
        return path
