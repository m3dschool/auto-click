"""
Auto-Approve clicker using PyAutoGUI + OpenCV.

- Looks for a template image (default: approve.png) on screen
- Clicks the center when found
- Toggle on/off with a global hotkey (default: Ctrl+Alt+A)
- Quit with a global hotkey (default: Ctrl+Alt+Q)
- Optional: restrict to active window title and/or a screen region

Notes
- Install deps: pip install -r requirements.txt
- On Windows, global hotkeys via the `keyboard` package may require running the
  script from an elevated (Administrator) terminal.
- PyAutoGUI failsafe is enabled: moving the mouse to the top-left corner stops
  the script by raising an exception.
"""

from __future__ import annotations

import argparse
import sys
import time
import threading
from typing import Optional, Tuple

try:
    import pyautogui as pg
except Exception as e:  # pragma: no cover
    print("Failed to import pyautogui. Install dependencies first.")
    raise

# Pillow is required by pyscreeze (used under the hood by PyAutoGUI locateOnScreen)
try:
    from PIL import Image  # noqa: F401
except Exception as e:
    print("Error: Pillow is required for screen image search.")
    print("Fix: activate your venv and run: pip install pillow")
    if sys.version_info >= (3, 13):
        print("Note: Use a recent Pillow version (11.x+) for Python 3.13.")
    sys.exit(1)

try:
    import keyboard  # global hotkeys
except Exception as e:  # pragma: no cover
    print("Failed to import keyboard. Install dependencies first.")
    raise

# Optional window filter support; only used if --window-title provided
try:
    import pygetwindow as gw  # type: ignore
except Exception:
    gw = None  # Optional dependency


def parse_region(region_str: Optional[str]) -> Optional[Tuple[int, int, int, int]]:
    if not region_str:
        return None
    try:
        parts = [int(p.strip()) for p in region_str.split(",")]
        if len(parts) != 4:
            raise ValueError
        left, top, width, height = parts
        if width <= 0 or height <= 0:
            raise ValueError
        return (left, top, width, height)
    except Exception:
        print("Invalid --region. Expected 'left,top,width,height' with positive ints.")
        sys.exit(2)


def active_window_matches(substr: Optional[str]) -> bool:
    if not substr:
        return True
    if gw is None:
        # If user requested window filtering but dependency missing, skip safely
        return True
    try:
        win = gw.getActiveWindow()
        if not win:
            return False
        title = (win.title or "").lower()
        return substr.lower() in title
    except Exception:
        return True


def main():
    parser = argparse.ArgumentParser(description="Auto-Approve clicker (PyAutoGUI + OpenCV)")
    parser.add_argument("--image", "-i", default="approve.png", help="Path to the template image to find")
    parser.add_argument("--confidence", "-c", type=float, default=0.85, help="Match confidence [0.0-1.0] (needs OpenCV)")
    parser.add_argument("--interval", type=float, default=0.2, help="Search interval in seconds")
    parser.add_argument("--pre-click-delay", type=float, default=0.0, help="Delay before clicking, in seconds")
    parser.add_argument("--after-click", type=float, default=0.5, help="Sleep after clicking, in seconds")
    parser.add_argument("--region", help="Limit search region as left,top,width,height")
    parser.add_argument("--window-title", help="Only click when the active window title contains this substring")
    parser.add_argument("--button", default="left", choices=["left", "right", "middle"], help="Mouse button to click")
    parser.add_argument("--clicks", type=int, default=1, help="Number of clicks when found")
    parser.add_argument("--toggle-hotkey", default="ctrl+alt+a", help="Hotkey to toggle running on/off")
    parser.add_argument("--quit-hotkey", default="ctrl+alt+q", help="Hotkey to quit the script")
    parser.add_argument("--no-detect-timeout", type=float, default=600.0, help="Auto-stop if no detection for N seconds (0 disables)")
    parser.add_argument("--no-restore-pointer", action="store_true", help="Do not restore mouse to original position after clicking")
    parser.add_argument("--restore-duration", type=float, default=0.0, help="Seconds to animate pointer restore (0 = instant)")
    parser.add_argument("--debug", action="store_true", help="Verbose errors and state changes")

    args = parser.parse_args()

    region = parse_region(args.region)

    # PyAutoGUI safety and tuning
    pg.FAILSAFE = True
    pg.PAUSE = 0.05

    running = {"value": True}
    exit_evt = threading.Event()

    def toggle():
        running["value"] = not running["value"]
        print(f"Auto-Approve {'resumed' if running['value'] else 'paused'}.")

    def quit_program():
        print("Quit requested. Exiting...")
        exit_evt.set()

    try:
        keyboard.add_hotkey(args.toggle_hotkey, toggle)
        keyboard.add_hotkey(args.quit_hotkey, quit_program)
    except Exception as e:
        print("Warning: failed to register hotkeys. Try running as Administrator on Windows.")
        if args.debug:
            print(repr(e))

    print("Auto-Approve running.")
    print(f"- Toggle: {args.toggle_hotkey} | Quit: {args.quit_hotkey}")
    if args.window_title:
        print(f"- Restricting clicks to active window containing: '{args.window_title}'")
        if gw is None:
            print("  (Install 'pygetwindow' for reliable window checks; included in requirements.txt)")
    if region:
        l, t, w, h = region
        print(f"- Limiting search region to: left={l}, top={t}, width={w}, height={h}")
    if args.no_detect_timeout and args.no_detect_timeout > 0:
        print(f"- Auto-stop if no detections for {int(args.no_detect_timeout)}s")
    if not args.no_restore_pointer:
        print("- Restoring mouse to original position after click")
        if args.restore_duration:
            print(f"  (Restore animation: {args.restore_duration}s)")

    last_error_ts = 0.0
    last_detection_ts = time.time()

    while not exit_evt.is_set():
        if running["value"]:
            # Auto-stop if no detection within timeout window
            if args.no_detect_timeout and args.no_detect_timeout > 0:
                if (time.time() - last_detection_ts) > args.no_detect_timeout:
                    print("No detections within timeout window. Stopping.")
                    quit_program()
                    break
            try:
                if not active_window_matches(args.window_title):
                    time.sleep(args.interval)
                    continue

                box = pg.locateOnScreen(
                    args.image,
                    confidence=args.confidence,
                    region=region,
                )
                if box:
                    x, y = pg.center(box)
                    orig_x, orig_y = pg.position()
                    if args.pre_click_delay > 0:
                        time.sleep(args.pre_click_delay)
                    if args.debug:
                        print(f"Found at ({x}, {y}), clicking {args.clicks}x with '{args.button}'")
                    pg.click(x=x, y=y, clicks=max(1, args.clicks), button=args.button)
                    # Post-click wait
                    if args.after_click > 0:
                        time.sleep(args.after_click)
                    # Restore pointer to original position
                    if not args.no_restore_pointer:
                        try:
                            pg.moveTo(orig_x, orig_y, duration=max(0.0, args.restore_duration))
                        except Exception as move_err:
                            if args.debug:
                                print(f"Restore pointer failed: {move_err}")
                    # Mark detection time
                    last_detection_ts = time.time()
            except KeyboardInterrupt:
                quit_program()
                break
            except Exception as e:
                # Commonly raised if OpenCV missing when using confidence, or failsafe triggered
                now = time.time()
                if args.debug or (now - last_error_ts) > 5.0:
                    print(f"Warning: locate/click error: {e.__class__.__name__}: {e}")
                    last_error_ts = now
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
