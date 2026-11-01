"""Quick check: does SAM 3.1 see our still images at all?

Run from backend\\ :  python sam_image_test.py ..\\data\\sops\\1\\step_2.jpg hand person screwdriver
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.services import meta_client  # noqa: E402

img = Path(sys.argv[1])
for phrase in sys.argv[2:] or ["hand"]:
    boxes = meta_client.sam_image(img, phrase)
    print(f"'{phrase}': {len(boxes)} match(es) {boxes[:2]}")
    if not boxes:
        print(meta_client.last_sam_raw[:400])
