#!/usr/bin/env python3
"""
Test script to validate Slack screenshot capture on macOS
"""

import time
import subprocess
import pyautogui
from pathlib import Path
from datetime import datetime


def test_slack_activation():
    """Test if we can activate Slack application"""
    print("=" * 60)
    print("TEST 1: Slack Activation")
    print("=" * 60)

    try:
        # Get list of running applications
        result = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to get name of (every process whose background only is false)'],
            capture_output=True,
            text=True,
            timeout=10
        )

        print(f"Running applications: {result.stdout[:200]}...")

        # Check if Slack is in the list
        if "Slack" in result.stdout:
            print("✅ Slack is running")
        else:
            print("⚠️  Slack not found in running applications")
            print("   Please start Slack desktop app")
            return False

        # Try to activate Slack
        print("\nAttempting to activate Slack...")
        activate_result = subprocess.run(
            ["osascript", "-e", 'tell application "Slack" to activate'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if activate_result.returncode == 0:
            print("✅ Slack activation command succeeded")
            time.sleep(2)  # Wait for window to come to front
            return True
        else:
            print(f"❌ Slack activation failed: {activate_result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_screenshot_capture():
    """Test screenshot capture"""
    print("\n" + "=" * 60)
    print("TEST 2: Screenshot Capture")
    print("=" * 60)

    try:
        # Create test directory
        test_dir = Path("test_screenshots")
        test_dir.mkdir(exist_ok=True)

        print("Taking full screenshot...")
        screenshot = pyautogui.screenshot()

        # Save screenshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = test_dir / f"test_fullscreen_{timestamp}.png"
        screenshot.save(filepath)

        print(f"✅ Screenshot saved: {filepath}")
        print(f"   Size: {screenshot.size}")

        # Get screenshot file size
        file_size = filepath.stat().st_size
        print(f"   File size: {file_size:,} bytes")

        if file_size < 1000:
            print("⚠️  File size is very small - might be blank")
            return False

        return True

    except Exception as e:
        print(f"❌ Screenshot capture failed: {e}")
        return False


def test_window_list():
    """Get list of visible windows"""
    print("\n" + "=" * 60)
    print("TEST 3: Window List")
    print("=" * 60)

    try:
        # Get window information using different approach
        result = subprocess.run([
            "osascript", "-e",
            '''
            tell application "System Events"
                set appList to name of every process whose visible is true
                return appList
            end tell
            '''
        ], capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            apps = result.stdout.strip().split(", ")
            print("Visible applications:")
            for app in apps:
                print(f"  - {app}")

            return "Slack" in apps
        else:
            print(f"❌ Failed to get window list: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_slack_window_specific():
    """Try to bring specific Slack window to front"""
    print("\n" + "=" * 60)
    print("TEST 4: Slack Window-Specific Activation")
    print("=" * 60)

    try:
        # More aggressive window activation
        script = '''
        tell application "Slack"
            activate
            tell application "System Events"
                tell process "Slack"
                    set frontmost to true
                    perform action "AXRaise" of window 1
                end tell
            end tell
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            print("✅ Window-specific activation succeeded")
            time.sleep(3)  # Wait longer for window to come to front

            # Take screenshot
            test_dir = Path("test_screenshots")
            test_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = test_dir / f"test_slack_focused_{timestamp}.png"

            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            print(f"✅ Screenshot saved: {filepath}")
            print(f"   Check if this shows Slack window!")

            return True
        else:
            print(f"❌ Window activation failed: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n🔍 Slack Screenshot Validation Tests")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {}

    # Test 1: Window list
    results["window_list"] = test_window_list()
    time.sleep(1)

    # Test 2: Slack activation
    results["slack_activation"] = test_slack_activation()
    time.sleep(1)

    # Test 3: Basic screenshot
    results["screenshot_capture"] = test_screenshot_capture()
    time.sleep(1)

    # Test 4: Window-specific activation and screenshot
    results["window_specific"] = test_slack_window_specific()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:.<40} {status}")

    print("\n" + "=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print("1. Check test_screenshots/ directory for captured images")
    print("2. Verify if 'test_slack_focused_*.png' shows Slack window")
    print("3. If not showing Slack, may need to:")
    print("   - Ensure Slack is in desktop app (not browser)")
    print("   - Disable any window manager shortcuts")
    print("   - Try clicking on Slack manually after activation")
    print("=" * 60)

    all_passed = all(results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit(main())
