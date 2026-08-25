import os
import json
import uuid

INTERVIEW_OUTPUT = "interview_output"

# === 加载最新 session_id ===
with open(os.path.join(INTERVIEW_OUTPUT, "last_session.json")) as f:
    session_id = json.load(f)["session_id"]

# === 加载本次反射数据
reflection_path = os.path.join(INTERVIEW_OUTPUT, f"reflection_{session_id}.json")
with open(reflection_path, "r", encoding="utf-8") as f:
    reflection_data = json.load(f)
    reflection = reflection_data.get("reflection", {})

# === 获取 agent 名称
raw_name = reflection.get("name", "").strip()
if raw_name == "":
    raw_name = f"agent_{uuid.uuid4().hex[:6]}"

AGENT_NAME = raw_name.replace(" ", "_")
AGENT_DIR = os.path.join("agents", AGENT_NAME)
MEMORY_DIR = os.path.join(AGENT_DIR, "memory_stream")
os.makedirs(MEMORY_DIR, exist_ok=True)

print(f"✅ Using agent name: {AGENT_NAME}")

# === 生成 scratch.json
scratch = {
    "first_name": reflection.get("name"),
    "traits": reflection.get("traits", ["reflective"]),
    "values": reflection.get("values", ["empathy"]),
    "summary": reflection.get("summary", ""),
    "origin_reflection": reflection
}
with open(os.path.join(AGENT_DIR, "scratch.json"), "w", encoding="utf-8") as f:
    json.dump(scratch, f, indent=2, ensure_ascii=False)

# === 生成 meta.json
meta = {"id": str(uuid.uuid4())}
with open(os.path.join(AGENT_DIR, "meta.json"), "w") as f:
    json.dump(meta, f, indent=2)

# === 加载 memory_nodes
nodes_path = os.path.join(INTERVIEW_OUTPUT, f"memory_nodes_{session_id}.json")
with open(nodes_path, "r", encoding="utf-8") as f:
    nodes = json.load(f)

# === 加载 embeddings
embedding_path = os.path.join(INTERVIEW_OUTPUT, f"interview_embeddings_{session_id}.json")
with open(embedding_path, "r", encoding="utf-8") as f:
    raw_embeddings = json.load(f)

embedding_dict = {item["text"]: item["embedding"] for item in raw_embeddings}

# === 保存 nodes.json
with open(os.path.join(MEMORY_DIR, "nodes.json"), "w", encoding="utf-8") as f:
    json.dump(nodes, f, indent=2, ensure_ascii=False)

# === 保存 embeddings.json
with open(os.path.join(MEMORY_DIR, "embeddings.json"), "w") as f:
    json.dump(embedding_dict, f, separators=(",", ":"))

print(f"✅ Agent saved at: {AGENT_DIR}")
