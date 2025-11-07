"""Minimal, cross-platform environment bootstrapper.

Creates a local virtual environment (if missing), installs requirements,
then re-executes the current script from that environment so imports succeed.

Only standard library is used here to avoid ImportError before bootstrapping.
"""
from __future__ import annotations

import os
import sys
import subprocess
import shutil
import venv
from pathlib import Path


def _venv_paths(base: Path) -> dict:
    """Return important paths for a venv rooted at base."""
    if os.name == 'nt':
        bin_dir = base / 'Scripts'
    else:
        bin_dir = base / 'bin'
    py = bin_dir / ('python.exe' if os.name == 'nt' else 'python')
    pip = bin_dir / ('pip.exe' if os.name == 'nt' else 'pip')
    return {'root': base, 'bin': bin_dir, 'python': py, 'pip': pip}


def _find_project_root(start: Path) -> Path:
    """Heuristic to find repo root: prefer directory containing requirements.txt; else parent of py_simple."""
    # Try current dir and parents for requirements.txt
    cur = start
    for p in [cur, *cur.parents]:
        if (p / 'requirements.txt').exists():
            return p
    # Fallback: parent of py_simple folder
    if start.name == 'py_simple':
        return start.parent
    return start


def ensure_venv_and_requirements(env_name: str = '.venv', force: bool = False) -> None:
    """Ensure a venv exists and required packages are installed, then re-exec into it if needed.

    Set AGENT_AUTO_VENV=0 to disable. Set AGENT_BOOTSTRAPPED=1 to prevent recursion.
    """
    if os.environ.get('AGENT_AUTO_VENV', '1').strip().lower() in ('0', 'false', 'no'):  # opt-out
        return

    # Avoid infinite recursion when we re-exec into the venv interpreter
    if os.environ.get('AGENT_BOOTSTRAPPED') == '1' and not force:
        return

    here = Path(__file__).resolve().parent
    project_root = _find_project_root(here)
    venv_dir = project_root / env_name
    vpaths = _venv_paths(venv_dir)

    # Determine which requirements file to use
    req = None
    for cand in [here / 'requirements.txt', project_root / 'requirements.txt']:
        if cand.exists():
            req = cand
            break

    # Create venv if missing
    if not venv_dir.exists():
        print(f"[bootstrap] Creating venv at {venv_dir}")
        venv.create(str(venv_dir), with_pip=True, clear=False, symlinks=True)

    # If we're not already using this venv's interpreter, re-exec after installs
    in_same_interpreter = Path(sys.executable).resolve() == vpaths['python'].resolve()

    # Install or upgrade pip and requirements
    if req is not None:
        print(f"[bootstrap] Installing requirements from {req}")
        # Upgrade pip first (best effort)
        try:
            subprocess.run([str(vpaths['python']), '-m', 'pip', 'install', '--upgrade', 'pip'], check=False)
        except Exception:
            pass
        # Install requirements
        subprocess.run([str(vpaths['python']), '-m', 'pip', 'install', '-r', str(req)], check=True)
    else:
        print("[bootstrap] No requirements.txt found; skipping dependency install")

    if not in_same_interpreter:
        # Re-exec current script with same args under the venv's python
        print(f"[bootstrap] Re-executing under {vpaths['python']}")
        os.environ['AGENT_BOOTSTRAPPED'] = '1'
        os.execv(str(vpaths['python']), [str(vpaths['python']), *sys.argv])
