#!/usr/bin/env python3
"""
Daily digest — reads today's sighting log from tracker_state.json
and sends a plain-text briefing via ntfy at 8pm.
Run via the digest.yml GitHub Actions workflow.
"""
 
import json
import os
from datetime import date
from pathlib import Path
 
import requests
 
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "plane_tracker_1998_2026_05_30")
STATE_FILE = Path(__file__).parent / "tracker_state.json"
 
WARBIRD_NAMES = ["Sally B", "MH434", "Marinell", "SP-MIL"]
 
 
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
                "Title": title,
                "Priority": "2",
                "Tags": "clipboard",
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
    except:
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
 
    if rare:
        lines.append(f"GLOBALLY RARE ({len(rare)})")
        for e in rare[:10]:
            lines.append(
                f"  {e['time']}  {e.get('type','?')}  {e.get('callsign','?')}{fmt_alt(e.get('alt'))}"
            )
        if len(rare) > 10:
            lines.append(f"  ... and {len(rare)-10} more")
        lines.append("")
 
    if warks:
        lines.append(f"WARWICKSHIRE ({len(warks)})")
        for e in warks[:10]:
            lines.append(
                f"  {e['time']}  {e.get('type','?')}  {e.get('callsign','?')}{fmt_alt(e.get('alt'))}"
            )
        if len(warks) > 10:
            lines.append(f"  ... and {len(warks)-10} more")
        lines.append("")
 
    if uk:
        lines.append(f"UK MILITARY ({len(uk)})")
        for e in uk[:10]:
            lines.append(
                f"  {e['time']}  {e.get('type','?')}  {e.get('callsign','?')}{fmt_alt(e.get('alt'))}"
            )
        if len(uk) > 10:
            lines.append(f"  ... and {len(uk)-10} more")
        lines.append("")
 
    lines.append("WARBIDS")
    for name in WARBIRD_NAMES:
        up   = next((e for e in w_up if e.get("name") == name), None)
        down = next((e for e in w_dn if e.get("name") == name), None)
        if up and down:
            lines.append(f"  {name}: {up['time']} - {down['time']}")
        elif up:
            lines.append(f"  {name}: flying from {up['time']}")
        else:
            lines.append(f"  {name}: not tracked")
    lines.append("")
    lines.append("Paste into Claude Project for analysis.")
 
    return "\n".join(lines)
 
 
def main():
    today = str(date.today())
    log   = load_log()
    print(f"Sightings today: {len(log)}")
 
    msg = build_digest(log, today)
    print(msg)
    send_ntfy(f"Daily Briefing — {today}", msg)
 
 
if __name__ == "__main__":
    main()
 
