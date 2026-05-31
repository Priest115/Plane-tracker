#!/usr/bin/env python3
"""
Daily digest — reads today's sighting log and flight positions from
tracker_state.json, reverse-geocodes routes via Nominatim, and sends
a plain-text briefing via ntfy at 8pm UTC.
"""

import json
import time
from datetime import date, datetime
from pathlib import Path

import requests

import os
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "plane_tracker_1998_2026_05_30")

STATE_FILE = Path(__file__).parent / "tracker_state.json"
NOM_HEADERS = {"User-Agent": "uk-plane-tracker/1.0 (personal project)"}


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
                return {
                    "daily_log":        data.get("daily_log", []),
                    "flight_positions": data.get("flight_positions", {}),
                }
        except (json.JSONDecodeError, OSError):
            pass
    return {"daily_log": [], "flight_positions": {}}


def send_ntfy(title, message):
    try:
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "2", "Tags": "clipboard"},
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


def flight_duration(start_str, end_str):
    try:
        s = datetime.strptime(start_str, "%H:%M")
        e = datetime.strptime(end_str,   "%H:%M")
        mins = int((e - s).total_seconds() / 60)
        if mins < 0:
            mins += 1440
        h, m = divmod(mins, 60)
        return f"{h}h {m:02d}m" if h else f"{m}m"
    except Exception:
        return ""


def reverse_geocode(lat, lon):
    """Return nearest town/county via OpenStreetMap Nominatim (free, no key)."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 10},
            headers=NOM_HEADERS,
            timeout=6,
        )
        if r.status_code == 200:
            addr = r.json().get("address", {})
            for field in ("city", "town", "village", "county"):
                if addr.get(field):
                    return addr[field]
    except Exception:
        pass
    return f"{lat:.1f}, {lon:.1f}"


def describe_route(positions):
    """
    Reverse-geocode start, midpoint, and end of a flight path.
    Returns (route_string, peak_alt_ft).
    Respects Nominatim's 1 req/sec rate limit.
    """
    valid = [p for p in positions if p.get("lat") and p.get("lon")]
    if not valid:
        return None, None

    peak_alt = max((p["alt"] for p in valid if p.get("alt")), default=None)

    if len(valid) == 1:
        loc = reverse_geocode(valid[0]["lat"], valid[0]["lon"])
        return f"near {loc}", peak_alt

    start = valid[0]
    end   = valid[-1]

    start_loc = reverse_geocode(start["lat"], start["lon"])
    time.sleep(1.2)
    end_loc = reverse_geocode(end["lat"], end["lon"])

    if len(valid) >= 6:
        mid = valid[len(valid) // 2]
        time.sleep(1.2)
        mid_loc = reverse_geocode(mid["lat"], mid["lon"])
        if mid_loc not in (start_loc, end_loc):
            return f"{start_loc} - {mid_loc} - {end_loc}", peak_alt

    if start_loc == end_loc:
        return f"local flying near {start_loc}", peak_alt
    return f"{start_loc} - {end_loc}", peak_alt


def build_digest(state, today):
    log         = state["daily_log"]
    flight_pos  = state["flight_positions"]

    rare  = [e for e in log if e.get("zone") == "rare"]
    warks = [e for e in log if e.get("zone") == "warks"]
    uk    = [e for e in log if e.get("zone") == "uk"]
    w_up  = [e for e in log if e.get("zone") == "warbird_up"]
    w_dn  = [e for e in log if e.get("zone") == "warbird_down"]

    lines = [f"UK Air Activity - {today}", ""]

    if not (rare or warks or uk or w_up):
        lines += ["Nothing notable tracked today.", "", "Tracker is running normally."]
        return "\n".join(lines)

    # -- Globally rare -------------------------------------------------------
    if rare:
        lines.append(f"GLOBALLY RARE ({len(rare)})")
        for e in rare[:15]:
            lines.append(
                f"  {e.get('time','?')}  {e.get('type','?')}  "
                f"{e.get('callsign','?')}{fmt_alt(e.get('alt'))}"
            )
        if len(rare) > 15:
            lines.append(f"  ...and {len(rare)-15} more")
        lines.append("")

    # -- Warwickshire --------------------------------------------------------
    if warks:
        lines.append(f"WARWICKSHIRE ({len(warks)})")
        for e in warks[:15]:
            lines.append(
                f"  {e.get('time','?')}  {e.get('type','?')}  "
                f"{e.get('callsign','?')}{fmt_alt(e.get('alt'))}"
            )
        if len(warks) > 15:
            lines.append(f"  ...and {len(warks)-15} more")
        lines.append("")

    # -- UK military ---------------------------------------------------------
    if uk:
        lines.append(f"UK MILITARY ({len(uk)})")
        for e in uk[:15]:
            lines.append(
                f"  {e.get('time','?')}  {e.get('type','?')}  "
                f"{e.get('callsign','?')}{fmt_alt(e.get('alt'))}"
            )
        if len(uk) > 15:
            lines.append(f"  ...and {len(uk)-15} more")
        lines.append("")

    # -- Warbids -------------------------------------------------------------
    if w_up:
        flew_names = {e.get("name") for e in w_up if e.get("name")}
        lines.append(f"WARBIDS FLYING ({len(flew_names)})")

        for name in sorted(flew_names):
            up   = next((e for e in w_up if e.get("name") == name), None)
            down = next((e for e in w_dn if e.get("name") == name), None)
            reg  = (up or {}).get("reg", "")

            if up and down:
                dur = flight_duration(up.get("time",""), down.get("time",""))
                dur_str = f" ({dur})" if dur else ""
                lines.append(f"  {name}: {up.get('time','?')} - {down.get('time','?')}{dur_str}")
            elif up:
                lines.append(f"  {name}: {up.get('time','?')} (still up at digest time)")

            # Route from logged positions
            if reg and flight_pos.get(reg):
                route, peak = describe_route(flight_pos[reg])
                if route:
                    lines.append(f"    Route: {route}")
                if peak:
                    lines.append(f"    Peak: {peak:,}ft")

        lines.append("")
    else:
        lines.append("WARBIDS")
        lines.append("  None tracked today")
        lines.append("")

    lines.append("Paste into Claude Project for analysis.")
    return "\n".join(lines)


def main():
    today = str(date.today())
    state = load_state()
    print(f"Log entries: {len(state['daily_log'])}")
    print(f"Aircraft with position data: {len(state['flight_positions'])}")
    msg = build_digest(state, today)
    print(msg)
    send_ntfy(f"Daily Briefing - {today}", msg)


if __name__ == "__main__":
    main()
