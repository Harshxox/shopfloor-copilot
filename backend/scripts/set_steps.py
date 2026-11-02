"""Set the action + 'done when' text of every step of an SOP in one go (instead of editing in the UI).

Run from backend\\ with uvicorn running:   python scripts\\set_steps.py --sop 3
"""
import argparse

import requests

API = "http://localhost:8000/api"

STEPS = {
    1: ("Remove the enclosure from the plastic sleeve",
        "The enclosure is out of the plastic sleeve and held up; the sleeve is pushed aside"),
    2: ("Remove the top screw (USB-C end, silver stripe side)",
        "The single top screw near the silver stripe is fully out and held up to the camera"),
    3: ("Remove the top cap (USB-C end, silver stripe side)",
        "The top cap is off and the USB-C end next to the silver stripe is open"),
    4: ("Remove the bottom screw (end without the silver stripe)",
        "The single bottom screw, at the end away from the silver stripe, is fully out and held up to the camera"),
    5: ("Remove the bottom cap (end without the silver stripe)",
        "The bottom cap is off and the end away from the silver stripe is open"),
    6: ("Slide the inner PCB out of the housing",
        "The black PCB is fully out of the aluminium housing; PCB and empty housing are shown separately"),
}

ap = argparse.ArgumentParser()
ap.add_argument("--sop", type=int, required=True)
a = ap.parse_args()

steps = requests.get(f"{API}/sops/{a.sop}").json()["steps"]
if len(steps) != len(STEPS):
    raise SystemExit(f"SOP {a.sop} has {len(steps)} steps, expected {len(STEPS)}. Fix the step count first.")
for st in steps:
    action, done = STEPS[st["idx"]]
    r = requests.patch(f"{API}/sops/{a.sop}/steps/{st['id']}", json={"action": action, "expected_end_state": done})
    r.raise_for_status()
    print(f"{st['idx']}. {action}\n   done when: {done}")
print("\nAll steps updated. Refresh the Teach page to see them.")