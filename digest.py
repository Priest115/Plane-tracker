#!/usr/bin/env python3
"""
Daily digest — reads today's sighting log from tracker_state.json
and sends a plain-text briefing via ntfy at 8pm UTC.
Run via digest.yml GitHub Actions workflow, triggered by a separate cron-job.org job.
"""
 
import json
import os
from datetime import date
from pathlib import Path
 
import requests
 
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "plane_tracker_1998_2026_05_30")
STATE_FILE = Path(__file__).parent / "tracker_state.json"
 
 
def load_log():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f).get("daily_log", [])
        except (json.JSONDecodeError, OSError):
            pass
    return []
 
 
def send_ntfy(title, message):
    try:
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title":    title,
                "Priority": "2",
                "Tags":     "clipboard",
            },
            timeout=10,
        )
        r.raise_for_status()
        print(f"Digest sent: {len(message)} chars")
    except requests.RequestException as e:
        print(f"ntfy error: {e}")
 
 
def fmt_alt(alt):
    if not alt:
        return ""
    try:
        return f"  {int(alt):,}ft"
    except Exception:
        return ""
 
 
def build_digest(log, today):
    rare  = [e for e in log if e.get("zone") == "rare"]
    warks = [e for e in log if e.get("zone") == "warks"]
    uk    = [e for e in log if e.get("zone") == "uk"]
    w_up  = [e for e in log if e.get("zone") == "warbird_up"]
    w_dn  = [e for e in log if e.get("zone") == "warbird_down"]
 
    lines = [f"UK Air Activity — {today}", ""]
 
    if not (rare or warks or uk or w_up):
        lines += [
            "Nothing notable tracked today.",
            "",
            "Tracker is running normally.",
        ]
        return "\n".join(lines)
 
    # ── Globally rare ──────────────────────────────────────────────────────
    if rare:
        lines.append(f"GLOBALLY RARE ({len(rare)})")
        for e in rare[:15]:
            lines.append(
                f"  {e.get('time','?')}  {e.get('type','?')}  "
                f"{e.get('callsign','?')}{fmt_alt(e.get('alt'))}"
            )
        if len(rare) > 15:
            lines.append(f"  ...and {len(rare) - 15} more")
        lines.append("")
 
    # ── Warwickshire ───────────────────────────────────────────────────────
    if warks:
        lines.append(f"WARWICKSHIRE ({len(warks)})")
        for e in warks[:15]:
            lines.append(
                f"  {e.get('time','?')}  {e.get('type','?')}  "
                f"{e.get('callsign','?')}{fmt_alt(e.get('alt'))}"
            )
        if len(warks) > 15:
            lines.append(f"  ...and {len(warks) - 15} more")
        lines.append("")
 
    # ── UK military ────────────────────────────────────────────────────────
    if uk:
        lines.append(f"UK MILITARY ({len(uk)})")
        for e in uk[:15]:
            lines.append(
                f"  {e.get('time','?')}  {e.get('type','?')}  "
                f"{e.get('callsign','?')}{fmt_alt(e.get('alt'))}"
            )
        if len(uk) > 15:
            lines.append(f"  ...and {len(uk) - 15} more")
        lines.append("")
 
    # ── Warbids ────────────────────────────────────────────────────────────
    if w_up:
        flew_names = {e.get("name") for e in w_up}
        lines.append(f"WARBIDS FLYING ({len(flew_names)})")
        for name in sorted(flew_names):
            up   = next((e for e in w_up if e.get("name") == name), None)
            down = next((e for e in w_dn if e.get("name") == name), None)
            if up and down:
                lines.append(f"  {name}: {up.get('time','?')} - {down.get('time','?')}")
            elif up:
                lines.append(f"  {name}: {up.get('time','?')} (still up at digest time)")
        lines.append("")
    else:
        lines.append("WARBIDS")
        lines.append("  None tracked today")
        lines.append("")
 
    lines.append("Paste into Claude Project for analysis.")
    return "\n".join(lines)
 
 
def main():
    today = str(date.today())
    log   = load_log()
    print(f"Sightings in log: {len(log)}")
    msg = build_digest(log, today)
    print(msg)
    send_ntfy(f"Daily Briefing — {today}", msg)
 
 
if __name__ == "__main__":
    main()
