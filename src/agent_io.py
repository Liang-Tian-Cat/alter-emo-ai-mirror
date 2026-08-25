# agent_io.py
import os
import json
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory_store import read_ndjson
from salience import DEFAULT_THRESHOLD, evaluate_salience

# 顶层目录（每个人格一个子目录）
OUT_DIR: str   = "agents"
AGENT_DIR: Optional[str] = None  # 由主程序设置（agents/<pseudonym>）

# -------------------------
# 基础 & 目录
# -------------------------
def ensure_dirs() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

def _paths(agent_dir: str) -> Dict[str, str]:
    """
    memory_stream 目录采用：NDJSON 为主、JSON 为兼容
    - nodes.ndjson                      节点元信息（含 source / emotion_tag / importance）
    - embeddings_event.ndjson           事件/语义向量
    - embeddings_emotion.ndjson         情绪向量
    - nodes.json / embeddings.json      旧版整文件格式（继续同步，便于你旧工具读取）
    """
    ms = os.path.join(agent_dir, "memory_stream")
    os.makedirs(ms, exist_ok=True)
    return {
        "nodes_nd":   os.path.join(ms, "nodes.ndjson"),
        "evt_nd":     os.path.join(ms, "embeddings_event.ndjson"),
        "emo_nd":     os.path.join(ms, "embeddings_emotion.ndjson"),
        # legacy
        "nodes_json": os.path.join(ms, "nodes.json"),
        "emb_json":   os.path.join(ms, "embeddings.json"),
    }

def _append_ndjson(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

# -------------------------
# meta
# -------------------------
def load_or_init_meta(meta_path: str, pseudonym: str) -> Dict[str, Any]:
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    else:
        meta = {"id": str(uuid.uuid4())}

    # 补默认字段（轻量）
    meta.setdefault("version", 1)
    meta.setdefault("created_at", datetime.utcnow().isoformat() + "Z")
    meta.setdefault("identity", {"pseudonym": pseudonym, "mbti": None})
    meta.setdefault("personality_seed", {})
    meta.setdefault("empathic_style", {
        "tone": [], "logic": "", "values": [], "boundaries": "", "example_phrases": [],
        "message_length": "", "sentence_rhythm": "", "reply_cadence": "",
        "recurring_vocabulary": [], "attribution": ""
    })
    meta.setdefault("model_info", {})
    # Consent is opt-in.  Older workspaces are preserved, while every new
    # persona starts paused until a client records an explicit grant.
    meta.setdefault("consent", {"status": False, "scope": "none", "updated_at": None})
    meta.setdefault("memory_paused", False)
    meta.setdefault("provenance", {"last_session_id": None, "sessions": []})
    return meta

def save_meta(
    meta_path: str,
    meta: Dict[str, Any],
    session_id: str,
    style: Dict[str, Any],
    seed: Dict[str, Any],
    model_chat: str,
    model_emb: str,
    mbti: Optional[str] = None,
) -> None:
    meta["provenance"]["last_session_id"] = session_id
    meta["provenance"]["sessions"].append(session_id)
    if mbti:
        meta["identity"]["mbti"] = mbti
    if seed:
        meta["personality_seed"] = seed
    if style:
        meta["empathic_style"] = style
    meta["model_info"] = {"chat": model_chat, "embed": model_emb}

    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

# -------------------------
# memory：保存节点 + 双通道向量（向后兼容）
# -------------------------
def save_memory_node_dual(
    agent_dir: str,
    text: str,
    summary: str,
    mtype: str,
    qid: Optional[str] = None,
    importance: int = 50,
    emotion_tag: Optional[Dict[str, Any]] = None,
    evt_vec: Optional[List[float]] = None,
    emo_vec: Optional[List[float]] = None,
    # NEW 可选字段
    source: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
    enforce_salience_gate: bool = True,
    salience_threshold: float = DEFAULT_THRESHOLD,
) -> Dict[str, Any]:
    """
    保存一个记忆节点到 nodes.ndjson，并把事件/情绪向量分别写到
    embeddings_event.ndjson / embeddings_emotion.ndjson。
    同时继续维护旧版 nodes.json / embeddings.json 的兼容写入。

    返回：带 id 的节点 dict（不含向量）。
    """
    ensure_dirs()
    os.makedirs(agent_dir, exist_ok=True)
    p = _paths(agent_dir)

    existing = read_ndjson(Path(p["nodes_nd"]))
    decision = evaluate_salience(
        text,
        emotion_tag=emotion_tag,
        importance=importance,
        existing_memories=existing,
        threshold=salience_threshold,
    )
    nid = str(uuid.uuid4())
    node: Dict[str, Any] = {
        "id": nid,
        "ts": time.time(),                 # 秒级时间戳
        "type": mtype,                     # 例如 main_answer / interviewer_main_q / followup_q / ...
        "qid": qid,                        # 可为空
        "content": text,                   # 原文
        "summary": summary,                # 简短摘要（如前缀 - Q: ...）
        "importance": int(importance),     # 0~100
        "emotion_tag": emotion_tag or {},  # {"emotion": "...", "tone": ["...","..."]}
        "salience": decision.to_dict(),
        "persisted": bool(decision.store or not enforce_salience_gate),
    }
    if source:
        # 例如 {"kind":"interview","session_id":"abc123","turn_index":5}
        node["source"] = source
    if extra:
        # 附加自定义字段，不覆盖已有 key
        for k, v in extra.items():
            if k not in node:
                node[k] = v

    # Low-salience turns remain available to the current session but do not
    # enter the long-term stream. The returned decision makes this observable.
    if enforce_salience_gate and not decision.store:
        return node

    # --- 新格式：逐行写入 ---
    _append_ndjson(p["nodes_nd"], node)
    if isinstance(evt_vec, list):
        _append_ndjson(p["evt_nd"], {"id": nid, "vec": evt_vec})
    if isinstance(emo_vec, list):
        _append_ndjson(p["emo_nd"], {"id": nid, "vec": emo_vec})

    # --- 兼容旧格式：整文件覆盖 ---
    # nodes.json（旧版一般不含 emotion_tag/source，这里保持兼容：去掉 emotion_tag）
    legacy_node = {k: v for k, v in node.items() if k not in ("emotion_tag",)}
    nodes_legacy: List[Dict[str, Any]] = []
    if os.path.exists(p["nodes_json"]):
        try:
            with open(p["nodes_json"], "r", encoding="utf-8") as f:
                nodes_legacy = json.load(f)
        except Exception:
            nodes_legacy = []
    nodes_legacy.append(legacy_node)
    with open(p["nodes_json"], "w", encoding="utf-8") as f:
        json.dump(nodes_legacy, f, ensure_ascii=False, indent=2)

    # embeddings.json（旧版只存事件向量）
    embs_legacy: List[Any] = []
    if os.path.exists(p["emb_json"]):
        try:
            with open(p["emb_json"], "r", encoding="utf-8") as f:
                embs_legacy = json.load(f)
        except Exception:
            embs_legacy = []
    # 旧格式里只追加事件向量（即使为 None 也占位以保持历史一致）
    embs_legacy.append(evt_vec if isinstance(evt_vec, list) else None)
    with open(p["emb_json"], "w", encoding="utf-8") as f:
        json.dump(embs_legacy, f, ensure_ascii=False, indent=2)

    return node

# -------------------------
# （可选）简单双通道检索工具 - 保留老接口名以便你现有代码调用
# -------------------------
def search_similar_nodes_dual(
    query_text: str,
    memory_cache: List[Dict[str, Any]],
    embed_fn,
    emo_tag_fn,
    cos_fn,
    w_evt: float = 0.6,
    w_emo: float = 0.4,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    """
    简单双通道相似度：事件(query_text) + 情绪(对 emotion+tone 做 embedding 更稳，这里保持兼容你的旧实现)。
    注意：这是一个通用小工具；你在业务脚本里有更完整的检索/筛选，可以不依赖它。
    """
    evt_q = embed_fn(query_text)

    # 情绪查询：优先 emotion+tone 拼接；若工具不支持，退回 emotion
    try:
        tag = emo_tag_fn(query_text) or {}
        emo_label = (tag.get("emotion") or "neutral").strip()
        tones = ",".join((tag.get("tone") or [])[:2]).strip(",")
        emo_text = f"{emo_label};{tones}" if tones else emo_label
    except Exception:
        emo_text = "neutral"
    emo_q = embed_fn(emo_text)

    scored: List[Dict[str, Any]] = []
    for n in memory_cache:
        evt_vec = n.get("evt_vec")
        emo_vec = n.get("emo_vec")

        s_evt = cos_fn(evt_q, evt_vec) if isinstance(evt_vec, list) else 0.0
        s_emo = cos_fn(emo_q, emo_vec) if isinstance(emo_vec, list) else 0.0
        score = w_evt * s_evt + w_emo * s_emo

        scored.append({
            **n,
            "score": float(score),
            "_s_evt": float(s_evt),
            "_s_emo": float(s_emo),
        })

    scored.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return scored[:top_k]
