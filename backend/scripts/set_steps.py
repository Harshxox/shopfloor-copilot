"""Reshape an SOP to the final 4-step procedure: every step has a VISIBLE end state.

A loosened screw looks the same as an untouched one, so 'loosen screw' + 'remove cap' are merged
into one step each. Deletes the screw-only steps (if present), renumbers, and sets exact text.

Run from backend\\ with uvicorn running:   python scripts\\set_steps.py --sop 3
"""
import argparse

import requests

API = "http://localhost:8000/api"

FINAL = [
    ("Remove the enclosure from the plastic sleeve",
     "The enclosure is out of the plastic sleeve and held up; the sleeve is pushed aside"),
    ("Unscrew and remove the top cap (USB-C end, silver stripe side)",
     "The top cap is fully off and the USB-C end next to the silver stripe is open"),
    ("Unscrew and remove the bottom cap (end without the silver stripe)",
     "The bottom cap is fully off and the end away from the silver stripe is open"),
    ("Slide the inner PCB out of the housing",
     "The black PCB is fully out of the aluminium housing; PCB and empty housing are shown separately"),
]

ap = argparse.ArgumentParser()
ap.add_argument("--sop", type=int, required=True)
a = ap.parse_args()

steps = requests.get(f"{API}/sops/{a.sop}").json()["steps"]
# remove screw-only steps (an action about a screw that isn't also about the cap)
for st in steps:
    act = st["action"].lower()
    if "screw" in act and "cap" not in act:
        requests.delete(f"{API}/sops/{a.sop}/steps/{st['id']}").raise_for_status()
        print(f"deleted step: {st['action']}")
steps = requests.get(f"{API}/sops/{a.sop}").json()["steps"]
if len(steps) != len(FINAL):
    raise SystemExit(f"SOP {a.sop} now has {len(steps)} steps, expected {len(FINAL)}: "
                     f"{[s['action'] for s in steps]}")
for st, (action, done) in zip(steps, FINAL):
    requests.patch(f"{API}/sops/{a.sop}/steps/{st['id']}",
                   json={"action": action, "expected_end_state": done, "critical": st["idx"] > 1}).raise_for_status()
    print(f"{st['idx']}. {action}\n   done when: {done}")
print("\nSOP reshaped to 4 steps. Refresh the Teach page to see it.")
