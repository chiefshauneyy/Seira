import os
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, List

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")

AGENT_NAME = os.getenv("AGENT_NAME", "Seira")
MEMORY_PATH = os.getenv("MEMORY_PATH", "memory.json")


REMEMBER_RE = re.compile(r"^/remember\s+([^=\s]+)\s*=\s*(.+)\s*$", re.IGNORECASE)
FORGET_RE = re.compile(r"^/forget\s+([^\s]+)\s*$", re.IGNORECASE)
NOTE_RE = re.compile(r"^/note\s+(.+)\s*$", re.IGNORECASE)
CHECKIN_RE = re.compile(r"^/checkin\s+(.+)\s*$", re.IGNORECASE)
HISTORY_RE = re.compile(r"^/history(?:\s+(\d+))?\s*$", re.IGNORECASE)

HELP_TEXT = f"""
{AGENT_NAME} commands:
  /help                               Show this help
  /memory                             Print current memory
  /remember <key>=<value>             Save memory (supports dotted keys)
  /forget <key>                       Delete a memory key
  /note <text>                        Append a timestamped note
  /checkin k=v k=v ...                Log readiness metrics (sleep/hrv/rhr/soreness/mood/stress)
  /today                              Readiness score + recommendation
  /history [n]                        Last n check-ins (default 7)

Telegram approval quick actions:
  note: <text>
  checkin: sleep=... soreness=... mood=... stress=... [hrv=.. rhr=..]
  remind: in 30m <text>
  remind: tomorrow 09:00 <text>
  remind: 2026-02-07 09:00 <text>
""".strip()

def memory_pretty(memory: Dict[str, Any]) -> str:
    return json.dumps(memory, indent=2, ensure_ascii=False)

def memory_summary(memory: Dict[str, Any]) -> str:
    """Returns a readable summary to avoid Telegram character limits."""
    profile = memory.get("profile", {})
    notes_count = len(memory.get("notes", []))
    checkins_count = len(memory.get("checkins", []))
    reminders = [r for r in memory.get("reminders", []) if not r.get("sent")]
    
    summary = [
        f"🧠 {AGENT_NAME} Memory Status",
        f"👤 User: {profile.get('telegram_chat_id', 'Unknown')}",
        f"📝 Notes: {notes_count}",
        f"📊 Check-ins: {checkins_count}",
        f"⏰ Active Reminders: {len(reminders)}",
        "\nLast 3 Notes:"
    ]
    for n in memory.get("notes", [])[-3:]:
        summary.append(f"- {n['ts'][:10]}: {n['text'][:40]}...")
        
    return "\n".join(summary)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _default_memory() -> Dict[str, Any]:
    return {
        "profile": {
            "telegram_chat_id": None,  # set by bot on /start
        },
        "preferences": {},
        "rules": {"execution_mode": "approval"},
        "fitness": {},
        "notes": [],
        "checkins": [],
        "reminders": [],       # list of {id, ts_created, due, text, sent}
        "pending_actions": {}  # action_id -> {ts, action:{type, summary, payload}}
    }

def load_memory() -> Dict[str, Any]:
    if not os.path.exists(MEMORY_PATH):
        return _default_memory()
    try:
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        base = _default_memory()
        for k, v in base.items():
            data.setdefault(k, v)
        # ensure nested keys
        data.setdefault("profile", {}).setdefault("telegram_chat_id", None)
        data.setdefault("reminders", [])
        data.setdefault("pending_actions", {})
        return data
    except Exception:
        return _default_memory()

def save_memory(memory: Dict[str, Any]) -> None:
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)

def memory_set(memory: Dict[str, Any], dotted_key: str, value: Any) -> None:
    parts = dotted_key.split(".")
    cur = memory
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value

def memory_delete(memory: Dict[str, Any], dotted_key: str) -> bool:
    parts = dotted_key.split(".")
    cur: Any = memory
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return False
        cur = cur[p]
    if isinstance(cur, dict) and parts[-1] in cur:
        del cur[parts[-1]]
        return True
    return False

def memory_pretty(memory: Dict[str, Any]) -> str:
    return json.dumps(memory, indent=2, ensure_ascii=False)


# -------------------------
# Fitness readiness
# -------------------------

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def compute_readiness(checkin: Dict[str, Any], prev: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    reasons: List[str] = []

    sleep = float(checkin.get("sleep", 0) or 0)
    soreness = float(checkin.get("soreness", 5) or 5)
    mood = float(checkin.get("mood", 5) or 5)
    stress = float(checkin.get("stress", 5) or 5)

    sleep_score = clamp((sleep - 4.0) / 4.0, 0.0, 1.0)
    score = 40.0 * sleep_score
    if sleep < 6:
        reasons.append(f"Sleep is low ({sleep:.1f}h).")
    elif sleep >= 7:
        reasons.append(f"Sleep is solid ({sleep:.1f}h).")

    soreness_pen = clamp((soreness - 3) / 7.0, 0.0, 1.0)
    score += 20.0 * (1.0 - soreness_pen)
    if soreness >= 7:
        reasons.append(f"Soreness is high ({soreness:.0f}/10).")

    mood_norm = clamp((mood - 1) / 9.0, 0.0, 1.0)
    stress_norm = clamp((stress - 1) / 9.0, 0.0, 1.0)
    score += 15.0 * mood_norm
    score += 15.0 * (1.0 - stress_norm)
    if stress >= 7:
        reasons.append(f"Stress is high ({stress:.0f}/10).")

    hrv = checkin.get("hrv", None)
    rhr = checkin.get("rhr", None)

    if prev:
        if hrv is not None and prev.get("hrv") is not None:
            hrv = float(hrv)
            prev_hrv = float(prev["hrv"])
            if prev_hrv > 0:
                delta = (hrv - prev_hrv) / prev_hrv
                score += clamp(delta / 0.10, -1.0, 1.0) * 10.0
                if delta <= -0.08:
                    reasons.append(f"HRV dropped vs last check-in ({prev_hrv:.0f} → {hrv:.0f}).")
                elif delta >= 0.08:
                    reasons.append(f"HRV improved vs last check-in ({prev_hrv:.0f} → {hrv:.0f}).")

        if rhr is not None and prev.get("rhr") is not None:
            rhr = float(rhr)
            prev_rhr = float(prev["rhr"])
            delta = rhr - prev_rhr
            score += clamp((-delta) / 5.0, -1.0, 1.0) * 10.0
            if delta >= 4:
                reasons.append(f"Resting HR is up vs last check-in ({prev_rhr:.0f} → {rhr:.0f}).")
            elif delta <= -4:
                reasons.append(f"Resting HR is down vs last check-in ({prev_rhr:.0f} → {rhr:.0f}).")

    score = int(round(clamp(score, 0.0, 100.0)))
    if score >= 75:
        label = "GREEN"
        rec = "Proceed as planned. You can push intensity today if joints feel good."
    elif score >= 55:
        label = "YELLOW"
        rec = "Train, but reduce intensity/volume ~10–25%. Prioritize form + recovery."
    else:
        label = "RED"
        rec = "Recovery day or very light work. Walk/zone 2 + mobility + early sleep."

    return {"score": score, "label": label, "reasons": reasons, "recommendation": rec}


# -------------------------
# LLM (OpenAI-only)
# -------------------------

def have(key: str) -> bool:
    return bool(os.getenv(key, "").strip())

def run_openai(system: str, user: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        temperature=0.3,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()

def llm(system: str, user: str) -> str:
    if not have("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY missing in .env")
    return run_openai(system, user)


# -------------------------
# Helpers
# -------------------------

def parse_kv_pairs(s: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for t in s.strip().split():
        if "=" not in t:
            continue
        k, v = t.split("=", 1)
        k = k.strip().lower()
        v = v.strip()
        try:
            out[k] = float(v) if "." in v else int(v)
        except Exception:
            out[k] = v
    return out

def parse_remind_spec(spec: str) -> Tuple[Optional[datetime], str]:
    """
    Accepts:
      - "in 30m <text>", "in 2h <text>", "in 1d <text>"
      - "tomorrow HH:MM <text>"
      - "HH:MM <text>" (today)
      - "YYYY-MM-DD HH:MM <text>"
    Returns (due_dt, text). due_dt is local naive datetime.
    """
    s = spec.strip()

    # in 30m / in 2h / in 1d
    m = re.match(r"^in\s+(\d+)\s*([mhd])\s+(.+)$", s, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        text = m.group(3).strip()
        delta = {"m": timedelta(minutes=n), "h": timedelta(hours=n), "d": timedelta(days=n)}[unit]
        return datetime.now() + delta, text

    # tomorrow HH:MM text
    m = re.match(r"^tomorrow\s+(\d{1,2}):(\d{2})\s+(.+)$", s, re.IGNORECASE)
    if m:
        hh = int(m.group(1)); mm = int(m.group(2))
        text = m.group(3).strip()
        due = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0) + timedelta(days=1)
        return due, text

    # YYYY-MM-DD HH:MM text
    m = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})\s+(.+)$", s)
    if m:
        date_s = m.group(1)
        hh = int(m.group(2)); mm = int(m.group(3))
        text = m.group(4).strip()
        y, mo, d = [int(x) for x in date_s.split("-")]
        due = datetime(y, mo, d, hh, mm, 0)
        return due, text

    # HH:MM text (today)
    m = re.match(r"^(\d{1,2}):(\d{2})\s+(.+)$", s)
    if m:
        hh = int(m.group(1)); mm = int(m.group(2))
        text = m.group(3).strip()
        due = datetime.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
        # if time already passed today, assume tomorrow
        if due <= datetime.now():
            due = due + timedelta(days=1)
        return due, text

    return None, ""


# -------------------------
# CLI Commands (terminal use)
# -------------------------

def handle_command(text: str, memory: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    cmd = text.strip()

    if cmd.lower() in {"/help", "help"}:
        return True, HELP_TEXT, memory

    if cmd.lower() in {"/memory", "memory"}:
        return True, memory_pretty(memory), memory

    m = REMEMBER_RE.match(cmd)
    if m:
        key = m.group(1).strip()
        value = m.group(2).strip()
        memory_set(memory, key, value)
        save_memory(memory)
        return True, f"Saved {key} = {value}", memory

    m = FORGET_RE.match(cmd)
    if m:
        key = m.group(1).strip()
        ok = memory_delete(memory, key)
        if ok:
            save_memory(memory)
            return True, f"Deleted {key}", memory
        return True, f"Not found: {key}", memory

    m = NOTE_RE.match(cmd)
    if m:
        t2 = m.group(1).strip()
        memory.setdefault("notes", [])
        memory["notes"].append({"ts": _now_iso(), "text": t2})
        save_memory(memory)
        return True, "Note added.", memory

    m = CHECKIN_RE.match(cmd)
    if m:
        payload = m.group(1)
        kv = parse_kv_pairs(payload)
        kv["ts"] = _now_iso()
        memory.setdefault("checkins", [])
        memory["checkins"].append(kv)
        save_memory(memory)
        return True, "Check-in logged. Use /today.", memory

    if cmd.lower() == "/today":
        checkins = memory.get("checkins", [])
        if not checkins:
            return True, "No check-ins yet. Use /checkin sleep=... soreness=... mood=... stress=...", memory
        last = checkins[-1]
        prev = checkins[-2] if len(checkins) >= 2 else None
        r = compute_readiness(last, prev)
        lines = [f"Readiness: {r['label']} | {r['score']}/100"]
        for reason in r["reasons"]:
            lines.append(f"- {reason}")
        lines.append("")
        lines.append(f"Recommendation: {r['recommendation']}")
        return True, "\n".join(lines), memory

    m = HISTORY_RE.match(cmd)
    if m:
        n = int(m.group(1)) if m.group(1) else 7
        checkins = memory.get("checkins", [])
        if not checkins:
            return True, "No check-ins yet.", memory
        tail = checkins[-n:]
        lines = [f"Last {len(tail)} check-ins:"]
        for c in tail:
            lines.append(
                f"- {c.get('ts','?')} | sleep={c.get('sleep','?')} hrv={c.get('hrv','?')} rhr={c.get('rhr','?')} "
                f"soreness={c.get('soreness','?')} mood={c.get('mood','?')} stress={c.get('stress','?')}"
            )
        return True, "\n".join(lines), memory

    return False, "", memory


# -------------------------
# Approval actions
# -------------------------

def save_pending_action(memory: Dict[str, Any], action: Dict[str, Any]) -> str:
    action_id = f"act_{int(datetime.now().timestamp())}_{len(memory.get('pending_actions', {})) + 1}"
    memory.setdefault("pending_actions", {})
    memory["pending_actions"][action_id] = {"ts": _now_iso(), **action}
    save_memory(memory)
    return action_id

def execute_action(memory: Dict[str, Any], action_id: str) -> str:
    pending = memory.get("pending_actions", {})
    if action_id not in pending:
        return "Action not found."

    wrapper = pending[action_id]
    action = wrapper.get("action", wrapper)
    a_type = action.get("type")
    payload = action.get("payload", {})

    if a_type == "add_note":
        text = str(payload.get("text", "")).strip()
        if not text:
            return "Invalid note payload."
        memory.setdefault("notes", [])
        memory["notes"].append({"ts": _now_iso(), "text": text})
        del pending[action_id]
        save_memory(memory)
        return "Approved: Note added."

    if a_type == "log_checkin":
        entry = {"ts": _now_iso(), **payload}
        memory.setdefault("checkins", [])
        memory["checkins"].append(entry)
        del pending[action_id]
        save_memory(memory)
        return "Approved: Check-in logged."

    if a_type == "set_reminder":
        due = str(payload.get("due", "")).strip()
        text = str(payload.get("text", "")).strip()
        if not due or not text:
            return "Invalid reminder payload."
        memory.setdefault("reminders", [])
        rid = f"rem_{int(datetime.now().timestamp())}_{len(memory['reminders']) + 1}"
        memory["reminders"].append({
            "id": rid,
            "ts_created": _now_iso(),
            "due": due,
            "text": text,
            "sent": False,
        })
        del pending[action_id]
        save_memory(memory)
        return f"Approved: Reminder set for {due}."

    return f"Action type '{a_type}' not supported yet."
