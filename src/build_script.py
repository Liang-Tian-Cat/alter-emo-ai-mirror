import json

def load_pool(path="mbti_pool.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def build_script_from_mbti_with_pool(mbti: str, pool: dict, n_per_axis=1, n_general=2):
    mbti = mbti.upper()
    axes = [
        ("I" if "I" in mbti else "E"),
        ("N" if "N" in mbti else "S"),
        ("T" if "T" in mbti else "F"),
        ("J" if "J" in mbti else "P"),
    ]
    script = []
    for axis in axes:
        script += pool.get(axis, [])[:n_per_axis]
    script += pool.get("GEN", [])[:n_general]
    return script