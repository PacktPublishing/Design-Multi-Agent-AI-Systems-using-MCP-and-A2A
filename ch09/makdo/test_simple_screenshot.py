#!/usr/bin/env python3
"""
Simplified screenshot test - avoiding System Events accessibility issues
"""

import time
import subprocess
import pyautogui
from pathlib import Path
from datetime import datetime


def activate_slack_simple():
    """Activate Slack using simple AppleScript (no System Events)"""
    print("=" * 60)
    print("Activating Slack (simple method)")
    print("=" * 60)

    try:
        # Simple activation - doesn't require accessibility permissions
        result = subprocess.run(
            ["osascript", "-e", 'tell application "Slack" to activate'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            print("✅ Slack activation command sent")
            return True
        else:
            print(f"❌ Activation failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_screenshot_pyautogui(name):
    """Take screenshot using pyautogui"""
    try:
        test_dir = Path("test_screenshots")
        test_dir.mkdir(exist_ok=True)

        screenshot = pyautogui.screenshot()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = test_dir / f"{name}_{timestamp}.png"
        screenshot.save(filepath)

        print(f"✅ Screenshot saved: {filepath}")
        print(f"   Size: {screenshot.size}")
        return filepath

    except Exception as e:
        print(f"❌ Screenshot failed: {e}")
        return None


def test_screenshot_native(name):
    """Take screenshot using macOS native screencapture command"""
    try:
        test_dir = Path("test_screenshots")
        test_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = test_dir / f"{name}_{timestamp}.png"

        # -x: no sound
        # -C: capture cursor
        result = subprocess.run(
            ["screencapture", "-x", "-C", str(filepath)],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            print(f"✅ Native screenshot saved: {filepath}")
            return filepath
        else:
            print(f"❌ Native screenshot failed: {result.stderr}")
            return None

    except Exception as e:
        print(f"❌ Native screenshot failed: {e}")
        return None


def main():
    print("\n🔍 Simplified Slack Screenshot Test")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)
    print("\nIMPORTANT: Make sure Slack desktop app is running!")
    print("          (Not browser version)")
    print("=" * 60)

    # Test 1: Take baseline screenshot
    print("\n1. Taking baseline screenshot (before activation)...")
    test_screenshot_pyautogui("01_baseline")
    time.sleep(1)

    # Test 2: Activate Slack and wait
    print("\n2. Activating Slack...")
    if activate_slack_simple():
        print("   Waiting 3 seconds for window to come to front...")
        time.sleep(3)

        # Test 3: Take screenshot with pyautogui
        print("\n3. Taking screenshot with pyautogui...")
        test_screenshot_pyautogui("02_after_activation_pyautogui")
        time.sleep(1)

        # Test 4: Take screenshot with native command
        print("\n4. Taking screenshot with native screencapture...")
        test_screenshot_native("03_after_activation_native")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    print("\nCheck test_screenshots/ directory:")
    print("  - 01_baseline_*.png          = Before Slack activation")
    print("  - 02_after_activation_*.png  = After Slack activation (pyautogui)")
    print("  - 03_after_activation_*.png  = After Slack activation (native)")
    print("\nOpen these files and check if Slack window is visible!")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    exit(main())
