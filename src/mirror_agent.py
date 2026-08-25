# mirror_agent.py
# Mirror Persona Chat: continue dialog with a person's "mirror" built from prior interviews.
# - Reads empathic_style from meta/sessions; four-signal retrieval restores narrative context.
# - interlocutor=="self": write user & mirror turns into memory_stream; else only mirror_sessions/.
# - NEW:
#   * Style prompt imitates speaking style (no example_phrases).
#   * Yes/No detection → concise, no advice.
#   * Context window: after picks, load local conversation window (mirror + interview).
#   * Reflection plan + constrained behavior policy before final response generation.
#   * Temp-cache for non-self sessions (no main memory pollution).
#   * Question-aware retrieval: prompt nodes are included only when the query is a question.
#   * Event embeddings for self: user_vec = prev_mirror + user; mirror_vec = user + reply.

from __future__ import annotations

import os
import re
import json
import time
import uuid
import argparse
from typing import Any, Dict, List

import numpy as np

# ---- Reuse your IO helpers (unchanged) ----
from agent_io import (
    load_or_init_meta,
    save_meta,  # noqa
    save_memory_node_dual,
    OUT_DIR,
    AGENT_DIR,  # noqa
    ensure_dirs,
)
from memory_retrieval import DEFAULT_WEIGHTS, score_candidate
from response_policy import (
    fallback_response_plan,
    normalize_response_plan,
    response_instruction,
)
from runtime_config import create_openai_client, load_settings

# =========================
# Environment & OpenAI Init
# =========================
cfg = load_settings()
MODEL_CHAT = cfg["CHAT_MODEL"]
MODEL_EMB = cfg["EMB_MODEL"]
client = None


def get_client():
    global client
    if client is None:
        client = create_openai_client(cfg)
    return client

# =========================
# Globals & Retrieval Params
# =========================
memory_cache: List[Dict[str, Any]] = []  # in-process extras (temp nodes etc.)

TOP_K = 3
REL_MIN_SCORE = 0.36
REL_MIN_EVT   = 0.25
DELTA_BAND    = 0.10

RETRIEVAL_WEIGHTS = DEFAULT_WEIGHTS

# 默认上下文窗口（前后各 win 条），可用 CLI --ctxwin 覆盖
WIN_CTX_DEFAULT = 2

# 问句类节点类型
PROMPT_MTYPES = {"interviewer_main_q", "followup_q"}

# =========================
# GPT & Embedding helpers
# =========================
def call_gpt(
    prompt: str,
    sys: str = "You are a warm, concise Chinese assistant.",
    temperature: float = 0.3,
    json_only: bool = False
) -> str:
    return get_client().chat.completions.create(
        model=MODEL_CHAT,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": prompt}],
        temperature=temperature,
        **({"response_format": {"type": "json_object"}} if json_only else {})
    ).choices[0].message.content.strip()

def get_embedding(text: str) -> List[float]:
    return get_client().embeddings.create(model=MODEL_EMB, input=text).data[0].embedding

def cosine(a: List[float], b: List[float]) -> float:
    if not isinstance(a, list) or not isinstance(b, list) or not a or not b:
        return 0.0
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    den = float(np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-8
    if den <= 0.0:
        return 0.0
    return float(np.dot(va, vb) / den)

def extract_emotion_tag(text: str) -> Dict[str, Any]:
    raw = call_gpt(
        '给这段话打情绪标签并提供2个语气词；严格返回JSON：{"emotion":"...","tone":["...","..."]}\n'+text,
        sys="你只返回有效 JSON 对象。",
        temperature=0.2,
        json_only=True
    )
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("not dict")
    except Exception:
        obj = {"emotion": "neutral", "tone": ["neutral"]}
    if "emotion" not in obj:
        obj["emotion"] = "neutral"
    if "tone" not in obj or not obj["tone"]:
        obj["tone"] = ["neutral"]
    return obj

def _emo_embed_from_tag(tag: Dict[str, Any]) -> List[float]:
    lab = (tag.get("emotion") or "neutral").strip()
    tones = ",".join((tag.get("tone") or [])[:2]).strip(",")
    emo_text = f"{lab};{tones}" if tones else lab
    return get_embedding(emo_text)

def summarize_answer(text: str) -> str:
    return f"- {text.strip()[:120]}"

def assess_importance(text: str) -> int:
    raw = call_gpt("请从0到100评估这句话的重要性，只返回数字：\n" + text, "你只输出整数0-100。", temperature=0.0)
    m = re.search(r"(-?\d+)", raw or "")
    try:
        v = int(m.group(1)) if m else 50
    except Exception:
        v = 50
    return max(0, min(100, v))

# =========================
# Memory stream loader
# =========================
def _paths(agent_dir: str) -> Dict[str, str]:
    ms = os.path.join(agent_dir, "memory_stream")
    return {
        "nodes_nd": os.path.join(ms, "nodes.ndjson"),
        "evt_nd":   os.path.join(ms, "embeddings_event.ndjson"),
        "emo_nd":   os.path.join(ms, "embeddings_emotion.ndjson"),
    }

def _read_ndjson(path: str) -> List[Dict[str, Any]]:
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out

def _get_any_id(rec: Dict[str, Any]) -> Any:
    return rec.get("id") or rec.get("node_id") or rec.get("nid")

def _get_any_vec(rec: Dict[str, Any]) -> List[float] | None:
    v = rec.get("vec")
    if v is None:
        v = rec.get("embedding")
    return v

def load_corpus_from_memory_stream(agent_dir: str) -> List[Dict[str, Any]]:
    p = _paths(agent_dir)
    nodes = _read_ndjson(p["nodes_nd"])
    evtv  = _read_ndjson(p["evt_nd"])
    emov  = _read_ndjson(p["emo_nd"])

    evt_map: Dict[Any, List[float] | None] = {}
    for x in evtv:
        k = _get_any_id(x)
        if k is not None:
            evt_map[k] = _get_any_vec(x)

    emo_map: Dict[Any, List[float] | None] = {}
    for x in emov:
        k = _get_any_id(x)
        if k is not None:
            emo_map[k] = _get_any_vec(x)

    corpus: List[Dict[str, Any]] = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = _get_any_id(n)
        text = n.get("content") or n.get("text") or ""
        summary = n.get("summary") or (text[:120] if isinstance(text, str) else "")
        corpus.append({
            **n,
            "id": nid,
            "text": text,
            "summary": summary,
            "evt_vec": evt_map.get(nid),
            "emo_vec": emo_map.get(nid),
        })
    print(f"🧩 memory_stream 载入：{len(corpus)} 条")
    return corpus

def _dedup_by_id(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for x in items:
        nid = x.get("id") or x.get("node_id")
        if nid in seen:
            continue
        seen.add(nid)
        out.append(x)
    return out

def _id_set(items: List[Dict[str, Any]]) -> set:
    s = set()
    for x in items:
        nid = x.get("id") or x.get("node_id")
        if nid:
            s.add(nid)
    return s

def build_corpus(
    agent_dir: str,
    exclude_ids: set | None = None,
    interlocutor: str | None = None,
    session_id: str | None = None,
) -> List[Dict[str, Any]]:
    exclude_ids = exclude_ids or set()
    past_nodes = load_corpus_from_memory_stream(agent_dir)
    past_ids = _id_set(past_nodes)
    agent_scope = os.path.abspath(agent_dir)

    def in_scope(memory: Dict[str, Any]) -> bool:
        if memory.get("_agent_dir") != agent_scope:
            return False
        if not str(memory.get("mtype", "")).endswith("_temp"):
            return True
        source = memory.get("source") or {}
        return (
            source.get("interlocutor") == interlocutor
            and source.get("session_id") == session_id
        )

    mem_extra = [
        memory
        for memory in memory_cache
        if in_scope(memory) and (memory.get("id") or memory.get("node_id")) not in past_ids
    ]
    merged = past_nodes + mem_extra
    merged = _dedup_by_id(merged)
    if exclude_ids:
        merged = [x for x in merged if (x.get("id") or x.get("node_id")) not in exclude_ids]
    return merged

# =========================
# Retrieval (dual-channel + Park-like)
# =========================
def park_like_select(
    rel_raw: List[Dict[str, Any]],
    top_k: int = TOP_K,
    min_score: float = REL_MIN_SCORE,
    min_evt: float = REL_MIN_EVT,
    delta: float = DELTA_BAND
) -> List[Dict[str, Any]]:
    if not rel_raw:
        return []
    rel_sorted = sorted(rel_raw, key=lambda r: r.get("score", 0.0), reverse=True)
    rel_sorted = [r for r in rel_sorted if r.get("score", 0.0) >= float(min_score) and r.get("_s_evt", 0.0) >= float(min_evt)]
    if not rel_sorted:
        return []
    best = rel_sorted[0]["score"]
    band = [r for r in rel_sorted if (best - r["score"]) <= float(delta)]
    return band[:top_k]

def _print_pick_stats(place: str, raw_cnt: int, use_cnt: int):
    print(f"🔎 [{place}] 相似记忆检索：原始 {raw_cnt} 条；采用 {use_cnt} 条（Park-like，自适应筛）")

def _is_yesno(q: str) -> bool:
    q = q.strip()
    return bool(re.search(r"[吗\?？]\s*$", q)) or q[:2] in ("会吗", "能吗", "要吗")

def _is_question(s: str) -> bool:
    s = s.strip()
    return s.endswith(("吗", "？", "?", "嘛")) or "为什么" in s or "如何" in s or "怎么" in s

def search_similar_nodes_dual_robust(
    query_text: str,
    memory_cache_like: List[Dict[str, Any]],
    embed_fn,
    emo_tag_fn,
    cos_fn,
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    evt_q = embed_fn(query_text)
    q_tag = emo_tag_fn(query_text)
    emo_q = _emo_embed_from_tag(q_tag)
    emo_q_label = (q_tag.get("emotion") or "neutral").strip()

    query_is_q = _is_question(query_text)
    if query_is_q:
        candidates = memory_cache_like
    else:
        candidates = [n for n in memory_cache_like if n.get("mtype") not in PROMPT_MTYPES]

    scored: List[Dict[str, Any]] = []
    for n in candidates:
        evt_vec = n.get("evt_vec")
        if not isinstance(evt_vec, list):
            base_text = n.get("text") or n.get("content") or n.get("summary") or ""
            evt_vec = embed_fn(base_text) if base_text else None

        emo_vec = n.get("emo_vec")
        cand_label = None
        cand_tag = None
        if isinstance(n.get("emotion_tag"), dict):
            cand_tag = n["emotion_tag"]
            cand_label = cand_tag.get("emotion")
        if not isinstance(emo_vec, list):
            if cand_tag:
                emo_vec = _emo_embed_from_tag(cand_tag)
            else:
                emo_vec = _emo_embed_from_tag({"emotion": "neutral", "tone": []})
                cand_label = "neutral"
        if not cand_label:
            cand_label = "neutral"

        s_evt = cos_fn(evt_q, evt_vec) if isinstance(evt_vec, list) else 0.0
        s_emo_raw = cos_fn(emo_q, emo_vec) if isinstance(emo_vec, list) else 0.0

        # 同标签/neutral 降权（B 规则）
        if cand_label == emo_q_label:
            s_emo = min(s_emo_raw, 0.2)
        elif "neutral" in (cand_label, emo_q_label):
            s_emo = 0.0
        else:
            s_emo = s_emo_raw

        score_details = score_candidate(
            semantic=s_evt,
            emotion=s_emo,
            importance=n.get("importance", 50),
            timestamp=n.get("ts"),
            weights=RETRIEVAL_WEIGHTS,
        )
        signals = score_details["signals"]
        scored.append({
            **n,
            "score": float(score_details["score"]),
            "_s_evt": float(signals["semantic"]),
            "_s_emo": float(signals["emotion"]),
            "_s_salience": float(signals["salience"]),
            "_s_recency": float(signals["recency"]),
            "_weighted": score_details["weighted"],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]

def _print_adopted(use: List[Dict[str, Any]]):
    if not use:
        return
    print("🔍 相似记忆（采用，按分数降序）：")
    for r in use:
        s = f"{r.get('score', 0.0):.2f}"
        print(
            f"   · {r.get('summary','')}  "
            f"(score={s} | semantic={r.get('_s_evt',0):.2f}, emotion={r.get('_s_emo',0):.2f}, "
            f"salience={r.get('_s_salience',0):.2f}, recency={r.get('_s_recency',0):.2f})"
        )

# =========================
# Style loading & prompt
# =========================
def _latest_style(agent_dir: str, pseudonym: str) -> Dict[str, Any]:
    meta_path = os.path.join(agent_dir, "meta.json")
    meta = load_or_init_meta(meta_path, pseudonym)
    style = meta.get("empathic_style") or meta.get("style") or {}
    if style:
        return style

    sess_root = os.path.join(agent_dir, "sessions")
    if os.path.exists(sess_root):
        sess_ids = sorted(os.listdir(sess_root))
        while sess_ids:
            last = sess_ids.pop()
            refl_path = os.path.join(sess_root, last, "reflection.json")
            if os.path.exists(refl_path):
                try:
                    refl = json.load(open(refl_path, "r", encoding="utf-8"))
                    return refl.get("empathic_style", {}) or {}
                except Exception:
                    pass
    return {}

def _build_style_prompt(style: Dict[str, Any]) -> str:
    tone = ", ".join(style.get("tone", [])[:3]) if isinstance(style.get("tone"), list) else ""
    logic = style.get("logic", "") or ""
    values = ", ".join(style.get("values", [])[:3]) if isinstance(style.get("values"), list) else ""
    boundaries = style.get("boundaries", "") or ""
    message_length = style.get("message_length", "") or ""
    sentence_rhythm = style.get("sentence_rhythm", "") or ""
    reply_cadence = style.get("reply_cadence", "") or ""
    recurring_vocabulary = ", ".join(style.get("recurring_vocabulary", [])[:6]) if isinstance(style.get("recurring_vocabulary"), list) else ""
    attribution = style.get("attribution", "") or ""
    return (
        "You are this person's MIRROR persona.\n"
        "Speak in their natural speaking style — imitate their habitual tone, rhythm, and phrasing inferred from past answers.\n"
        "Use Chinese, concise, first-person replies.\n\n"
        "Style:\n"
        f"- tone: {tone or '—'}\n"
        f"- logic: {logic or '—'}\n"
        f"- values: {values or '—'}\n"
        f"- boundaries: {boundaries or '—'}\n\n"
        f"- typical message length: {message_length or '—'}\n"
        f"- sentence rhythm: {sentence_rhythm or '—'}\n"
        f"- reply cadence: {reply_cadence or '—'}\n"
        f"- recurring vocabulary: {recurring_vocabulary or '—'}\n"
        f"- attribution pattern: {attribution or '—'}\n\n"
        "Hard rules:\n"
        "1) Stay consistent with this person's speaking manner (tone/rhythm/word choice).\n"
        "2) 1–3 short sentences; no generic advice unless explicitly asked.\n"
        "3) Only use retrieved memories/context; if unsure, ask one brief clarification.\n"
        "4) Do not repeat the user's wording verbatim.\n"
        "5) You are a transparent mirror, not the real person; never invent private memories, relationships, or certainty."
    )

# =========================
# Mirror sessions (paths & IO)
# =========================
def _mirror_session_paths(agent_dir: str, interlocutor: str, session_id: str) -> Dict[str, str]:
    base = os.path.join(agent_dir, "mirror_sessions", interlocutor, session_id)
    os.makedirs(base, exist_ok=True)
    return {
        "base": base,
        "conversation": os.path.join(base, "conversation.json"),
        "retrieval_log": os.path.join(base, "retrieval_log.jsonl"),
        "config": os.path.join(base, "config.json"),
    }

def _append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

def _read_conversation(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    try:
        return json.load(open(path, "r", encoding="utf-8"))
    except Exception:
        return []

# =========================
# Context window gatherer
# =========================
def gather_context_window(agent_dir: str, pick: Dict[str, Any], win: int) -> str:
    """
    回溯上下文：支持 kind=mirror 与 kind=interview。
    """
    src = pick.get("source") or {}
    kind = src.get("kind")
    if kind == "mirror":
        interlocutor = src.get("interlocutor") or "self"
        sid = src.get("session_id"); t = src.get("turn_index")
        if sid is None or t is None:
            return ""
        sp = _mirror_session_paths(agent_dir, interlocutor, sid)
        convo = _read_conversation(sp["conversation"])
        if not convo:
            return ""
        L = max(0, int(t) - int(win)); R = min(len(convo), int(t) + int(win) + 1)
        lines = []
        for i in range(L, R):
            role = convo[i].get("role", "")
            text = convo[i].get("content", "")
            lines.append(f"{role}: {text}")
        return "\n".join(lines)

    if kind == "interview":
        sid = src.get("session_id"); t = src.get("turn_index")
        if sid is None or t is None:
            return ""
        path = os.path.join(agent_dir, "sessions", sid, "conversation.json")
        convo = _read_conversation(path)
        if not convo:
            return ""
        L = max(0, int(t) - int(win)); R = min(len(convo), int(t) + int(win) + 1)
        lines = []
        for i in range(L, R):
            role = convo[i].get("role", "")
            text = convo[i].get("content", "")
            lines.append(f"{role}: {text}")
        return "\n".join(lines)

    return ""

# =========================
# Small helpers (cleanup)
# =========================
GENERIC_BAN = {"你也可以试试", "享受每个小幸福", "保持乐观", "放轻松", "加油", "相信自己"}
def _strip_generic(s: str) -> str:
    t = s
    for p in GENERIC_BAN:
        t = t.replace(p, "")
    return re.sub(r"\s{2,}", " ", t).strip(" ，")

def _soft_deecho(reply: str, user_text: str) -> str:
    if len(user_text) >= 6 and user_text in reply:
        return reply.replace(user_text, "").strip()
    return reply


def build_response_plan(user_text: str, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Turn retrieved evidence into a constrained action before reply generation."""
    retrieved_ids = [str(item.get("id") or item.get("node_id")) for item in memories if item.get("id") or item.get("node_id")]
    fallback = fallback_response_plan(user_text, bool(retrieved_ids))
    if not memories:
        return fallback

    evidence = [
        {
            "id": str(item.get("id") or item.get("node_id")),
            "summary": item.get("summary", ""),
            "emotion": (item.get("emotion_tag") or {}).get("emotion", "neutral"),
            "score": round(float(item.get("score", 0.0)), 4),
        }
        for item in memories
    ]
    prompt = (
        "Plan one grounded mirror response. Return only JSON with this schema:\n"
        '{"reflection":"short evidence-based observation","action":"ask|reframe|nudge|mirror|pause",'
        '"confidence":0.0,"grounding_ids":["retrieved-id"]}\n\n'
        "Use only the supplied evidence. Choose ask when evidence is insufficient; never diagnose.\n"
        f"User message: {user_text}\n"
        f"Retrieved evidence: {json.dumps(evidence, ensure_ascii=False)}"
    )
    try:
        raw = json.loads(call_gpt(
            prompt,
            sys="You are Alter Emo's reflection planner. Return one valid JSON object only.",
            temperature=0.1,
            json_only=True,
        ))
    except Exception:
        raw = fallback
    return normalize_response_plan(raw, user_text=user_text, retrieved_ids=retrieved_ids)

# =========================
# Mirror chat core
# =========================
def mirror_reply(
    pseudonym: str,
    agent_dir: str,
    user_text: str,
    interlocutor: str,
    session_id: str,
    win_ctx: int
) -> str:
    style = _latest_style(agent_dir, pseudonym)
    sys = _build_style_prompt(style)

    # Build retrieval corpus (exclude latest in-process node if any)
    exclude_ids = set()
    if memory_cache:
        last = memory_cache[-1]
        lid = last.get("id") or last.get("node_id")
        if lid:
            exclude_ids.add(lid)

    corpus = build_corpus(
        agent_dir,
        exclude_ids=exclude_ids,
        interlocutor=interlocutor,
        session_id=session_id,
    ) or build_corpus(agent_dir, interlocutor=interlocutor, session_id=session_id)
    rel_raw = search_similar_nodes_dual_robust(user_text, corpus, get_embedding, extract_emotion_tag, cosine)
    use = park_like_select(rel_raw, top_k=TOP_K, min_score=REL_MIN_SCORE, min_evt=REL_MIN_EVT, delta=DELTA_BAND)

    _print_pick_stats("Mirror", len(rel_raw), len(use))
    _print_adopted(use)

    # Gather context: summary + [Context] window
    ctx_chunks = []
    for r in use:
        sumline = r.get("summary", "")
        window = gather_context_window(agent_dir, r, win=win_ctx)
        if window:
            ctx_chunks.append(f"{sumline}\n[Context]\n{window}")
        else:
            ctx_chunks.append(sumline)
    rel_txt = "\n\n---\n\n".join(ctx_chunks)

    response_plan = build_response_plan(user_text, use)

    # ====== Generate reply ======
    yesno_mode = _is_yesno(user_text)
    extra_rule = (
        "If the user asks a yes/no about 'you', answer with a direct '会/不会/偶尔会' plus one concrete detail from Context; no suggestions; 1 sentence only."
        if yesno_mode else
        "Reply in 1–3 short sentences. Ground at least one detail in Context when available. Do not repeat user's wording."
    )
    prompt = (
        "Context memories (each with optional local context window):\n"
        f"{rel_txt or '(none)'}\n\n"
        "Reflection plan:\n"
        f"- observation: {response_plan['reflection']}\n"
        f"- action: {response_plan['action']}\n"
        f"- action instruction: {response_instruction(response_plan)}\n"
        f"- grounded memory ids: {', '.join(response_plan['grounding_ids']) or '(none)'}\n\n"
        f"User said: {user_text}\n"
        f"{extra_rule}"
    )
    reply = call_gpt(prompt, sys=sys, temperature=0.2)
    reply = _strip_generic(_soft_deecho(reply, user_text))
    if not reply:
        reply = "会。" if yesno_mode else "嗯。"

    # ====== Save strategy ======
    SAVE_TO_MAIN = (interlocutor in (None, "", "self"))

    # 当前会话 turn 索引（用于 source 回溯） + 取上一条镜像回复文本
    sp = _mirror_session_paths(agent_dir, interlocutor, session_id)
    conv_len = 0
    prev_mirror_text = ""
    if os.path.exists(sp["conversation"]):
        try:
            _old = json.load(open(sp["conversation"], "r", encoding="utf-8"))
            conv_len = len(_old)
            if _old and _old[-1].get("role") == "mirror":
                prev_mirror_text = _old[-1].get("content", "")
        except Exception:
            pass

    if SAVE_TO_MAIN:
        # ✅ Self-chat: write to main memory_stream
        # user node (embedding = prev_mirror + user)
        u_sum = summarize_answer(user_text)
        u_imp = assess_importance(user_text)
        u_emo = extract_emotion_tag(user_text)
        u_evt = get_embedding(f"{prev_mirror_text}\n{user_text}".strip() if prev_mirror_text else user_text)
        u_emo_vec = _emo_embed_from_tag(u_emo)
        u_node = save_memory_node_dual(
            agent_dir=agent_dir,
            text=user_text,
            summary=u_sum,
            mtype="mirror_user",
            qid=None,
            importance=u_imp,
            emotion_tag=u_emo,
            evt_vec=u_evt,
            emo_vec=u_emo_vec,
            source={
                "kind": "mirror",
                "interlocutor": interlocutor,
                "session_id": session_id,
                "turn_index": conv_len,
            },
        )
        memory_cache.append({
            **u_node,
            "evt_vec": u_evt,
            "emo_vec": u_emo_vec,
            "_agent_dir": os.path.abspath(agent_dir),
        })

        # mirror node (embedding = user + reply)
        m_sum = summarize_answer(reply)
        m_imp = assess_importance(reply)
        m_emo = extract_emotion_tag(reply)
        m_evt = get_embedding(f"{user_text}\n{reply}")
        m_emo_vec = _emo_embed_from_tag(m_emo)
        m_node = save_memory_node_dual(
            agent_dir=agent_dir,
            text=reply,
            summary=m_sum,
            mtype="mirror_reply",
            qid=None,
            importance=m_imp,
            emotion_tag=m_emo,
            evt_vec=m_evt,
            emo_vec=m_emo_vec,
            source={
                "kind": "mirror",
                "interlocutor": interlocutor,
                "session_id": session_id,
                "turn_index": conv_len + 1,
            },
        )
        memory_cache.append({
            **m_node,
            "evt_vec": m_evt,
            "emo_vec": m_emo_vec,
            "_agent_dir": os.path.abspath(agent_dir),
        })
    else:
        # 🚫 Others: DO NOT write to main memory; only log session below
        # 临时节点（embedding 同样合并上下文）
        u_tag = extract_emotion_tag(user_text)
        u_evt = get_embedding(f"{prev_mirror_text}\n{user_text}".strip() if prev_mirror_text else user_text)
        u_emo_vec = _emo_embed_from_tag(u_tag)
        memory_cache.append({
            "id": f"temp-{uuid.uuid4().hex}",
            "text": user_text, "summary": summarize_answer(user_text),
            "evt_vec": u_evt, "emo_vec": u_emo_vec,
            "emotion_tag": u_tag,
            "mtype": "mirror_user_temp",
            "_agent_dir": os.path.abspath(agent_dir),
            "source": {"kind":"mirror","interlocutor": interlocutor,"session_id": session_id,"turn_index": conv_len}
        })
        m_tag = extract_emotion_tag(reply)
        m_evt = get_embedding(f"{user_text}\n{reply}")
        m_emo_vec = _emo_embed_from_tag(m_tag)
        memory_cache.append({
            "id": f"temp-{uuid.uuid4().hex}",
            "text": reply, "summary": summarize_answer(reply),
            "evt_vec": m_evt, "emo_vec": m_emo_vec,
            "emotion_tag": m_tag,
            "mtype": "mirror_reply_temp",
            "_agent_dir": os.path.abspath(agent_dir),
            "source": {"kind":"mirror","interlocutor": interlocutor,"session_id": session_id,"turn_index": conv_len+1}
        })

    # ---- Always log mirror session (conversation + retrieval picks) ----
    convo = []
    if os.path.exists(sp["conversation"]):
        convo = json.load(open(sp["conversation"], "r", encoding="utf-8"))
    convo += [
        {"role": "user", "content": user_text, "ts": time.time(), "interlocutor": interlocutor},
        {"role": "mirror", "content": reply, "ts": time.time(), "interlocutor": interlocutor},
    ]
    with open(sp["conversation"], "w", encoding="utf-8") as f:
        json.dump(convo, f, ensure_ascii=False, indent=2)

    _append_jsonl(sp["retrieval_log"], {
        "ts": time.time(),
        "interlocutor": interlocutor,
        "q": user_text,
        "picks": [
            {"id": (r.get("id") or r.get("node_id")), "summary": r.get("summary",""),
             "score": r.get("score",0.0), "semantic": r.get("_s_evt",0.0),
             "emotion": r.get("_s_emo",0.0), "salience": r.get("_s_salience",0.0),
             "recency": r.get("_s_recency",0.0), "weighted": r.get("_weighted", {})}
            for r in use
        ],
        "response_plan": response_plan,
        "retrieval_weights": RETRIEVAL_WEIGHTS,
        "win_ctx": win_ctx
    })

    return reply

# =========================
# Helpers: list & ensure structure
# =========================
def _list_existing_agents() -> List[str]:
    ensure_dirs()
    base = OUT_DIR
    if not os.path.exists(base):
        return []
    names = []
    for n in sorted(os.listdir(base)):
        p = os.path.join(base, n)
        if not os.path.isdir(p):
            continue
        if os.path.exists(os.path.join(p, "meta.json")) or os.path.exists(os.path.join(p, "memory_stream")):
            names.append(n)
    return names

def _ensure_min_agent_structure(agent_dir: str, pseudonym: str):
    os.makedirs(agent_dir, exist_ok=True)
    ms_dir = os.path.join(agent_dir, "memory_stream")
    os.makedirs(ms_dir, exist_ok=True)
    meta_path = os.path.join(agent_dir, "meta.json")
    if not os.path.exists(meta_path):
        meta = {
            "id": str(uuid.uuid4()),
            "version": 1,
            "identity": {"pseudonym": pseudonym, "mbti": None},
            "empathic_style": {
                "tone": [],
                "logic": "",
                "values": [],
                "boundaries": "",
            }
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

# =========================
# CLI + Interactive main
# =========================
def main():
    parser = argparse.ArgumentParser(description="Mirror Persona Chat")
    parser.add_argument("--id", help="参与者代号，如 MIMI")
    parser.add_argument("--interlocutor", help="与镜像对话的人（如 self/妈妈/朋友A）")
    parser.add_argument("--list", action="store_true", help="仅列出已有的人格目录后退出")
    parser.add_argument("--check", action="store_true", help="验证 OpenAI 配置与网络后退出")
    parser.add_argument("--ctxwin", type=int, default=WIN_CTX_DEFAULT, help="上下文窗口大小（前后各 N 条）")
    args = parser.parse_args()

    print("\n🪞 Mirror Persona Chat （输入 Q 回车可随时退出）")
    ensure_dirs()

    if args.check:
        try:
            models = get_client().models.list().data
            print(f"✅ OpenAI connection is ready ({len(models)} models visible).")
        except Exception as error:
            raise SystemExit(f"❌ OpenAI connection check failed: {error}")
        return

    if args.list:
        names = _list_existing_agents()
        if names:
            print("📚 已有人格：", ", ".join(names))
        else:
            print("（暂无）请先创建或运行本程序交互式创建。")
        return

    # ① Pick pseudonym
    if args.id:
        pseudonym = args.id.strip()
    else:
        names = _list_existing_agents()
        if names:
            print("\n可用人格目录：")
            for i, n in enumerate(names, 1):
                print(f"  {i}. {n}")
            raw = input("请选择编号，或直接输入新的人格代号：").strip()
            if raw.upper() == "Q":
                print("👋 已退出。")
                return
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(names):
                    pseudonym = names[idx-1]
                else:
                    print("⚠️ 编号超出范围。")
                    return
            else:
                pseudonym = raw
        else:
            raw = input("当前无已有人格，请输入新的人格代号：").strip()
            if not raw or raw.upper() == "Q":
                print("👋 已退出。")
                return
            pseudonym = raw

    if not pseudonym:
        print("⚠️ 人格代号为空。")
        return

    agent_dir = os.path.join(OUT_DIR, pseudonym)
    if not os.path.exists(agent_dir):
        print(f"🆕 未找到 agents/{pseudonym}/，将为你创建最小结构。")
        _ensure_min_agent_structure(agent_dir, pseudonym)

    # ② Pick interlocutor
    if args.interlocutor:
        interlocutor = args.interlocutor.strip() or "self"
    else:
        interlocutor = input("请输入与镜像对话的对象（如 self / 妈妈 / 朋友A）：").strip() or "self"
        if interlocutor.upper() == "Q":
            print("👋 已退出。")
            return

    # ③ Create session + config snapshot
    session_id = uuid.uuid4().hex[:8]
    sp = _mirror_session_paths(agent_dir, interlocutor, session_id)
    config = {
        "MODEL_CHAT": MODEL_CHAT,
        "MODEL_EMB": MODEL_EMB,
        "TOP_K": TOP_K,
        "REL_MIN_SCORE": REL_MIN_SCORE,
        "REL_MIN_EVT": REL_MIN_EVT,
        "DELTA_BAND": DELTA_BAND,
        "RETRIEVAL_WEIGHTS": RETRIEVAL_WEIGHTS,
        "interlocutor": interlocutor,
        "started_at": time.time(),
        "WIN_CTX": int(args.ctxwin),
    }
    with open(sp["config"], "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    print(f"\n🪞 已载入人格 [{pseudonym}]，当前对象 [{interlocutor}] (session={session_id})")
    print(f"上下文窗口：前后各 {int(args.ctxwin)} 条\n开始聊天吧：\n")

    try:
        while True:
            user_text = input("你：").strip()
            if not user_text:
                continue
            if user_text.upper() == "Q":
                print("👋 结束镜像会话。")
                break
            reply = mirror_reply(pseudonym, agent_dir, user_text, interlocutor, session_id, win_ctx=int(args.ctxwin))
            print("镜像：", reply, "\n")
    except KeyboardInterrupt:
        print("\n👋 结束镜像会话。")

if __name__ == "__main__":
    main()
