# ai_interview_agent_text.py
# Text-only idiographic empathy interviewer (Park-like).
# NEW:
# - Save question nodes for main & follow-up (with embeddings = question text).
# - Save answer nodes as before (embeddings = question + answer).
# - Add source for all saved nodes (kind=interview, session_id, turn_index).
# - Retrieval thresholds/logic unchanged here (this file doesn't retrieve in Main phase).

from __future__ import annotations

import os
import re
import json
import uuid
import time
import random
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from agent_io import (
    load_or_init_meta,
    save_meta,
    save_memory_node_dual,
    OUT_DIR,
    AGENT_DIR,
    ensure_dirs,
)
from runtime_config import PROJECT_ROOT, create_openai_client, load_settings

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
# Global Runtime State
# =========================
memory_cache: List[Dict[str, Any]] = []
conversation_log: List[Dict[str, str]] = []
notes: List[str] = []

# Retrieval params (used only in follow-ups)
TOP_K = 3
REL_MIN_SCORE = 0.50
REL_MIN_EVT   = 0.30
DELTA_BAND    = 0.10
MAX_FOLLOWUPS = 2
STOP_THRESHOLD = 0.60
W_EVT = 0.80
W_EMO = 0.20

class QuitSignal(Exception):
    pass

QUIT_REQUESTED = False
CURRENT_SESSION_ID = ""

# =========================
# Utils
# =========================
def _retry(fn, *a, **kw):
    for i in range(4):
        try:
            return fn(*a, **kw)
        except Exception:
            if i == 3:
                raise
            time.sleep(1.2 * (i + 1))

def call_gpt(prompt: str, sys: str = "You are a warm, concise Chinese interviewer.",
             temperature: float = 0.3, json_only: bool = False) -> str:
    return _retry(
        lambda: get_client().chat.completions.create(
            model=MODEL_CHAT,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": prompt}],
            temperature=temperature,
            **({"response_format": {"type": "json_object"}} if json_only else {})
        ).choices[0].message.content.strip()
    )

def get_embedding(text: str) -> List[float]:
    return _retry(lambda: get_client().embeddings.create(model=MODEL_EMB, input=text).data[0].embedding)

def cosine(a: List[float], b: List[float]) -> float:
    if not isinstance(a, list) or not isinstance(b, list) or not a or not b:
        return 0.0
    va, vb = np.array(a, dtype=np.float32), np.array(b, dtype=np.float32)
    den = float(np.linalg.norm(va) * np.linalg.norm(vb)) + 1e-8
    if den <= 0.0:
        return 0.0
    return float(np.dot(va, vb) / den)

def ask_user(text: str, kind: str = "Question") -> str:
    print(f"\n🧾 [{kind}] {text}")
    resp = input("你的回答（输入 Q 退出）：").strip()
    if resp.upper() == "Q":
        print("👋 检测到退出请求，正在保存当前会话……")
        raise QuitSignal()
    return resp

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

def extract_emotion_tag(text: str) -> Dict[str, Any]:
    raw = call_gpt(
        "给这段话打情绪标签，并给出2个语气词。严格返回JSON："
        '{"emotion":"...","tone":["...","..."]}\n' + text,
        "你只返回紧凑的JSON。",
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

# =========================
# Reflection style guard (unchanged)
# =========================
DEFAULT_BANNED_TOKENS = {
    "calm", "gentle", "listen → reframe → support", "care > fairness",
    "听起来你在倾听方面非常用心，能具体分享一下当时通过哪些方式确认自己理解正确吗？",
    "真有意思的经历！能具体举例说明你是怎么做到认真听的吗？"
}

def _looks_template_like(obj: Dict[str, Any]) -> bool:
    try:
        style = obj.get("empathic_style", {}) or {}
        toks = set()
        if isinstance(style.get("tone"), list):
            toks.update([t for t in style.get("tone") if isinstance(t, str)])
        if isinstance(style.get("values"), list):
            toks.update([t for t in style.get("values") if isinstance(t, str)])
        for k in ("logic", "boundaries", "message_length", "sentence_rhythm", "reply_cadence", "attribution"):
            v = style.get(k)
            if isinstance(v, str):
                toks.add(v)
        for k in ("example_phrases", "recurring_vocabulary"):
            if isinstance(style.get(k), list):
                toks.update([t for t in style.get(k) if isinstance(t, str)])
        toks = {t.strip() for t in toks if isinstance(t, str)}
        return any(t in DEFAULT_BANNED_TOKENS for t in toks)
    except Exception:
        return False

def reflect_empathic_style(conversation: List[Dict[str, str]]) -> Dict[str, Any]:
    joined = "\n".join([f"{x['role']}: {x['content']}" for x in conversation])
    prompt = f"""
请基于“对话记录”提炼此人的【共情风格】，严格输出 JSON 对象（不要多余文本、不要代码围栏）。

规则：
- 仅依据对话事实生成，不可使用通用模板词；如无法确定某字段，用 null 或 []。
- "example_phrases" 必须从对话原话中抽取或高度贴近原话（中文）。
- "logic" 用简短流程串（如 "倾听→澄清→建议"），禁止 "listen → reframe → support"。
- "tone" ≤3 个词，避免 "calm"、"gentle"。
- "values"/"boundaries" 无依据则为 null。
- "message_length" 描述典型消息长度；"sentence_rhythm" 描述断句和节奏；"reply_cadence" 描述回应频率与展开方式。
- "recurring_vocabulary" 只记录反复出现的词或短语；"attribution" 描述此人通常如何解释事件原因。无依据则为空。
- "personality_seed" 为 Big5 推断，不确定可为 null。

输出 JSON 结构（字段说明，不是示例）：
{{
  "empathic_style": {{
    "tone": [],
    "logic": "",
    "values": [],
    "boundaries": "",
    "example_phrases": [],
    "message_length": "",
    "sentence_rhythm": "",
    "reply_cadence": "",
    "recurring_vocabulary": [],
    "attribution": ""
  }},
  "personality_seed": {{"O": null, "C": null, "E": null, "A": null, "N": null}}
}}

对话记录：
{joined}
"""
    raw = call_gpt(prompt, sys="你是严谨的数据标注员，只输出有效 JSON。", temperature=0.2, json_only=True)
    try:
        obj = json.loads(raw)
    except Exception:
        m = re.search(r"```json\s*(.*?)\s*```", raw or "", re.DOTALL)
        obj = json.loads(m.group(1)) if m else {"empathic_style": {}, "personality_seed": {}}
    if _looks_template_like(obj):
        ban_list = "\\n".join(sorted(DEFAULT_BANNED_TOKENS))
        raw2 = call_gpt(prompt + f"\n【严格禁止使用的词/短语】：\n{ban_list}\n",
                        sys="你是严谨的数据标注员，只输出有效 JSON。", temperature=0.4, json_only=True)
        try:
            obj2 = json.loads(raw2)
            if not _looks_template_like(obj2):
                return obj2
        except Exception:
            pass
    return obj

# =========================
# Corpus Loader (used in follow-ups only, unchanged)
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
    miss_evt = miss_emo = 0

    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = _get_any_id(n)
        text = n.get("content") or n.get("text") or ""
        summary = n.get("summary") or (text[:120] if isinstance(text, str) else "")

        evt_vec = evt_map.get(nid)
        emo_vec = emo_map.get(nid)
        if evt_vec is None: miss_evt += 1
        if emo_vec is None: miss_emo += 1

        corpus.append({
            **n,
            "id": nid,
            "text": text,
            "summary": summary,
            "evt_vec": evt_vec,
            "emo_vec": emo_vec,
        })

    print(f"🧩 memory_stream 载入：{len(corpus)} 条；缺事件向量 {miss_evt}，缺情绪向量 {miss_emo}")
    return corpus

def _dedup_by_id(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set(); out = []
    for x in items:
        nid = x.get("id") or x.get("node_id")
        if nid in seen: continue
        seen.add(nid); out.append(x)
    return out

def _id_set(items: List[Dict[str, Any]]) -> set:
    s = set()
    for x in items:
        nid = x.get("id") or x.get("node_id")
        if nid: s.add(nid)
    return s

def build_corpus(agent_dir: str, exclude_ids: set | None = None) -> List[Dict[str, Any]]:
    exclude_ids = exclude_ids or set()
    past_nodes = load_corpus_from_memory_stream(agent_dir)
    past_ids = _id_set(past_nodes)
    mem_extra = [m for m in memory_cache if (m.get("id") or m.get("node_id")) not in past_ids]
    merged = past_nodes + mem_extra
    merged = _dedup_by_id(merged)
    if exclude_ids:
        merged = [x for x in merged if (x.get("id") or x.get("node_id")) not in exclude_ids]
    return merged

# =========================
# Retrieval (only in follow-ups; unchanged core)
# =========================
def park_like_select(rel_raw: List[Dict[str, Any]], top_k: int = TOP_K,
                     min_score: float = REL_MIN_SCORE, min_evt: float = REL_MIN_EVT,
                     delta: float = DELTA_BAND) -> List[Dict[str, Any]]:
    if not rel_raw: return []
    rel_sorted = sorted(rel_raw, key=lambda r: r.get("score", 0.0), reverse=True)
    rel_sorted = [r for r in rel_sorted if r.get("score", 0.0) >= float(min_score) and r.get("_s_evt", 0.0) >= float(min_evt)]
    if not rel_sorted: return []
    best = rel_sorted[0]["score"]
    band = [r for r in rel_sorted if (best - r["score"]) <= float(delta)]
    return band[:top_k]

def _print_pick_stats(place: str, raw_cnt: int, use_cnt: int):
    print(f"🔎 [{place}] 相似记忆检索：原始 {raw_cnt} 条；采用 {use_cnt} 条（Park-like，自适应筛）")

def search_similar_nodes_dual_robust(query_text: str, memory_cache_like: List[Dict[str, Any]],
                                     embed_fn, emo_tag_fn, cos_fn, w_evt: float = W_EVT,
                                     w_emo: float = W_EMO, top_k: int = 6, allow_fallback: bool = True) -> List[Dict[str, Any]]:
    evt_q = embed_fn(query_text)
    q_tag = emo_tag_fn(query_text)
    emo_q = _emo_embed_from_tag(q_tag)
    emo_q_label = (q_tag.get("emotion") or "neutral").strip()

    scored: List[Dict[str, Any]] = []
    for n in memory_cache_like:
        evt_vec = n.get("evt_vec")
        if allow_fallback and not isinstance(evt_vec, list):
            base_text = n.get("text") or n.get("content") or n.get("summary") or ""
            evt_vec = embed_fn(base_text) if base_text else None

        emo_vec = n.get("emo_vec")
        cand_label = None; cand_tag = None
        if isinstance(n.get("emotion_tag"), dict):
            cand_tag = n["emotion_tag"]; cand_label = cand_tag.get("emotion")
        if allow_fallback and not isinstance(emo_vec, list):
            if cand_tag:
                emo_vec = _emo_embed_from_tag(cand_tag)
            else:
                emo_vec = _emo_embed_from_tag({"emotion": "neutral", "tone": []})
                cand_label = "neutral"
        if not cand_label: cand_label = "neutral"

        s_evt = cos_fn(evt_q, evt_vec) if isinstance(evt_vec, list) else 0.0
        s_emo_raw = cos_fn(emo_q, emo_vec) if isinstance(emo_vec, list) else 0.0

        if cand_label == emo_q_label:
            s_emo = min(s_emo_raw, 0.2)
        elif "neutral" in (cand_label, emo_q_label):
            s_emo = 0.0
        else:
            s_emo = s_emo_raw

        score = w_evt * s_evt + w_emo * s_emo
        scored.append({**n, "score": float(score), "_s_evt": float(s_evt), "_s_emo": float(s_emo)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]

def _print_adopted(use: List[Dict[str, Any]]):
    if not use: return
    print("🔍 相似记忆（采用，按分数降序）：")
    for r in use:
        s = f"{r.get('score', 0.0):.2f}"
        print(f"   · {r.get('summary','')}  (score={s} | s_evt={r.get('_s_evt',0):.2f}, s_emo={r.get('_s_emo',0):.2f})")

# =========================
# Followup Engine (unchanged saving, but we will add question nodes)
# =========================
def generate_followups(latest_transcript: str, current_question: str, objective: str, agent_dir: str) -> None:
    global memory_cache, notes, QUIT_REQUESTED

    q_text = latest_transcript
    _ = get_embedding(f"{current_question}\n{q_text}" if current_question else q_text)

    for _round in range(MAX_FOLLOWUPS):
        # 排除“当前最新节点”，避免自我命中
        exclude_ids = set()
        if memory_cache:
            last = memory_cache[-1]
            last_id = last.get("id") or last.get("node_id")
            if last_id:
                exclude_ids.add(last_id)

        corpus = build_corpus(agent_dir, exclude_ids=exclude_ids) or build_corpus(agent_dir, exclude_ids=set())

        rel_raw = search_similar_nodes_dual_robust(q_text, corpus, get_embedding, extract_emotion_tag, cosine)
        use = park_like_select(rel_raw, top_k=TOP_K, min_score=REL_MIN_SCORE, min_evt=REL_MIN_EVT, delta=DELTA_BAND)
        _print_pick_stats("Follow-up", len(rel_raw), len(use))
        _print_adopted(use)

        rel_txt = "\n".join([r.get("summary", "") for r in use])

        prompt = f"""Meta: Chinese; interviewer warm and concise
Question: "{current_question}"
Objective: {objective}
User: "{q_text}"
Notes: {"; ".join(notes)}
Related memories: {rel_txt}

任务（严格遵守）：
1) 先评估目标完成度，输出一行：score=0.xx （0~1）
2) 若 score≥{STOP_THRESHOLD:.2f}，必须只输出一行：STOP
3) 若 score<{STOP_THRESHOLD:.2f}，输出两行：
   Follow-up Question: <一句追问>
   Next Utterance: <采访者将如何自然地说出这句追问>
仅输出上述行，不要输出其它任何内容。
"""
        resp = call_gpt(prompt, temperature=0.2)
        conversation_log.append({"role": "reflection", "content": resp})

        mscore = re.search(r"score\s*=\s*([01](?:\.\d+)?)", resp or "", re.IGNORECASE)
        if mscore:
            try:
                score = float(mscore.group(1))
                if score >= STOP_THRESHOLD:
                    break
            except Exception:
                pass

        if "STOP" in (resp or "").upper():
            break

        m1 = re.search(r"Follow-?up Question:\s*(.*)", resp or "", re.IGNORECASE)
        m2 = re.search(r"Next Utterance:\s*(.*)", resp or "", re.IGNORECASE)
        if not m1:
            break

        followup_q = m1.group(1).strip()
        next_utt = (m2.group(1).strip() if m2 else followup_q) or followup_q

        # ====== NEW: 保存“追问问句节点” ======
        fq_source = {
            "kind": "interview",
            "session_id": CURRENT_SESSION_ID,
            "turn_index": len(conversation_log)  # 下一条就会 append 这条追问
        }
        fq_emo = {"emotion": "neutral", "tone": ["neutral"]}
        fq_evt = get_embedding(followup_q)
        fq_emo_vec = _emo_embed_from_tag(fq_emo)
        save_memory_node_dual(
            agent_dir=agent_dir,
            text=followup_q,
            summary=f"- Q: {followup_q[:120]}",
            mtype="followup_q",
            qid=None,
            importance=5,
            emotion_tag=fq_emo,
            evt_vec=fq_evt,
            emo_vec=fq_emo_vec,
            source=fq_source
        )

        try:
            ans = ask_user(next_utt, kind="Follow-up")
        except QuitSignal:
            QUIT_REQUESTED = True
            return

        conversation_log.append({"role": "interviewer_followup", "content": followup_q})
        conversation_log.append({"role": "user", "content": ans})

        summary = summarize_answer(ans)
        notes.append(summary)
        importance = assess_importance(ans)
        emo = extract_emotion_tag(ans)

        evt_vec = get_embedding(f"{followup_q}\n{ans}")
        emo_vec = _emo_embed_from_tag(emo)

        node = save_memory_node_dual(
            agent_dir=agent_dir,
            text=ans,
            summary=summary,
            mtype="followup_answer",
            qid=None,
            importance=importance,
            emotion_tag=emo,
            evt_vec=evt_vec,
            emo_vec=emo_vec,
            source={
                "kind": "interview",
                "session_id": CURRENT_SESSION_ID,
                "turn_index": len(conversation_log)-1  # 刚加入的 user 答案位置
            }
        )
        memory_cache.append({**node, "evt_vec": evt_vec, "emo_vec": emo_vec})

        q_text = ans  # 下一轮追问的查询文本

# =========================
# Script builder (unchanged)
# =========================
MBTI_LETTERS = set(list("IENS" + "TFJP"))

def _pick_letters(mbti_str: str) -> List[str]:
    letters = [c for c in mbti_str if c in MBTI_LETTERS]
    seen, out = set(), []
    for c in letters:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:4]

def _random_sample(lst: List[Any], k: int) -> List[Any]:
    if not lst:
        return []
    k = min(k, len(lst))
    return random.sample(lst, k)

def build_random_script_from_mbti(mbti: str, pool: Dict[str, List[Dict[str, Any]]], n_mbti: int = 2, n_gen: int = 2) -> List[Dict[str, Any]]:
    letters = _pick_letters(mbti)
    available_letters = [L for L in letters if isinstance(pool.get(L), list) and pool[L]]
    chosen: List[Dict[str, Any]] = []

    picked_letters = _random_sample(available_letters, n_mbti)
    for L in picked_letters:
        chosen += _random_sample(pool.get(L, []), 1)

    if len(chosen) < n_mbti:
        all_mbti_q = []
        for L in available_letters:
            all_mbti_q.extend(pool.get(L, []))
        rem = [q for q in all_mbti_q if q not in chosen]
        need = n_mbti - len(chosen)
        chosen += _random_sample(rem, need)

    chosen += _random_sample(pool.get("GEN", []), n_gen)
    return chosen[: (n_mbti + n_gen)]

# =========================
# Pool Loader
# =========================
def load_pool(filename: str) -> Dict[str, Any]:
    pool_path = PROJECT_ROOT / "examples" / filename
    if not pool_path.exists():
        raise FileNotFoundError(f"题库文件不存在：{pool_path}")
    try:
        with open(pool_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("题库 JSON 顶层应为对象（dict）。")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"题库 JSON 格式错误：{pool_path}\n{e}")

# =========================
# Main
# =========================
def main() -> None:
    global QUIT_REQUESTED, CURRENT_SESSION_ID

    ensure_dirs()

    pseudonym = input("给这位参与者起个代号（如 AA）：").strip() or "AA"
    agent_dir = os.path.join("agents", pseudonym)
    os.makedirs(agent_dir, exist_ok=True)

    CURRENT_SESSION_ID = uuid.uuid4().hex[:8]

    meta_path = os.path.join(agent_dir, "meta.json")
    meta = load_or_init_meta(meta_path, pseudonym)

    mbti = input("请输入你的 MBTI（如 INFP）：").strip().upper().split("-")[0]
    pool = load_pool("mbti_pool.json")

    script = build_random_script_from_mbti(mbti, pool, n_mbti=2, n_gen=2)

    print("\n🧠 Interview Starting...\n")
    for q in script:
        question = q.get("question", "").strip()
        if not question:
            continue

        conversation_log.append({"role": "interviewer_main", "content": question})

        # ====== NEW: 主问题问句节点（先落盘） ======
        q_source = {
            "kind": "interview",
            "session_id": CURRENT_SESSION_ID,
            "turn_index": len(conversation_log)-1  # 刚加入的问题位置
        }
        q_emo = {"emotion": "neutral", "tone": ["neutral"]}
        q_evt = get_embedding(question)
        q_emo_vec = _emo_embed_from_tag(q_emo)
        save_memory_node_dual(
            agent_dir=agent_dir,
            text=question,
            summary=f"- Q: {question[:120]}",
            mtype="interviewer_main_q",
            qid=q.get("id"),
            importance=5,
            emotion_tag=q_emo,
            evt_vec=q_evt,
            emo_vec=q_emo_vec,
            source=q_source
        )

        try:
            ans = ask_user(question, kind="Main")
        except QuitSignal:
            QUIT_REQUESTED = True
            break

        conversation_log.append({"role": "user", "content": ans})

        # Save main answer node（问+答合并）
        summary = summarize_answer(ans)
        notes.append(summary)
        importance = assess_importance(ans)
        emo = extract_emotion_tag(ans)

        evt_text = f"{question}\n{ans}" if question else ans
        evt_vec  = get_embedding(evt_text)
        emo_vec  = _emo_embed_from_tag(emo)

        node = save_memory_node_dual(
            agent_dir=agent_dir,
            text=ans,
            summary=summary,
            mtype="main_answer",
            qid=q.get("id"),
            importance=importance,
            emotion_tag=emo,
            evt_vec=evt_vec,
            emo_vec=emo_vec,
            source={
                "kind": "interview",
                "session_id": CURRENT_SESSION_ID,
                "turn_index": len(conversation_log)-1  # 刚加入的 user 答案位置
            }
        )
        memory_cache.append({**node, "evt_vec": evt_vec, "emo_vec": emo_vec})

        # Follow-ups
        generate_followups(ans, question, q.get("objective", ""), agent_dir)
        if QUIT_REQUESTED:
            break

    # Reflection
    print("\n🧠 Generating reflection summary...")
    reflection = reflect_empathic_style(conversation_log)
    print(json.dumps(reflection, ensure_ascii=False, indent=2))

    # Persist session
    sess_dir = os.path.join(agent_dir, "sessions", CURRENT_SESSION_ID)
    os.makedirs(sess_dir, exist_ok=True)

    with open(os.path.join(sess_dir, "conversation.json"), "w", encoding="utf-8") as f:
        json.dump(conversation_log, f, ensure_ascii=False, indent=2)
    with open(os.path.join(sess_dir, "reflection.json"), "w", encoding="utf-8") as f:
        json.dump(reflection, f, ensure_ascii=False, indent=2)
    with open(os.path.join(sess_dir, "script_used.json"), "w", encoding="utf-8") as f:
        json.dump({"mbti": mbti, "script": script}, f, ensure_ascii=False, indent=2)

    save_meta(
        meta_path=meta_path,
        meta=meta,
        session_id=CURRENT_SESSION_ID,
        style=reflection.get("empathic_style", {}),
        seed=reflection.get("personality_seed", {}),
        model_chat=MODEL_CHAT,
        model_emb=MODEL_EMB,
        mbti=mbti,
    )
    print(f"\n✅ 完成。数据已保存在：{agent_dir}")
    if QUIT_REQUESTED:
        print("ℹ️ 本次为手动中途退出，已保存当下对话与反思（可能不完整）。")

if __name__ == "__main__":
    main()
