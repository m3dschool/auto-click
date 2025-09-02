Auto-Approve (PyAutoGUI + OpenCV)

What it does
- Finds an on-screen button by image template (approve.png by default) and clicks it when visible
- Toggle on/off with Ctrl+Alt+A, quit with Ctrl+Alt+Q
- Optional: restrict by active window title and/or a screen region

Setup (Windows/PowerShell)
1) Create venv and install deps
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt

2) Place a small, crisp approve.png in this folder (ideally tightly cropped to the button text/icon)

Run
   python auto_approve.py

Useful flags
- Image path:       --image approve.png
- Confidence:       --confidence 0.85   (requires OpenCV; included)
- Search interval:  --interval 0.2
- After click wait: --after-click 0.3
- Region:           --region "left,top,width,height"
- Window filter:    --window-title "Your App Name"
- Hotkeys:          --toggle-hotkey "ctrl+alt+a"  --quit-hotkey "ctrl+alt+q"
- Debug logs:       --debug

Examples
- Only when VS Code is active:
  python auto_approve.py --window-title "Visual Studio Code" --confidence 0.9

- Search only top-left quarter of a 1920x1080 screen:
  python auto_approve.py --region "0,0,960,540"

Notes
- On Windows, global hotkeys via the `keyboard` lib may require running the terminal as Administrator.
- PyAutoGUI failsafe is enabled: move mouse to the top-left corner to immediately stop with an exception.
- For web-only buttons, a userscript (e.g., Tampermonkey) using DOM selectors is usually more robust than image search.

Troubleshooting
- Error: "PyAutoGUI was unable to import pyscreeze / Pillow":
  - Cause: Pillow missing or unsupported version.
  - Fix: Activate your venv and run `pip install pillow` (requirements now include it). On Python 3.13+, ensure a recent Pillow (11.x+).

Safety
- Limit scope via --window-title or --region to avoid accidental clicks.
- Be careful when automating approvals with security/financial impact.
