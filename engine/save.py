import json
import os

SAVE_DIR = os.path.join(os.path.expanduser("~"), ".linuxquest")
SAVE_FILE = os.path.join(SAVE_DIR, "save.json")


def load():
    if not os.path.exists(SAVE_FILE):
        return {"completed": [], "current_mission": 0, "score": 0, "hints_used": 0}
    try:
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"completed": [], "current_mission": 0, "score": 0, "hints_used": 0}


def save(state):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(SAVE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def reset():
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)
