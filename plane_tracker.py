#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "plane_tracker_1998_2026_05_30")
POLL_INTERVAL = 120

WARWICKSHIRE_BOUNDS = {
    "lat_min": 51.9, "lat_max": 52.8,
    "lon_min": -2.1, "lon_max": -1.1,
}
UK_BOUNDS = {
    "lat_min": 49.5, "lat_max": 61.0,
    "lon_min": -8.5, "lon_max":  2.5,
}

WARBIRD_WATCHLIST = [
    {"reg": "G-BEDF", "name": "Sally B",        "desc": "B-17G Flying Fortress - only airworthy in Europe"},
    {"reg": "G-ASJV", "name": "MH434",          "desc": "Spitfire LF IXb - OFMC Duxford"},
    {"reg": "G-MRLL", "name": "Marinell",        "desc": "P-51D Mustang (44-13521)"},
    {"reg": "SP-MIL", "name": "SP-MIL",          "desc": "MiG-17 Lim-5 - only airworthy in Europe"},

    {"reg": "G-AWII", "name": "AR501",           "desc": "Spitfire LF Vc - Shuttleworth Collection"},
    {"reg": "G-LFIX", "name": "ML407",           "desc": "Spitfire TR IX - The Grace Spitfire"},
    {"reg": "G-CICK", "name": "NH341",           "desc": "Spitfire TR IX Elizabeth - Aero Legends"},
    {"reg": "G-AIDN", "name": "G-AIDN", "desc": "Spitfire"},
    {"reg": "G-SOAF", "name": "G-SOAF", "desc": "BAC Strikemaster - ex Sultan of Oman's Air Force"},
    {"reg": "G-RSAF", "name": "G-RSAF", "desc": "BAC Strikemaster - ex Royal Saudi Air Force"},
    {"reg": "G-PBIX", "name": "G-PBIX", "desc": "Porky II"},



    {"reg": "G-SIJJ", "name": "Tall in the Saddle", "desc": "P-51D Mustang - Hangar 11, North Weald"},

    {"reg": "C-GVRA", "name": "Mynarski Lancaster", "desc": "Avro Lancaster FM213 - Canadian Warplane Heritage"},

    {"reg": "N529B",  "name": "FIFI",            "desc": "B-29 Superfortress - CAF Dallas"},
    {"reg": "N69972", "name": "Doc",             "desc": "B-29 Superfortress - Wichita"},
    {"reg": "N9323Z", "name": "Sentimental Journey", "desc": "B-17G - CAF Arizona Wing"},
    {"reg": "N5017N", "name": "Aluminum Overcast",   "desc": "B-17G - EAA Oshkosh"},
    {"reg": "N224J",  "name": "Witchcraft",      "desc": "B-24J Liberator - Collings Foundation"},

  # --- Rare types added: rarest survivors, roughly <10 flying worldwide ---
    # All reg-based, so they get tracked globally (like FIFI/Doc above), not just over the UK.
    # Most of these live in the US; only the Blenheim, G-BMSB and BBMF AB910 are UK-based.
 
    {"reg": "G-BPIV", "name": "Blenheim L6739",  "desc": "Bristol Blenheim Mk.IF - ONLY airworthy in the world, ARC Duxford"},
    {"reg": "N24927", "name": "Diamond Lil",     "desc": "B-24A Liberator (AM927) - only regularly-flying B-24, CAF Dallas"},
 
    {"reg": "N114KA", "name": "Mosquito KA114",  "desc": "DH Mosquito FB.26 - Military Aviation Museum, Virginia Beach VA"},
    {"reg": "N959TV", "name": "Mosquito TV959",  "desc": "DH Mosquito T.III (flown as NS838) - Flying Heritage, Everett WA"},
    {"reg": "N474PZ", "name": "Mosquito PZ474",  "desc": "DH Mosquito FB.VI - Charles Somers collection, Sacramento CA"},
    # {"reg": "??????", "name": "Mosquito NZ2308", "desc": "DH Mosquito T.43 - Lewis Air Legends TX (CONFIRM REG)"},
    # {"reg": "C-?????", "name": "Mosquito VR796", "desc": "DH Mosquito B.35 - Bob Jens, Canada (not flown for years)"},
 
    {"reg": "N17630", "name": "Glacier Girl",    "desc": "P-38F Lightning (41-7630) - Air Legends Foundation, San Antonio TX"},
    {"reg": "N25Y",   "name": "Flying Bulls P-38", "desc": "P-38L Lightning - ONLY P-38 in Europe, Flying Bulls, Salzburg AT"},
    {"reg": "N505MH", "name": "Collings P-38",   "desc": "P-38L Lightning (44-53186) - Collings Foundation, Stow MA"},
    {"reg": "N577JB", "name": "War Eagles P-38", "desc": "P-38 Lightning (44-27053) - War Eagles Air Museum, Santa Teresa NM"},
    # {"reg": "??????", "name": "Jandina III",    "desc": "P-38J Lightning (42-103988) - Flying Heritage, Everett WA (CONFIRM REG)"},
 
    {"reg": "N712Z",  "name": "CAF Zero",        "desc": "Mitsubishi A6M3 Zero - CAF SoCal Wing, Camarillo CA (P&W engine)"},
    # {"reg": "??????", "name": "Planes of Fame Zero", "desc": "A6M5 w/ original Sakae engine - Chino CA (CONFIRM REG)"},
 
    {"reg": "G-BMSB", "name": "MJ627",           "desc": "Spitfire T.9 two-seat (ex-Irish AC) - Biggin Hill; damaged in May-2025 forced landing"},
 
    # BBMF - RAF serials, no civil reg. Find hex codes at globe.adsbexchange.com
    # {"hex": "??????", "name": "BBMF Lancaster",  "desc": "Avro Lancaster PA474"},
    # {"hex": "??????", "name": "BBMF Hurricane",  "desc": "Hurricane LF363"},
    # {"hex": "??????", "name": "BBMF Hurricane",  "desc": "Hurricane PZ865"},
    # {"hex": "??????", "name": "BBMF Spitfire",   "desc": "Spitfire IIa P7350"},
    # {"hex": "??????", "name": "BBMF Spitfire",   "desc": "Spitfire PR XIX PS915"},
    # {"hex": "??????", "name": "BBMF Spitfire Vb", "desc": "Spitfire Vb AB910 - Dieppe & D-Day veteran; back flying Jan 2026"},
]

GLOBALLY_RARE_TYPES = {"B2","U2","WC135","B52","B1","RC135","E3","RQ4","WP3"}
DAILY_NOTIFY_TYPES  = {"F35","F22","F15","F16","A10","C17","P8","E7","AH64","F18"}
SKIP_TYPES          = {"EF","C130","A400","CH47","MRTT","H135","AS365"}

MIN_ALT_FT = 500

MIL_BASE = "https://api.adsb.fi/v1"
WARBIRD_SOURCES = [
    "https://api.adsb.fi/v1",
    "https://api.adsb.lol/v2",
    "https://api.adsb.one/v2",
]

STATE_FILE = Path(__file__).parent / "tracker_state.json"
HEADERS    = {"User-Agent": "uk-plane-tracker/1.0 (personal project)"}


def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "date": "", "airborne": {},
        "seen_warks": {}, "seen_uk": {}, "seen_global": {},
        "heartbeat_date": "", "daily_log": [],
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def maybe_reset_daily(state):
    today = str(date.today())
    if state.get("date") != today:
        state.update({
            "date": today,
            "seen_warks": {}, "seen_uk": {}, "seen_global": {},
            "daily_log": [],
        })
    for key in ("airborne", "seen_warks", "seen_uk", "seen_global"):
        state.setdefault(key, {})
    state.setdefault("daily_log", [])
    state.setdefault("heartbeat_date", "")
    return state


def fetch_all_military():
    try:
        r = requests.get(f"{MIL_BASE}/mil", headers=HEADERS, timeout=15)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json().get("ac", [])
    except requests.RequestException as e:
        log(f"Military fetch error: {e}")
        return []


def fetch_by_reg(reg):
    for base in WARBIRD_SOURCES:
        try:
            r = requests.get(f"{base}/reg/{reg.upper()}", headers=HEADERS, timeout=10)
            if r.status_code == 200:
                results = r.json().get("ac", [])
                if results:
                    return results[0]
        except requests.RequestException:
            continue
    return None


def fetch_by_hex(hex_code):
    for base in WARBIRD_SOURCES:
        try:
            r = requests.get(f"{base}/icao/{hex_code.lower()}", headers=HEADERS, timeout=10)
            if r.status_code == 200:
                results = r.json().get("ac", [])
                if results:
                    return results[0]
        except requests.RequestException:
            continue
    return None


def in_bounds(ac, bounds):
    lat, lon = ac.get("lat"), ac.get("lon")
    if lat is None or lon is None:
        return False
    return (bounds["lat_min"] <= lat <= bounds["lat_max"] and
            bounds["lon_min"] <= lon <= bounds["lon_max"])


def is_airborne(ac):
    alt = ac.get("alt_baro", 0)
    gs  = ac.get("gs", 0) or 0
    if alt == "ground":
        return False
    try:
        return int(alt) >= MIN_ALT_FT
    except (TypeError, ValueError):
        return float(gs) > 30


def get_type(ac):
    return (ac.get("t") or ac.get("type") or "").upper().replace("-", "").replace(" ", "")


def is_globally_rare(ac):
    t = get_type(ac)
    return any(r in t for r in GLOBALLY_RARE_TYPES)


def is_daily_notify(ac):
    t = get_type(ac)
    return any(d in t for d in DAILY_NOTIFY_TYPES)


def is_skipped_uk(ac):
    t = get_type(ac)
    return any(s in t for s in SKIP_TYPES)


def map_url(ac):
    icao = (ac.get("hex") or "").strip()
    if icao:
        return f"https://globe.adsbexchange.com/?icao={icao.lower()}"
    lat, lon = ac.get("lat"), ac.get("lon")
    if lat is not None and lon is not None:
        return f"https://globe.adsbexchange.com/?lat={lat:.3f}&lon={lon:.3f}&zoom=10"
    return None


def format_message(ac, note=""):
    lines = [note] if note else []
    reg      = (ac.get("r")      or "").strip()
    callsign = (ac.get("flight") or "").strip()
    ac_type  = (ac.get("t")      or ac.get("type") or "").strip()
    alt      = ac.get("alt_baro")
    gs       = ac.get("gs")
    track    = ac.get("track")
    squawk   = ac.get("squawk", "")
    if reg:      lines.append(f"Reg: {reg}")
    if callsign: lines.append(f"Callsign: {callsign}")
    if ac_type:  lines.append(f"Type: {ac_type}")
    if squawk:   lines.append(f"Squawk: {squawk}")
    if alt == "ground":
        lines.append("On ground")
    elif alt is not None:
        try:    lines.append(f"Alt: {int(alt):,} ft")
        except: pass
    if gs is not None:
        try:    lines.append(f"Speed: {int(gs)} kts")
        except: pass
    if track is not None:
        try:    lines.append(f"Heading: {int(track)} deg")
        except: pass
    return "\n".join(lines)


def log_sighting(state, zone, ac=None, name=""):
    entry = {
        "time": datetime.now().strftime("%H:%M"),
        "zone": zone,
        "name": name,
    }
    if ac:
        alt = ac.get("alt_baro")
        if alt and alt != "ground":
            try: alt = int(alt)
            except: alt = None
        else:
            alt = None
        entry["type"]     = (ac.get("t") or ac.get("type") or "").strip()
        entry["callsign"] = (ac.get("flight") or "").strip()
        entry["alt"]      = alt
    state.setdefault("daily_log", []).append(entry)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def ntfy(title, message, priority=3, tags="", url=None):
    headers = {"Title": title, "Priority": str(priority)}
    if tags:
        headers["Tags"] = tags
    if url:
        headers["Click"] = url
    try:
        r = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers=headers,
            timeout=10,
        )
        r.raise_for_status()
        log(f"  -> ntfy sent: {title}")
    except requests.RequestException as e:
        log(f"  -> ntfy FAILED: {e}")


def check_heartbeat(state):
    today = str(date.today())
    if state.get("heartbeat_date") != today:
        state["heartbeat_date"] = today
        log("  Sending daily heartbeat")
        ntfy(
            title="Plane Tracker - running",
            message=f"Still active. Polling regularly.\n{today}",
            priority=2,
            tags="white_check_mark",
        )
    return state


def check_warbids(state):
    for bird in WARBIRD_WATCHLIST:
        reg  = bird.get("reg")
        hex_ = bird.get("hex")
        name = bird["name"]
        key  = (reg or hex_).upper()
        ac = fetch_by_reg(reg) if reg else fetch_by_hex(hex_)
        time.sleep(0.4)
        if ac is None or not is_airborne(ac):
            if key in state["airborne"]:
                log(f"  {name} landed")
                log_sighting(state, "warbird_down", name=name)
                del state["airborne"][key]
            continue
        if key not in state["airborne"]:
            state["airborne"][key] = True
            log(f"  {name} airborne - notifying")
            log_sighting(state, "warbird_up", ac=ac, name=name)
            ntfy(
                title=f"{name} is flying!",
                message=format_message(ac, note=bird["desc"]),
                priority=3,
                tags="airplane",
                url=map_url(ac),
            )
        else:
            log(f"  {name} airborne (already notified)")
    return state


def check_military(state):
    all_mil = fetch_all_military()
    airborne = [a for a in all_mil if is_airborne(a)]
    warbird_keys = {(b.get("reg") or b.get("hex", "")).upper() for b in WARBIRD_WATCHLIST}
    log(f"Military globally: {len(all_mil)}")

    for ac in airborne:
        if not is_globally_rare(ac):
            continue
        icao    = (ac.get("hex") or "").lower()
        ac_type = (ac.get("t") or ac.get("type") or "Unknown").strip()
        if icao and icao not in state["seen_global"]:
            state["seen_global"][icao] = True
            log(f"  GLOBAL RARE: {ac_type}")
            log_sighting(state, "rare", ac=ac)
            ntfy(
                title=f"{ac_type} tracked globally",
                message=format_message(ac),
                priority=5,
                tags="globe_with_meridians,rotating_light",
                url=map_url(ac),
            )

    warks = [a for a in airborne if in_bounds(a, WARWICKSHIRE_BOUNDS)]
    log(f"Military over Warwickshire: {len(warks)}")
    for ac in warks:
        icao    = (ac.get("hex") or "").lower()
        ac_type = (ac.get("t") or ac.get("type") or "Military aircraft").strip()
        if icao and icao not in state["seen_warks"]:
            state["seen_warks"][icao] = True
            log(f"  WARWICKSHIRE: {ac_type}")
            log_sighting(state, "warks", ac=ac)
            ntfy(
                title=f"Military overhead - {ac_type}",
                message=format_message(ac, note="In Warwickshire airspace"),
                priority=4,
                tags="dart",
                url=map_url(ac),
            )

    uk = [a for a in airborne if in_bounds(a, UK_BOUNDS)]
    log(f"Military in UK: {len(uk)}")
    for ac in uk:
        icao    = (ac.get("hex") or "").lower()
        ac_type = (ac.get("t") or ac.get("type") or "Unknown military").strip()
        if not icao or is_globally_rare(ac) or is_skipped_uk(ac):
            continue
        if is_daily_notify(ac) and icao not in state["seen_uk"]:
            state["seen_uk"][icao] = True
            log(f"  UK: {ac_type}")
            log_sighting(state, "uk", ac=ac)
            ntfy(
                title=f"Military UK: {ac_type}",
                message=format_message(ac),
                priority=3,
                tags="shield",
                url=map_url(ac),
            )

    current = {(a.get("hex") or "").lower() for a in all_mil}
    for k in [k for k in list(state["airborne"]) if k not in current and k not in warbird_keys]:
        del state["airborne"][k]
    return state


def run_once():
    log("-- Poll --")
    state = maybe_reset_daily(load_state())
    state = check_heartbeat(state)
    state = check_warbids(state)
    state = check_military(state)
    save_state(state)
    log("-- Done --")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        log("Sending test notification...")
        ntfy(
            title="Plane Tracker - test",
            message="Notifications working.",
            priority=3,
            tags="white_check_mark",
        )
        return

    if args.once:
        run_once()
        return

    log("Running continuously. Ctrl+C to stop.")
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            log("Stopped.")
            break
        except Exception as e:
            log(f"Error: {e}")
        log(f"Sleeping {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
