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
from typing import Optional, Tuple, List, Iterable
from pathlib import Path

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

# Optional OpenCV + NumPy for scoring and multi-template matching
try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:
    cv2 = None  # type: ignore
    np = None  # type: ignore

# Supported image extensions for template files
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}


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


def gather_image_templates(
    single_image: Optional[str],
    images_dir: Optional[str],
    allow_dir_scan: bool,
) -> List[str]:
    """Collect a list of template image file paths to scan for.

    - Includes all files with common image extensions under `images_dir` (non-recursive)
      when `allow_dir_scan` is True and the directory exists.
    - Also includes `single_image` if provided and not already in the list.
    """
    templates: List[str] = []

    if allow_dir_scan and images_dir:
        p = Path(images_dir)
        if p.is_dir():
            for entry in sorted(p.iterdir()):
                if entry.is_file() and entry.suffix.lower() in IMAGE_EXTS:
                    templates.append(str(entry.resolve()))

    if single_image:
        sp = Path(single_image)
        if sp.suffix.lower() in IMAGE_EXTS and sp.is_file():
            try:
                resolved = str(sp.resolve())
            except Exception:
                resolved = str(sp)
            if resolved not in templates:
                templates.append(resolved)

    return templates


def dedupe_points(points: Iterable[Tuple[int, int]], min_dist: int = 6) -> List[Tuple[int, int]]:
    """Deduplicate points by skipping any that are within `min_dist` pixels of a prior point."""
    kept: List[Tuple[int, int]] = []
    for x, y in points:
        too_close = False
        for kx, ky in kept:
            if abs(kx - x) <= min_dist and abs(ky - y) <= min_dist:
                too_close = True
                break
        if not too_close:
            kept.append((x, y))
    return kept


def screenshot_bgr(region: Optional[Tuple[int, int, int, int]] = None):
    """Capture the screen (or region) and return as a BGR numpy array for OpenCV."""
    if cv2 is None or np is None:
        return None
    img = pg.screenshot(region=region)
    arr = np.array(img)  # RGB
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return bgr


def load_templates_cv(paths: List[str]):
    """Load template images as BGR arrays with metadata for matching."""
    if cv2 is None:
        return None
    templates = []
    for p in paths:
        try:
            t = cv2.imread(p, cv2.IMREAD_COLOR)
            if t is None:
                continue
            h, w = t.shape[:2]
            templates.append({"path": p, "name": Path(p).name, "img": t, "w": w, "h": h})
        except Exception:
            continue
    return templates


def match_all_templates_cv(
    screen_bgr,
    templates,
    confidence: float,
    region_offset: Tuple[int, int] = (0, 0),
):
    """Match all templates on the provided screenshot.

    Returns a list of dicts: {name, path, x, y, cx, cy, w, h, score}
    Coordinates are absolute screen coordinates, accounting for region offset.
    """
    if cv2 is None or np is None or screen_bgr is None or not templates:
        return []
    results = []
    for t in templates:
        tmpl = t["img"]
        w, h = t["w"], t["h"]
        try:
            res = cv2.matchTemplate(screen_bgr, tmpl, cv2.TM_CCOEFF_NORMED)
        except Exception:
            continue
        loc = np.where(res >= confidence)
        ys, xs = loc[0], loc[1]
        candidates = [
            (int(x), int(y), float(res[y, x]))
            for x, y in zip(xs.tolist(), ys.tolist())
        ]
        candidates.sort(key=lambda k: k[2], reverse=True)
        kept: List[Tuple[int, int, float]] = []
        for x, y, s in candidates:
            too_close = False
            for kx, ky, _ in kept:
                if abs(kx - x) <= max(6, w // 4) and abs(ky - y) <= max(6, h // 4):
                    too_close = True
                    break
            if not too_close:
                kept.append((x, y, s))

        offx, offy = region_offset
        for x, y, s in kept:
            cx = x + w // 2 + offx
            cy = y + h // 2 + offy
            results.append(
                {
                    "name": t["name"],
                    "path": t["path"],
                    "x": x + offx,
                    "y": y + offy,
                    "cx": cx,
                    "cy": cy,
                    "w": w,
                    "h": h,
                    "score": s,
                }
            )
    return results


def main():
    parser = argparse.ArgumentParser(description="Auto-Approve clicker (PyAutoGUI + OpenCV)")
    parser.add_argument("--image", "-i", default="approve.png", help="Path to a template image to find (also scans --images-dir)")
    parser.add_argument("--images-dir", default="images", help="Directory of images to scan and click when matched")
    parser.add_argument("--no-images-dir", action="store_true", help="Do not scan --images-dir; only use --image")
    parser.add_argument("--confidence", "-c", type=float, default=0.80, help="Match confidence [0.0-1.0] (needs OpenCV)")
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

    # Build list of templates to scan
    templates = gather_image_templates(
        single_image=args.image,
        images_dir=args.images_dir,
        allow_dir_scan=(not args.no_images_dir),
    )
    if templates:
        print(f"- Scanning {len(templates)} template(s)")
        if args.images_dir and not args.no_images_dir and Path(args.images_dir).is_dir():
            print(f"  (Includes images in '{args.images_dir}')")
        if args.debug:
            for t in templates:
                print(f"  - {t}")
    else:
        print("Warning: No templates to scan. Check --image or --images-dir.")

    # Inform if default/specified single image is missing (to avoid OpenCV WARN spam)
    if args.image:
        sp = Path(args.image)
        if sp.suffix.lower() in IMAGE_EXTS and not sp.is_file():
            print(f"Warning: template not found, skipping: {args.image}")

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

                # Accumulate all hit centers this iteration (dedup close points)
                hit_points: List[Tuple[int, int]] = []
                printed_any = False
                if cv2 is not None and np is not None and templates:
                    # Preload templates once if available
                    try:
                        cv_templates
                    except NameError:
                        cv_templates = None  # type: ignore
                    if not cv_templates:
                        cv_templates = load_templates_cv(templates)
                    # Capture screenshot once per loop
                    offx, offy = 0, 0
                    if region:
                        offx, offy, _, _ = region
                    scr = screenshot_bgr(region=region)
                    matches = match_all_templates_cv(
                        screen_bgr=scr,
                        templates=cv_templates,
                        confidence=args.confidence,
                        region_offset=(offx, offy),
                    )
                    for m in matches:
                        print(f"Match: {m['name']} @ ({m['cx']},{m['cy']}) score={m['score']:.3f}")
                        printed_any = True
                        hit_points.append((m["cx"], m["cy"]))
                else:
                    for tmpl in templates:
                        try:
                            found = list(
                                pg.locateAllOnScreen(
                                    tmpl,
                                    confidence=args.confidence,
                                    region=region,
                                )
                            )
                        except TypeError:
                            # If confidence not supported (OpenCV missing), fall back to single locate
                            box = pg.locateOnScreen(tmpl, region=region)
                            found = [box] if box else []
                        for b in found:
                            if not b:
                                continue
                            cx, cy = pg.center(b)
                            print(f"Match: {Path(tmpl).name} @ ({int(cx)},{int(cy)})")
                            printed_any = True
                            hit_points.append((int(cx), int(cy)))

                # Deduplicate near-overlapping points (e.g., similar templates)
                hit_points = dedupe_points(hit_points, min_dist=6)

                for (x, y) in hit_points:
                    orig_x, orig_y = pg.position()
                    if args.pre_click_delay > 0:
                        time.sleep(args.pre_click_delay)
                    if args.debug and not printed_any:
                        print(f"Found at ({x}, {y}), clicking {args.clicks}x with '{args.button}'")
                    pg.click(x=x, y=y, clicks=max(1, args.clicks), button=args.button)
                    if args.after_click > 0:
                        time.sleep(args.after_click)
                    if not args.no_restore_pointer:
                        try:
                            pg.moveTo(orig_x, orig_y, duration=max(0.0, args.restore_duration))
                        except Exception as move_err:
                            if args.debug:
                                print(f"Restore pointer failed: {move_err}")
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
