#!/usr/bin/env python3
"""
Test script for the ransom window.
Run this to see the ransom window in action.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ransom_window import show_ransom_window

if __name__ == "__main__":
    print("=" * 60)
    print("RANSOM WINDOW TEST")
    print("=" * 60)
    print("\nThis will display an unclosable fullscreen ransom window.")
    print("Features:")
    print("  ✓ Countdown timer (48 hours)")
    print("  ✓ Animated GIF from Tenor")
    print("  ✓ Unclosable (Alt+F4, ESC disabled)")
    print("  ✓ Fullscreen & always on top")
    print("\nTo force close for testing:")
    print("  - Kill the Python process from another terminal")
    print("  - Use task manager to end process")
    print("  - Restart your system")
    print("\n" + "=" * 60)
    
    input("\nPress ENTER to launch the ransom window...")
    
    print("\n[TEST] Launching ransom window...")
    print("[TEST] Window will appear in fullscreen mode")
    print("[TEST] Timer set to 48 hours countdown")
    
    # Launch the window (blocking mode for testing)
    show_ransom_window(hours=48, blocking=True)
