#!/usr/bin/env python3
"""
Book with Google — Automatic Feed Generator via Acuity API
CPR Certification Labs (cprcertificationlabs.com)

This script fetches your real appointment types and available time slots
directly from Acuity Scheduling, then generates a Google inventory feed
(feed.xml) that is always up to date.

Usage:
    python3 feed_auto.py

Run this script once a day (e.g. via cron) to keep your Google feed fresh.
Upload the resulting feed.xml to the Reserve with Google Partner Portal,
or host it at a public URL and give Google that URL to auto-fetch.

Requirements:
    pip3 install requests

Acuity API credentials:
    Acuity → Business Settings → Integrations → API Credentials
    You need: User ID  and  API Key
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, date
import sys
import os

# =============================================================================
# CONFIGURATION
# Credentials are read from environment variables (set as GitHub Secrets).
# When running locally, you can set them in your terminal:
#   export ACUITY_USER_ID=12345678
#   export ACUITY_API_KEY=your_key_here
# =============================================================================

# --- Acuity API credentials (from GitHub Secrets / env vars) ---
ACUITY_USER_ID  = os.environ.get("ACUITY_USER_ID", "")
ACUITY_API_KEY  = os.environ.get("ACUITY_API_KEY", "")
ACUITY_OWNER_ID = os.environ.get("ACUITY_OWNER_ID", "")

# --- Google Partner info (from GitHub Secrets / env vars) ---
MERCHANT_ID   = os.environ.get("GOOGLE_MERCHANT_ID", "YOUR_MERCHANT_ID")
AGGREGATOR_ID = os.environ.get("GOOGLE_AGGREGATOR_ID", "YOUR_AGGREGATOR_ID")

# Optional custom Acuity subdomain — leave "" if you don't have one
ACUITY_SUBDOMAIN = os.environ.get("ACUITY_SUBDOMAIN", "")

# --- Business details ---
BUSINESS = {
    "name":    "CPR Certification Labs",
    "phone":   "+1-YOUR-PHONE-NUMBER",       # e.g. "+12125551234"
    "website": "https://www.cprcertificationlabs.com",
    "address": {
        "street":  "YOUR STREET ADDRESS",
        "city":    "YOUR CITY",
        "state":   "NY",
        "zip":     "YOUR ZIP",
        "country": "US",
    },
    "timezone": "America/New_York",
}

# --- How many weeks ahead to fetch availability ---
WEEKS_AHEAD = 8

# --- Output file ---
OUTPUT_FILE = "feed.xml"

# --- Service ID mapping ---
# Acuity appointment type NAMES → Google service IDs
# The keys must exactly match your Acuity appointment type names.
# Add/remove entries to match your actual Acuity appointment types.
SERVICE_ID_MAP = {
    "BLS HeartCode Complete":                       "bls-heartcode-complete",
    "BLS HeartCode Complete for Intelvio Students": "bls-heartcode-intelvio",
    "BLS HeartCode Skills Only":                    "bls-heartcode-skills",
    "ACLS HeartCode Complete":                      "acls-heartcode-complete",
    "ACLS HeartCode Skills Only":                   "acls-heartcode-skills",
    "PALS HeartCode Complete":                      "pals-heartcode-complete",
    "PALS HeartCode Skills Only":                   "pals-heartcode-skills",
    "BLS & PALS HeartCode Complete Combo":          "bls-pals-complete-combo",
    "BLS & PALS HeartCode Skills Only":             "bls-pals-skills-combo",
    "ACLS & BLS HeartCode Complete Combo":          "acls-bls-complete-combo",
    "ACLS & BLS HeartCode Skills Only":             "acls-bls-skills-combo",
    "ACLS & PALS HeartCode Complete Combo":         "acls-pals-complete-combo",
    "ACLS & PALS HeartCode Skills Only":            "acls-pals-skills-combo",
    "BLS, PALS, & ACLS HeartCode Complete Bundle":  "bls-pals-acls-complete-bundle",
    "BLS, PALS, & ACLS HeartCode Skills Only":      "bls-pals-acls-skills-bundle",
}

# =============================================================================
# ACUITY API CLIENT
# =============================================================================

ACUITY_BASE = "https://acuityscheduling.com/api/v1"

def acuity_get(endpoint, params=None):
    """Make an authenticated GET request to the Acuity API."""
    url = f"{ACUITY_BASE}/{endpoint}"
    try:
        resp = requests.get(
            url,
            params=params,
            auth=(ACUITY_USER_ID, ACUITY_API_KEY),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"  ✗ Acuity API error on {endpoint}: {e}")
        print(f"    Response: {e.response.text[:300]}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Network error on {endpoint}: {e}")
        return None


def fetch_appointment_types():
    """Fetch all active appointment types from Acuity."""
    types = acuity_get("appointment-types")
    if types is None:
        return []
    # Filter to only types we have in SERVICE_ID_MAP
    known = [t for t in types if t.get("name") in SERVICE_ID_MAP]
    unknown = [t["name"] for t in types if t.get("name") not in SERVICE_ID_MAP]
    if unknown:
        print(f"  ℹ  Skipping Acuity types not in SERVICE_ID_MAP: {unknown}")
    return known


def fetch_available_dates(appointment_type_id, month_str):
    """
    Fetch available dates for a type in a given month.
    month_str: "YYYY-MM"
    Returns list of date strings "YYYY-MM-DD"
    """
    data = acuity_get("availability/dates", params={
        "appointmentTypeID": appointment_type_id,
        "month": month_str,
    })
    if not data:
        return []
    return [d["date"] for d in data]


def fetch_available_times(appointment_type_id, date_str):
    """
    Fetch available time slots for a type on a given date.
    date_str: "YYYY-MM-DD"
    Returns list of dicts with 'time' (ISO) and 'slotsAvailable'
    """
    data = acuity_get("availability/times", params={
        "appointmentTypeID": appointment_type_id,
        "date": date_str,
    })
    if not data:
        return []
    return data  # each item: {"time": "2026-03-15T10:00:00-0500", "slotsAvailable": 8}


# =============================================================================
# FEED BUILDER
# =============================================================================

def format_duration(minutes):
    hours = minutes // 60
    mins  = minutes % 60
    if hours and mins:
        return f"PT{hours}H{mins}M"
    elif hours:
        return f"PT{hours}H"
    else:
        return f"PT{mins}M"


def acuity_booking_url(appointment_type_id):
    """Build the Acuity direct booking URL for a type."""
    if ACUITY_SUBDOMAIN:
        return (f"https://{ACUITY_SUBDOMAIN}.acuityscheduling.com"
                f"/schedule.php?appointmentTypeID={appointment_type_id}")
    return (f"https://app.acuityscheduling.com/schedule.php"
            f"?owner={ACUITY_OWNER_ID}&appointmentTypeID={appointment_type_id}")


def months_in_range(num_weeks):
    """Return all YYYY-MM month strings covered by the next num_weeks."""
    today = date.today()
    end   = today + timedelta(weeks=num_weeks)
    months = set()
    cur = today.replace(day=1)
    while cur <= end:
        months.add(cur.strftime("%Y-%m"))
        # advance one month
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)
    return sorted(months)


def build_feed(appointment_types, availability):
    """Build the Google feed XML tree."""
    namespace = "http://schema.googleapis.com/application/commerce/action/appointment"
    ET.register_namespace("", namespace)

    root = ET.Element("FeedMapping", attrib={
        "xmlns": namespace,
        "version": "1",
    })

    # ── Merchant ──
    merchant = ET.SubElement(root, "Merchant")
    ET.SubElement(merchant, "merchant_id").text = MERCHANT_ID
    ET.SubElement(merchant, "name").text        = BUSINESS["name"]

    tel = ET.SubElement(merchant, "telephone")
    ET.SubElement(tel, "number").text = BUSINESS["phone"]

    url_el = ET.SubElement(merchant, "url")
    ET.SubElement(url_el, "url_value").text = BUSINESS["website"]

    loc  = ET.SubElement(merchant, "location")
    addr = ET.SubElement(loc, "address")
    a = BUSINESS["address"]
    ET.SubElement(addr, "address_component", attrib={"type": "STREET_ADDRESS"}).text             = a["street"]
    ET.SubElement(addr, "address_component", attrib={"type": "LOCALITY"}).text                   = a["city"]
    ET.SubElement(addr, "address_component", attrib={"type": "ADMINISTRATIVE_AREA_LEVEL_1"}).text = a["state"]
    ET.SubElement(addr, "address_component", attrib={"type": "POSTAL_CODE"}).text                = a["zip"]
    ET.SubElement(addr, "address_component", attrib={"type": "COUNTRY"}).text                    = a["country"]

    ET.SubElement(merchant, "timezone").text = BUSINESS["timezone"]

    # ── Services ──
    for apt in appointment_types:
        svc_id = SERVICE_ID_MAP[apt["name"]]

        svc_el = ET.SubElement(root, "Service")
        ET.SubElement(svc_el, "merchant_id").text = MERCHANT_ID
        ET.SubElement(svc_el, "service_id").text  = svc_id
        ET.SubElement(svc_el, "name").text        = apt["name"]
        ET.SubElement(svc_el, "description").text = apt.get("description", apt["name"])

        price_cents = int(float(apt.get("price", "0")) * 100)
        price_el = ET.SubElement(svc_el, "price")
        ET.SubElement(price_el, "currency_code").text = "USD"
        ET.SubElement(price_el, "units").text = str(price_cents // 100)
        ET.SubElement(price_el, "nanos").text = str((price_cents % 100) * 10_000_000)

        total_duration = apt.get("duration", 60) + apt.get("paddingAfter", 0)
        ET.SubElement(svc_el, "duration").text = format_duration(total_duration)

        action = ET.SubElement(svc_el, "action_link")
        ET.SubElement(action, "url").text = acuity_booking_url(apt["id"])

    # ── Availability ──
    for apt in appointment_types:
        svc_id = SERVICE_ID_MAP[apt["name"]]
        slots  = availability.get(apt["id"], [])

        if not slots:
            continue

        avail_el = ET.SubElement(root, "ServiceAvailability")
        ET.SubElement(avail_el, "merchant_id").text = MERCHANT_ID
        ET.SubElement(avail_el, "service_id").text  = svc_id

        duration_min = apt.get("duration", 60)

        for slot in slots:
            raw_time      = slot["time"]       # e.g. "2026-03-15T10:00:00-0500"
            slots_avail   = slot.get("slotsAvailable", 1)

            # Parse start time — Acuity returns offset like "-0500", convert to "-05:00"
            try:
                # Acuity format: 2026-03-15T10:00:00-0500 (no colon in offset)
                if len(raw_time) == 24 and raw_time[-5] in ("+", "-"):
                    iso_time = raw_time[:-2] + ":" + raw_time[-2:]
                else:
                    iso_time = raw_time
                start_dt = datetime.fromisoformat(iso_time)
                end_dt   = start_dt + timedelta(minutes=duration_min)
                start_str = start_dt.strftime("%Y-%m-%dT%H:%M:%S%z")
                # Insert colon in timezone offset for RFC3339
                start_str = start_str[:-2] + ":" + start_str[-2:]
                end_str   = end_dt.strftime("%Y-%m-%dT%H:%M:%S%z")
                end_str   = end_str[:-2] + ":" + end_str[-2:]
            except Exception:
                # Fallback: use raw time as-is
                start_str = raw_time
                end_str   = raw_time

            slot_el = ET.SubElement(avail_el, "availability")
            ET.SubElement(slot_el, "start_time").text  = start_str
            ET.SubElement(slot_el, "end_time").text    = end_str
            ET.SubElement(slot_el, "spots_open").text  = str(slots_avail)
            ET.SubElement(slot_el, "spots_total").text = str(slots_avail)

    return root


def indent_xml(elem, level=0):
    pad = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = pad + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = pad
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = pad
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = pad
    return elem


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("Book with Google — Auto Feed Generator")
    print("Source: Acuity Scheduling API")
    print("=" * 60)

    # Validate config
    if not ACUITY_USER_ID or not ACUITY_API_KEY:
        print("\n✗ ERROR: ACUITY_USER_ID and ACUITY_API_KEY are not set.")
        print("  Set them as GitHub Secrets, or locally:")
        print("    export ACUITY_USER_ID=12345678")
        print("    export ACUITY_API_KEY=your_api_key")
        print("  Acuity → Business Settings → Integrations → API Credentials")
        sys.exit(1)

    # 1. Fetch appointment types
    print("\n[1/3] Fetching appointment types from Acuity...")
    appointment_types = fetch_appointment_types()
    if not appointment_types:
        print("  ✗ No matching appointment types found. Check SERVICE_ID_MAP.")
        sys.exit(1)
    for apt in appointment_types:
        print(f"  ✓  {apt['name']:40s} (ID: {apt['id']}, ${apt.get('price','?')}, {apt.get('duration','?')}min)")

    # 2. Fetch availability for all types across all months
    print(f"\n[2/3] Fetching availability for next {WEEKS_AHEAD} weeks...")
    months = months_in_range(WEEKS_AHEAD)
    print(f"  Months to check: {', '.join(months)}")

    availability = {}   # apt_id → list of slot dicts
    total_slots = 0

    for apt in appointment_types:
        apt_id   = apt["id"]
        apt_name = apt["name"]
        slots    = []
        today_str = date.today().isoformat()

        for month_str in months:
            dates = fetch_available_dates(apt_id, month_str)
            for d in dates:
                if d < today_str:
                    continue  # skip past dates
                times = fetch_available_times(apt_id, d)
                slots.extend(times)

        availability[apt_id] = slots
        total_slots += len(slots)
        print(f"  ✓  {apt_name:40s} → {len(slots):3d} slots")

    if total_slots == 0:
        print("\n  ⚠  No availability found for any service.")
        print("     Check that your Acuity calendar has future availability.")

    # 3. Build and write feed
    print(f"\n[3/3] Building feed.xml...")
    root = build_feed(appointment_types, availability)
    indent_xml(root)

    tree = ET.ElementTree(root)
    tree.write(OUTPUT_FILE, xml_declaration=True, encoding="UTF-8")

    print(f"\n{'=' * 60}")
    print(f"  ✓  Feed written: {OUTPUT_FILE}")
    print(f"     Services:     {len(appointment_types)}")
    print(f"     Total slots:  {total_slots}")
    print(f"{'=' * 60}")
    print("""
Next steps:
  1. Upload feed.xml to the Reserve with Google Partner Portal, OR
  2. Host this script on a server and point Google to its output URL.

Automate with cron (runs every day at 3am):
  crontab -e
  0 3 * * * /usr/bin/python3 /path/to/feed_auto.py
""")


if __name__ == "__main__":
    main()
