import os
import json
import socket
import platform
import ipaddress
import concurrent.futures
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

    def __init__(self, sandbox_dir: str, report_dir: str | None = None):
        # Where sample files live / are processed
        self.sandbox_dir = sandbox_dir
        os.makedirs(self.sandbox_dir, exist_ok=True)

        # Centralized report directory (defaults to Windows path or env override)
        self.report_dir = report_dir or os.getenv("REPORT_DIR") or r"C:\\Users\\user\\report"
        try:
            os.makedirs(self.report_dir, exist_ok=True)
        except Exception:
            # Fallback to sandbox dir if the preferred path cannot be created
            self.report_dir = self.sandbox_dir

        # Indicators log location in report directory
        self.indicator_log = os.path.join(self.report_dir, "indicators.json")

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
        
        inventory_path = os.path.join(self.report_dir, "inventory.json")
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
        path = os.path.join(self.report_dir, "commands_attempted.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(commands) + "\n")
        self._append_indicator("commands", {"file": path, "count": len(commands)})
        return path
    
    def scan_network_hosts(self, subnet: str = None, ports: list = None) -> dict:
        """Scan local network for active hosts on common ports.
        
        Args:
            subnet: CIDR notation (e.g., "192.168.1.0/24"), defaults to local subnet
            ports: List of ports to scan, defaults to [445, 139, 3389, 22, 80, 443]
        """
        if ports is None:
            ports = [445, 139, 3389, 22, 80, 443]  # SMB, RDP, SSH, HTTP, HTTPS
        
        # Get local subnet if not provided
        if subnet is None:
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                # Assume /24 subnet
                ip_parts = local_ip.split('.')
                subnet = f"{'.'.join(ip_parts[:3])}.0/24"
            except Exception:
                subnet = "192.168.1.0/24"  # fallback
        
        scan_results = {"subnet": subnet, "ports_scanned": ports, "hosts_found": []}
        
        def scan_host_port(host_ip, port):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    result = s.connect_ex((str(host_ip), port))
                    if result == 0:
                        return {"ip": str(host_ip), "port": port, "status": "open"}
            except Exception:
                pass
            return None
        
        try:
            network = ipaddress.ip_network(subnet, strict=False)
            hosts_to_scan = list(network.hosts())[:50]  # Limit to first 50 hosts
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for host in hosts_to_scan:
                    for port in ports:
                        futures.append(executor.submit(scan_host_port, host, port))
                
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        scan_results["hosts_found"].append(result)
            
            scan_results["status"] = "completed"
            scan_results["total_hosts_scanned"] = len(hosts_to_scan)
            scan_results["active_targets"] = len(scan_results["hosts_found"])
            
        except Exception as e:
            scan_results["status"] = "error"
            scan_results["error"] = str(e)
        
        # Log scan results to centralized report directory
        scan_log = os.path.join(self.report_dir, "network_scan.json")
        with open(scan_log, "w", encoding="utf-8") as f:
            json.dump(scan_results, f, indent=2)
        
        self._append_indicator("network_scan", scan_results)
        return scan_results

