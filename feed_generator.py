#!/usr/bin/env python3
"""
Book with Google — Inventory Feed Generator
CPR Certification Labs (cprcertificationlabs.com)

This script generates a Google Reserve with Google (Book with Google)
inventory feed XML file for the Redirect Flow integration.

Usage:
  1. Edit the CONFIGURATION section below to match your real business data.
  2. Run: python3 feed_generator.py
  3. Upload the generated feed.xml to the Reserve with Google Partner Portal.

Documentation:
  https://developers.google.com/actions-center/verticals/appointments/redirect
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import copy

# =============================================================================
# ========================== CONFIGURATION ====================================
# =============================================================================

# --- Your Business Info (from Google Partner Portal after approval) ---
MERCHANT_ID    = "YOUR_MERCHANT_ID"       # Provided by Google after Partner approval
AGGREGATOR_ID  = "YOUR_AGGREGATOR_ID"     # Provided by Google after Partner approval
PARTNER_NAME   = "CPR Certification Labs"

# --- Acuity Scheduling ---
# Find your Owner ID: Acuity → Business Settings → Scheduling Page Link
# Your link looks like: https://app.acuityscheduling.com/schedule.php?owner=12345678
# The number after "owner=" is your Owner ID.
ACUITY_OWNER_ID  = "YOUR_ACUITY_OWNER_ID"

# Optional custom subdomain (set to "" if you don't have one)
# e.g. "cprcertificationlabs" → https://cprcertificationlabs.acuityscheduling.com
ACUITY_SUBDOMAIN = ""  # e.g. "cprcertificationlabs"

def acuity_url(appointment_type_id):
    """Build an Acuity direct booking URL for a given appointment type."""
    if ACUITY_SUBDOMAIN:
        base = f"https://{ACUITY_SUBDOMAIN}.acuityscheduling.com/schedule.php"
        return f"{base}?appointmentTypeID={appointment_type_id}"
    else:
        base = "https://app.acuityscheduling.com/schedule.php"
        return f"{base}?owner={ACUITY_OWNER_ID}&appointmentTypeID={appointment_type_id}"

# --- Business Details ---
BUSINESS = {
    "name":        "CPR Certification Labs",
    "phone":       "+1-YOUR-PHONE-NUMBER",   # e.g. +12125551234
    "website":     "https://www.cprcertificationlabs.com",
    "email":       "info@cprcertificationlabs.com",
    "address": {
        "street":   "YOUR STREET ADDRESS",
        "city":     "YOUR CITY",
        "state":    "NY",                    # 2-letter state code
        "zip":      "YOUR ZIP",
        "country":  "US",
    },
    "timezone":    "America/New_York",       # IANA timezone (e.g. America/Chicago)
}

# --- Services You Offer ---
# For each service:
#   service_id:          Unique URL-safe ID (lowercase, hyphens). Must match your Webflow JS map.
#   name:                Display name shown on Google
#   description:         Short description shown to users
#   duration_minutes:    Length of class in minutes
#   price_usd:           Price in USD
#   capacity:            Max students per class
#   acuity_type_id:      Acuity Appointment Type ID
#                        → Acuity → Appointment Types → Edit → ID is in the browser URL bar
#                          e.g. https://secure.acuityscheduling.com/appt-type.php?action=edit&id=XXXXXXXX

SERVICES = [
    {
        "service_id":        "cpr-bls-adult",
        "name":              "BLS/CPR for Adults",
        "description":       "AHA-aligned Basic Life Support CPR class for adults. Earn your CPR certification card same day.",
        "duration_minutes":  120,
        "price_usd":         65.00,
        "capacity":          10,
        "acuity_type_id":    "ACUITY_TYPE_ID_1",   # ← Replace with your real Acuity Appointment Type ID
        # URL auto-built by acuity_url() below — no need to edit
    },
    {
        "service_id":        "cpr-bls-healthcare",
        "name":              "BLS for Healthcare Providers",
        "description":       "Basic Life Support certification for healthcare professionals. Includes adult, child, and infant CPR.",
        "duration_minutes":  150,
        "price_usd":         80.00,
        "capacity":          8,
        "acuity_type_id":    "ACUITY_TYPE_ID_2",   # ← Replace
    },
    {
        "service_id":        "cpr-aed-combo",
        "name":              "CPR + AED Combo",
        "description":       "Combined CPR and AED training course. Learn to use an Automated External Defibrillator.",
        "duration_minutes":  120,
        "price_usd":         70.00,
        "capacity":          10,
        "acuity_type_id":    "ACUITY_TYPE_ID_3",   # ← Replace
    },
    {
        "service_id":        "first-aid-cpr-aed",
        "name":              "First Aid + CPR + AED",
        "description":       "Comprehensive emergency response training: First Aid, CPR, and AED all in one course.",
        "duration_minutes":  240,
        "price_usd":         95.00,
        "capacity":          8,
        "acuity_type_id":    "ACUITY_TYPE_ID_4",   # ← Replace
    },
    {
        "service_id":        "heartsaver-firstaid",
        "name":              "Heartsaver First Aid CPR AED",
        "description":       "AHA Heartsaver certification course. Ideal for workplace compliance and childcare workers.",
        "duration_minutes":  240,
        "price_usd":         100.00,
        "capacity":          8,
        "acuity_type_id":    "ACUITY_TYPE_ID_5",   # ← Replace
    },
]

# --- Class Schedule ---
# Define which services run on which days/times.
# This generates slots for the next NUM_WEEKS_AHEAD weeks.
#
# Each entry:
#   service_id: must match one of the service_ids above
#   weekday:    0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
#   hour:       start hour in 24h format (local time per BUSINESS["timezone"])
#   minute:     start minute

NUM_WEEKS_AHEAD = 8  # How many weeks of availability to generate

SCHEDULE = [
    # BLS/CPR for Adults — runs Tue/Thu mornings and Saturday afternoons
    {"service_id": "cpr-bls-adult",       "weekday": 1, "hour": 9,  "minute": 0},
    {"service_id": "cpr-bls-adult",       "weekday": 3, "hour": 9,  "minute": 0},
    {"service_id": "cpr-bls-adult",       "weekday": 5, "hour": 13, "minute": 0},

    # BLS Healthcare — runs Wed/Fri mornings
    {"service_id": "cpr-bls-healthcare",  "weekday": 2, "hour": 10, "minute": 0},
    {"service_id": "cpr-bls-healthcare",  "weekday": 4, "hour": 10, "minute": 0},

    # CPR + AED Combo — runs Mon/Wed evenings
    {"service_id": "cpr-aed-combo",       "weekday": 0, "hour": 18, "minute": 0},
    {"service_id": "cpr-aed-combo",       "weekday": 2, "hour": 18, "minute": 0},

    # First Aid + CPR + AED — runs Saturdays mornings
    {"service_id": "first-aid-cpr-aed",   "weekday": 5, "hour": 9,  "minute": 0},

    # Heartsaver — runs Sundays
    {"service_id": "heartsaver-firstaid", "weekday": 6, "hour": 10, "minute": 0},
]

# --- Specific dates to BLOCK (cancelled classes) ---
# Add dates in YYYY-MM-DD format that should have no classes
BLOCKED_DATES = [
    # "2026-07-04",  # July 4th holiday example
]

# =============================================================================
# ========================== FEED GENERATION ==================================
# Do not edit below this line unless you know what you are doing.
# =============================================================================

def format_duration(minutes):
    """Convert minutes to ISO 8601 duration (e.g. PT2H30M)."""
    hours = minutes // 60
    mins  = minutes % 60
    if hours and mins:
        return f"PT{hours}H{mins}M"
    elif hours:
        return f"PT{hours}H"
    else:
        return f"PT{mins}M"

def format_datetime(dt):
    """Format a datetime to RFC3339 with offset."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S%z")

def generate_slots(schedule_entry, service_map, num_weeks=NUM_WEEKS_AHEAD, blocked=None):
    """Generate all time slots for a schedule entry over num_weeks."""
    blocked = blocked or []
    service = service_map[schedule_entry["service_id"]]
    duration = timedelta(minutes=service["duration_minutes"])
    slots = []

    today = datetime.now().date()
    for week in range(num_weeks):
        for day_offset in range(7):
            candidate = today + timedelta(weeks=week, days=day_offset)
            if candidate.weekday() != schedule_entry["weekday"]:
                continue
            if candidate.strftime("%Y-%m-%d") in blocked:
                continue

            # Build naive datetime in local time, then attach UTC offset
            start_naive = datetime(
                candidate.year, candidate.month, candidate.day,
                schedule_entry["hour"], schedule_entry["minute"], 0
            )
            # For simplicity we use UTC-5 (Eastern Standard).
            # For production, use pytz or zoneinfo for proper DST handling.
            utc_offset = timezone(timedelta(hours=-5))
            start_dt = start_naive.replace(tzinfo=utc_offset)
            end_dt   = start_dt + duration

            slots.append({
                "service_id": schedule_entry["service_id"],
                "start":      format_datetime(start_dt),
                "end":        format_datetime(end_dt),
                "spots_open": service["capacity"],
                "spots_total": service["capacity"],
            })

    return slots

def build_feed():
    """Build the complete inventory feed XML."""
    # Register namespaces
    namespace = "http://schema.googleapis.com/application/commerce/action/appointment"
    ET.register_namespace("", namespace)

    root = ET.Element("FeedMapping", attrib={
        "xmlns": namespace,
        "version": "1"
    })

    # ---- Merchant ----
    merchant = ET.SubElement(root, "Merchant")
    ET.SubElement(merchant, "merchant_id").text = MERCHANT_ID
    ET.SubElement(merchant, "name").text = BUSINESS["name"]

    merchant_tel = ET.SubElement(merchant, "telephone")
    ET.SubElement(merchant_tel, "number").text = BUSINESS["phone"]

    merchant_url = ET.SubElement(merchant, "url")
    ET.SubElement(merchant_url, "url_value").text = BUSINESS["website"]

    loc = ET.SubElement(merchant, "location")
    addr = ET.SubElement(loc, "address")
    ET.SubElement(addr, "address_component", attrib={"type": "STREET_ADDRESS"}).text = BUSINESS["address"]["street"]
    ET.SubElement(addr, "address_component", attrib={"type": "LOCALITY"}).text       = BUSINESS["address"]["city"]
    ET.SubElement(addr, "address_component", attrib={"type": "ADMINISTRATIVE_AREA_LEVEL_1"}).text = BUSINESS["address"]["state"]
    ET.SubElement(addr, "address_component", attrib={"type": "POSTAL_CODE"}).text    = BUSINESS["address"]["zip"]
    ET.SubElement(addr, "address_component", attrib={"type": "COUNTRY"}).text        = BUSINESS["address"]["country"]

    ET.SubElement(merchant, "timezone").text = BUSINESS["timezone"]

    # ---- Services ----
    service_map = {s["service_id"]: s for s in SERVICES}

    for svc in SERVICES:
        service_el = ET.SubElement(root, "Service")
        ET.SubElement(service_el, "merchant_id").text = MERCHANT_ID
        ET.SubElement(service_el, "service_id").text  = svc["service_id"]
        ET.SubElement(service_el, "name").text         = svc["name"]
        ET.SubElement(service_el, "description").text  = svc["description"]

        price_el = ET.SubElement(service_el, "price")
        ET.SubElement(price_el, "currency_code").text   = "USD"
        ET.SubElement(price_el, "units").text            = str(int(svc["price_usd"]))
        ET.SubElement(price_el, "nanos").text            = str(int((svc["price_usd"] % 1) * 1e9))

        ET.SubElement(service_el, "duration").text = format_duration(svc["duration_minutes"])

        # Redirect URL — goes to Acuity with the correct appointment type pre-selected
        action_link = ET.SubElement(service_el, "action_link")
        ET.SubElement(action_link, "url").text = acuity_url(svc["acuity_type_id"])

    # ---- Availability Slots ----
    for entry in SCHEDULE:
        slots = generate_slots(entry, service_map, blocked=BLOCKED_DATES)
        if not slots:
            continue

        avail_el = ET.SubElement(root, "ServiceAvailability")
        ET.SubElement(avail_el, "merchant_id").text = MERCHANT_ID
        ET.SubElement(avail_el, "service_id").text  = entry["service_id"]

        for slot in slots:
            slot_el = ET.SubElement(avail_el, "availability")
            ET.SubElement(slot_el, "start_time").text  = slot["start"]
            ET.SubElement(slot_el, "end_time").text    = slot["end"]
            ET.SubElement(slot_el, "spots_open").text  = str(slot["spots_open"])
            ET.SubElement(slot_el, "spots_total").text = str(slot["spots_total"])

    return root

def indent_xml(elem, level=0):
    """Pretty-print XML with indentation."""
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

if __name__ == "__main__":
    print("Generating Book with Google inventory feed...")

    root = build_feed()
    indent_xml(root)

    tree = ET.ElementTree(root)
    output_file = "feed.xml"
    tree.write(output_file, xml_declaration=True, encoding="UTF-8")

    # Count generated slots
    slots = root.findall(".//availability")
    services = root.findall("Service")
    print(f"  - Business:    {BUSINESS['name']}")
    print(f"  - Acuity ID:   {ACUITY_OWNER_ID}")
    print(f"  - Services:    {len(services)}")
    print(f"  - Avail slots: {len(slots)}")
    print(f"  - Weeks ahead: {NUM_WEEKS_AHEAD}")
    print(f"\nFeed written to: {output_file}")
    print("\nSample Acuity URLs in feed:")
    for svc in SERVICES[:2]:
        print(f"  {svc['service_id']:25s} → {acuity_url(svc['acuity_type_id'])}")
    print("\nNext steps:")
    print("  1. Fill in ACUITY_OWNER_ID and all acuity_type_id values above")
    print("  2. Run this script again to regenerate feed.xml")
    print("  3. Upload feed.xml to the Reserve with Google Partner Portal")
    print("  4. Fix any validation errors shown in the portal")
    print("  5. Re-run this script whenever your schedule or services change")
