#!/usr/bin/env python3

import argparse
import json
import math
import os
import time
from datetime import date, datetime
from pathlib import Path

import requests

NTFY_TOPIC = os.getenv("NTFY_TOPIC", "plane_tracker_1998_2026_05_30")
HOME_LAT       = float(os.getenv("HOME_LAT") or 0)
HOME_LON       = float(os.getenv("HOME_LON") or 0)
HOME_RADIUS_KM = 10  # km — adjust if needed
POLL_INTERVAL = 120

# Minimum distance (km) a local zone aircraft must move before sending
# another position update. Prevents spam for circling/hovering aircraft.
LOCAL_NOTIFY_KM = 10

# Local zone — any military aircraft here notifies with position updates
LOCAL_ZONE_BOUNDS = {
    "lat_min": 51.65,
    "lat_max": 53.05,
    "lon_min": -3.15,
    "lon_max": -0.35,
}

# UK-wide — interesting types, first sighting per day
UK_BOUNDS = {
    "lat_min": 49.5,
    "lat_max": 61.0,
    "lon_min": -8.5,
    "lon_max":  2.5,
}

WARBIRD_WATCHLIST = [

    # -- Originals -------------------------------------------------------------
    {"reg": "G-BEDF", "name": "Sally B",            "desc": "B-17G Flying Fortress - only airworthy in Europe"},
    {"reg": "G-ASJV", "name": "MH434",              "desc": "Spitfire LF IXb - OFMC Duxford"},
    {"reg": "G-MRLL", "name": "Marinell",            "desc": "P-51D Mustang (44-13521)"},
    {"reg": "SP-MIL", "name": "SP-MIL",              "desc": "MiG-17 Lim-5 - only airworthy in Europe"},

    # -- UK Spitfires ----------------------------------------------------------
    {"reg": "G-AWII", "name": "AR501",               "desc": "Spitfire LF Vc - Shuttleworth Collection"},
    {"reg": "G-LFIX", "name": "ML407",               "desc": "Spitfire TR IX - The Grace Spitfire"},
    {"reg": "G-CICK", "name": "NH341",               "desc": "Spitfire TR IX Elizabeth - Aero Legends"},
    {"reg": "G-AIDN", "name": "G-AIDN",              "desc": "Spitfire"},
    {"reg": "G-PBIX", "name": "Porky II",            "desc": "Spitfire - The Suffolk Spitfire"},
    {"reg": "G-BMSB", "name": "MJ627",               "desc": "Spitfire T.9 two-seat (ex-Irish AC) - Biggin Hill"},
    {"reg": "AB910",  "name": "AB910",               "desc": "Spitfire Vb - BBMF, Dieppe and D-Day veteran"},

    # -- UK Strikemaster -------------------------------------------------------
    {"reg": "G-SOAF", "name": "G-SOAF",              "desc": "BAC Strikemaster - ex Sultan of Oman's Air Force"},
    {"reg": "G-RSAF", "name": "G-RSAF",              "desc": "BAC Strikemaster - ex Royal Saudi Air Force"},

    # -- UK P-51 ---------------------------------------------------------------
    {"reg": "G-SIJJ", "name": "Tall in the Saddle",  "desc": "P-51D Mustang - Hangar 11, North Weald"},
    {"reg": "G-JERK", "name": "Jersey Jerk",         "desc": "CA-18 Mustang Mk.21 - Commonwealth Aircraft Corporation"},

    # -- Canada ----------------------------------------------------------------
    {"reg": "C-GVRA", "name": "Mynarski Lancaster",  "desc": "Avro Lancaster FM213 - Canadian Warplane Heritage"},

    # -- USA: Heavy bombers ----------------------------------------------------
    {"reg": "N529B",  "name": "FIFI",                "desc": "B-29 Superfortress - CAF Dallas"},
    {"reg": "N69972", "name": "Doc",                 "desc": "B-29 Superfortress - Wichita"},
    {"reg": "N9323Z", "name": "Sentimental Journey", "desc": "B-17G - CAF Arizona Wing"},
    {"reg": "N5017N", "name": "Aluminum Overcast",   "desc": "B-17G - EAA Oshkosh"},
    {"reg": "N224J",  "name": "Witchcraft",          "desc": "B-24J Liberator - Collings Foundation"},
    {"reg": "N24927", "name": "Diamond Lil",         "desc": "B-24A Liberator (AM927) - CAF Dallas"},

    # -- UK: Rare survivors ----------------------------------------------------
    {"reg": "G-BPIV", "name": "Blenheim L6739",      "desc": "Bristol Blenheim Mk.IF - only airworthy in the world, ARC Duxford"},

    # -- USA: Mosquitos --------------------------------------------------------
    {"reg": "N114KA", "name": "Mosquito KA114",      "desc": "DH Mosquito FB.26 - Military Aviation Museum, Virginia Beach VA"},
    {"reg": "N959TV", "name": "Mosquito NS838",      "desc": "DH Mosquito T.III (flies as NS838) - Flying Heritage, Everett WA"},
    {"reg": "N474PZ", "name": "Mosquito PZ474",      "desc": "DH Mosquito FB.VI - Somers collection, Sacramento CA"},

    # -- USA: P-38 Lightnings --------------------------------------------------
    {"reg": "N17630", "name": "Glacier Girl",        "desc": "P-38F Lightning (41-7630) - recovered from Greenland icecap"},
    {"reg": "N25Y",   "name": "Flying Bulls P-38",   "desc": "P-38L Lightning - only P-38 in Europe, Flying Bulls, Salzburg"},
    {"reg": "N505MH", "name": "Collings P-38",       "desc": "P-38L Lightning (44-53186) - Collings Foundation"},
    {"reg": "N577JB", "name": "War Eagles P-38",     "desc": "P-38 Lightning (44-27053) - War Eagles Air Museum"},

    # -- USA: Other rare types -------------------------------------------------
    {"reg": "N712Z",  "name": "CAF Zero",            "desc": "Mitsubishi A6M3 Zero - CAF SoCal Wing, Camarillo CA"},

    # -- BBMF: RAF serials, no civil reg ---------------------------------------
    # Find hex codes at globe.adsbexchange.com on any BBMF display day
    # {"hex": "??????", "name": "BBMF Lancaster",    "desc": "Avro Lancaster PA474"},
    # {"hex": "??????", "name": "BBMF Hurricane",    "desc": "Hurricane LF363"},
    # {"hex": "??????", "name": "BBMF Hurricane",    "desc": "Hurricane PZ865"},
    # {"hex": "??????", "name": "BBMF Spitfire",     "desc": "Spitfire IIa P7350"},
    # {"hex": "??????", "name": "BBMF Spitfire",     "desc": "Spitfire PR XIX PS915"},
]

GLOBALLY_RARE_TYPES = {"B2","U2","WC135","B52","B1","RC135","E3","RQ4","WP3"}
DAILY_NOTIFY_TYPES = {
    # Jet fighters
    "F35","F22","F15","F16","A10","F18",
    # Apache only — other helicopters too noisy UK-wide
    "AH64",
    # Transport & tanker
    "C17","C130","A400","MRTT","KC135","B703","K35R",
    # ISR & patrol
    "P8","E7",
}

SKIP_TYPES = {
    "EF","EUFI",                          # Typhoon
    "CH47",                               # Chinook
    "AW10",                               # Merlin
    "LYNX","LYX",                         # Lynx
    "SA33","PUMA",                        # Puma
    "AW15","WILD",                        # Wildcat
    "H135","AS365",                       # SAR/police
}

# Always excluded regardless of zone — training types and light aircraft
# Add to this as you encounter unwanted types in the logs
EXCLUDE_TYPES = {
    "G12T","G115","G109",   # Grob Prefect/Tutor
    "TEXN","T6",            # Texan II
    "PC9","PC21",           # Pilatus trainers
}


MIN_ALT_FT    = 500
MAX_POSITIONS = 100

MIL_SOURCES = [
    "https://api.adsb.fi/v2/mil",
    "https://api.adsb.lol/v2/mil",
    "https://api.adsb.one/v2/mil",
]
WARBIRD_SOURCES = [
    "https://api.adsb.fi/v1",
    "https://api.adsb.lol/v2",
    "https://api.adsb.one/v2",
]

STATE_FILE = Path(__file__).parent / "tracker_state.json"
HEADERS    = {"User-Agent": "uk-plane-tracker/1.0 (personal project)"}


# -- State --------------------------------------------------------------------

def load_state():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "date": "", "airborne": {},
        "seen_uk": {}, "seen_global": {},
        "heartbeat_date": "", "daily_log": [],
        "flight_positions": {}, "local_positions": {},
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def maybe_reset_daily(state):
    today = str(date.today())
    if state.get("date") != today:
        state.update({
            "date": today,
            "seen_uk": {}, "seen_global": {},
            "daily_log": [], "flight_positions": {},
            "local_positions": {},
        })
    for key in ("airborne", "seen_uk", "seen_global", "local_positions"):
        state.setdefault(key, {})
    state.setdefault("daily_log", [])
    state.setdefault("flight_positions", {})
    state.setdefault("heartbeat_date", "")
    return state


# -- API ----------------------------------------------------------------------

def fetch_all_military():
    for url in MIL_SOURCES:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code == 404:
                log(f"Military source 404: {url}")
                continue
            r.raise_for_status()
            aircraft = r.json().get("ac", [])
            if aircraft:
                return aircraft
        except requests.RequestException as e:
            log(f"Military fetch error ({url}): {e}")
            continue
    log("All military sources returned empty or failed")
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


# -- Helpers ------------------------------------------------------------------

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


def type_matches(ac_type, code):
    """Match if ac_type equals code or code followed by up to 2 letter suffixes.
    Prevents e.g. 'B2' matching 'B212' (Bell 212 helicopter)."""
    if not ac_type.startswith(code):
        return False
    suffix = ac_type[len(code):]
    return suffix == "" or (len(suffix) <= 2 and suffix.isalpha())


def is_globally_rare(ac):
    t = get_type(ac)
    return any(type_matches(t, r) for r in GLOBALLY_RARE_TYPES)


def is_daily_notify(ac):
    t = get_type(ac)
    return any(type_matches(t, d) for d in DAILY_NOTIFY_TYPES)


def is_skipped_uk(ac):
    t = get_type(ac)
    return any(type_matches(t, s) for s in SKIP_TYPES)

def is_mlat(ac):
    """Aircraft positioned by multilateration rather than ADS-B — typically small/light types."""
    return (ac.get("type") or "").lower() == "mlat"

def is_excluded(ac):
    """Always-exclude list — training aircraft and unwanted light types."""
    t = get_type(ac)
    return any(type_matches(t, e) for e in EXCLUDE_TYPES)

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points."""
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return r * 2 * math.asin(math.sqrt(a))

def is_near_home(ac):
    if not HOME_LAT or not HOME_LON:
        return False
    lat, lon = ac.get("lat"), ac.get("lon")
    if lat is None or lon is None:
        return False
    return haversine_km(HOME_LAT, HOME_LON, lat, lon) <= HOME_RADIUS_KM

def has_moved(state, icao, lat, lon):
    """Return True if aircraft has moved more than LOCAL_NOTIFY_KM since last ping,
    or has no previous position recorded (first detection in zone)."""
    prev = state.get("local_positions", {}).get(icao)
    if not prev:
        return True
    try:
        dist = haversine_km(prev["lat"], prev["lon"], lat, lon)
        return dist >= LOCAL_NOTIFY_KM
    except Exception:
        return True


def update_local_position(state, icao, lat, lon):
    state.setdefault("local_positions", {})[icao] = {
        "lat": lat, "lon": lon,
        "time": datetime.now().strftime("%H:%M"),
    }


def map_url(ac):
    icao = (ac.get("hex") or "").strip()
    if icao:
        return f"https://globe.adsbexchange.com/?icao={icao.lower()}"
    lat, lon = ac.get("lat"), ac.get("lon")
    if lat is not None and lon is not None:
        return f"https://globe.adsbexchange.com/?lat={lat:.3f}&lon={lon:.3f}&zoom=10"
    return None


def reverse_geocode(lat, lon):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 10},
            headers=HEADERS,
            timeout=5,
        )
        if r.status_code == 200:
            addr = r.json().get("address", {})
            for field in ("city", "town", "village", "county"):
                if addr.get(field):
                    return addr[field]
    except Exception:
        pass
    return None


def get_location(ac):
    lat, lon = ac.get("lat"), ac.get("lon")
    if lat is not None and lon is not None:
        return reverse_geocode(lat, lon)
    return None


def format_message(ac, note="", location=None):
    lines = [note] if note else []
    if location:
        lines.append(f"Location: near {location}")
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


def log_sighting(state, zone, ac=None, name="", reg=""):
    entry = {"time": datetime.now().strftime("%H:%M"), "zone": zone, "name": name, "reg": reg}
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


def record_position(state, key, ac):
    if not (ac.get("lat") and ac.get("lon")):
        return
    alt = ac.get("alt_baro")
    try:    alt = int(alt) if alt and alt != "ground" else None
    except: alt = None
    track = ac.get("track")
    try:    track = int(track) if track else None
    except: track = None
    fp = state.setdefault("flight_positions", {})
    positions = fp.setdefault(key, [])
    positions.append({
        "time":  datetime.now().strftime("%H:%M"),
        "lat":   ac.get("lat"),
        "lon":   ac.get("lon"),
        "alt":   alt,
        "track": track,
    })
    if len(positions) > MAX_POSITIONS:
        positions.pop(0)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# -- Notifications ------------------------------------------------------------

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


# -- Checks -------------------------------------------------------------------

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
                log_sighting(state, "warbird_down", name=name, reg=key)
                del state["airborne"][key]
            continue

        record_position(state, key, ac)

# Home proximity — fires independently of the regular airborne notification
        home_key = f"home_{key}"
        if is_near_home(ac):
            if home_key not in state["airborne"]:
                state["airborne"][home_key] = True
                log(f"  {name} near home!")
                ntfy(
                    title=f"{name} near you!",
                    message=format_message(ac, location=get_location(ac)),
                    priority=4,
                    tags="airplane,house",
                    url=map_url(ac),
                )
        else:
            if home_key in state["airborne"]:
                del state["airborne"][home_key]
        
        if key not in state["airborne"]:
            state["airborne"][key] = True
            log(f"  {name} airborne - notifying")
            log_sighting(state, "warbird_up", ac=ac, name=name, reg=key)
            location = get_location(ac)
            ntfy(
                title=f"{name} is flying!",
                message=format_message(ac, note=bird["desc"], location=location),
                priority=3,
                tags="airplane",
                url=map_url(ac),
            )
        else:
            log(f"  {name} airborne (already notified)")

    return state


def check_military(state):
    all_mil  = fetch_all_military()
    airborne = [a for a in all_mil if is_airborne(a) and not is_mlat(a) and not is_excluded(a)]
    warbird_keys = {(b.get("reg") or b.get("hex", "")).upper() for b in WARBIRD_WATCHLIST}
    log(f"Military globally: {len(all_mil)}")

    # Pass 1: Globally rare — once per continuous flight via airborne dict
    for ac in airborne:
        if not is_globally_rare(ac):
            continue
        icao    = (ac.get("hex") or "").lower()
        ac_type = (ac.get("t") or ac.get("type") or "Unknown").strip()
        mil_key = f"mil_g_{icao}"
        if icao and mil_key not in state["airborne"]:
            state["airborne"][mil_key] = True
            log(f"  GLOBAL RARE: {ac_type}")
            log_sighting(state, "rare", ac=ac)
            location = get_location(ac)
            ntfy(
                title=f"{ac_type} tracked globally",
                message=format_message(ac, location=location),
                priority=5,
                tags="globe_with_meridians,rotating_light",
                url=map_url(ac),
            )

    # Pass 2: Local zone — notify on entry and when moved > LOCAL_NOTIFY_KM
    local = [a for a in airborne if in_bounds(a, LOCAL_ZONE_BOUNDS)]
    log(f"Military over local zone: {len(local)}")
    for ac in local:
        icao    = (ac.get("hex") or "").lower()
        ac_type = (ac.get("t") or ac.get("type") or "Military aircraft").strip()
        lat, lon = ac.get("lat"), ac.get("lon")
        if not icao or lat is None or lon is None:
            continue
        if has_moved(state, icao, lat, lon):
            update_local_position(state, icao, lat, lon)
            log(f"  LOCAL ZONE (moved): {ac_type}")
            log_sighting(state, "warks", ac=ac)
            location = get_location(ac)
            ntfy(
                title=f"Military overhead - {ac_type}",
                message=format_message(ac, note="In local zone", location=location),
                priority=2,
                tags="dart",
                url=map_url(ac),
            )
        else:
            log(f"  LOCAL ZONE (no movement): {ac_type}")

    # Remove local_positions for aircraft no longer in zone
    current_local = {(a.get("hex") or "").lower() for a in local}
    state["local_positions"] = {
        k: v for k, v in state.get("local_positions", {}).items()
        if k in current_local
    }

    # Pass 3: UK-wide — interesting types, first sighting per day
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
            location = get_location(ac)
            ntfy(
                title=f"Military UK: {ac_type}",
                message=format_message(ac, location=location),
                priority=3,
                tags="shield",
                url=map_url(ac),
            )

# Home proximity — all military aircraft
    for ac in airborne:
        icao     = (ac.get("hex") or "").lower()
        ac_type  = (ac.get("t") or ac.get("type") or "Military aircraft").strip()
        home_key = f"home_m_{icao}"
        if icao and is_near_home(ac):
            if home_key not in state["airborne"]:
                state["airborne"][home_key] = True
                log(f"  HOME PROXIMITY: {ac_type}")
                ntfy(
                    title=f"Military near you - {ac_type}",
                    message=format_message(ac, location=get_location(ac)),
                    priority=4,
                    tags="rotating_light,house",
                    url=map_url(ac),
                )
        else:
            if home_key in state["airborne"]:
                del state["airborne"][home_key]
    
    # Clean up airborne dict
    current_icaos = {(a.get("hex") or "").lower() for a in all_mil}
    for k in [k for k in list(state["airborne"])
              if k.startswith("mil_g_") and k[6:] not in current_icaos]:
        del state["airborne"][k]
    for k in [k for k in list(state["airborne"])
              if not k.startswith("mil_") and k not in current_icaos
              and k not in warbird_keys]:
        del state["airborne"][k]

    return state


# -- Entry point --------------------------------------------------------------

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
