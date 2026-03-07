#!/usr/bin/env python3
"""
Book with Google — Automatic Multi-Location Feed Generator
CPR Certification Labs (cprcertificationlabs.com)

Fetches real availability from Acuity per location (calendar)
and generates a Google inventory feed (feed.xml).

Run daily via GitHub Actions to keep the feed fresh.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, date
import sys
import os

# =============================================================================
# CREDENTIALS (from GitHub Secrets / environment variables)
# =============================================================================
ACUITY_USER_ID  = os.environ.get("ACUITY_USER_ID", "")
ACUITY_API_KEY  = os.environ.get("ACUITY_API_KEY", "")

# Google Partner info (add to GitHub Secrets after Google approves you)
MERCHANT_ID_PREFIX = os.environ.get("GOOGLE_MERCHANT_ID_PREFIX", "cprlabs")

# =============================================================================
# LOCATIONS — active locations with Acuity calendar IDs
# merchant_id: unique ID per location (you'll get real ones from Google)
# calendar_id: Acuity calendar ID (from your booking URLs)
# =============================================================================
LOCATIONS = [
    {
        "merchant_id":   "cprlabs-bryan",
        "name":          "CPR Certification Labs — Bryan / College Station",
        "phone":         "+19792136953",
        "email":         "collegestation@cprcertificationlabs.com",
        "street":        "501 Graham Rd, Suite 16",
        "city":          "College Station",
        "state":         "TX",
        "zip":           "77845",
        "calendar_id":   "13529644",
    },
    {
        "merchant_id":   "cprlabs-corpus",
        "name":          "CPR Certification Labs — Corpus Christi",
        "phone":         "+13617610919",
        "email":         "corpuschristi@cprcertificationlabs.com",
        "street":        "1116 Santa Fe St, Suite 1",
        "city":          "Corpus Christi",
        "state":         "TX",
        "zip":           "78404",
        "calendar_id":   "13467715",
    },
    {
        "merchant_id":   "cprlabs-kingwood",
        "name":          "CPR Certification Labs — Kingwood",
        "phone":         "+13464778247",
        "email":         "kingwood@cprcertificationlabs.com",
        "street":        "1525 Lakeville Drive, Suite 235",
        "city":          "Kingwood",
        "state":         "TX",
        "zip":           "77339",
        "calendar_id":   "13467697",
    },
    {
        "merchant_id":   "cprlabs-conroe",
        "name":          "CPR Certification Labs — Conroe",
        "phone":         "+19362352170",
        "email":         "conroe@cprcertificationlabs.com",
        "street":        "704 North Thompson Street, Suite 157",
        "city":          "Conroe",
        "state":         "TX",
        "zip":           "77301",
        "calendar_id":   "13467701",
    },
    {
        "merchant_id":   "cprlabs-rockwall",
        "name":          "CPR Certification Labs — Rockwall / Rowlett",
        "phone":         "+14697695383",
        "email":         "rockwall@cprcertificationlabs.com",
        "street":        "1 Horizon Ct., Suite A",
        "city":          "Heath",
        "state":         "TX",
        "zip":           "75302",
        "calendar_id":   "12895394",
    },
    {
        "merchant_id":   "cprlabs-midland",
        "name":          "CPR Certification Labs — Midland / Odessa",
        "phone":         "+14323150921",
        "email":         "midland@cprcertificationlabs.com",
        "street":        "4214 Andrews Highway, Suite 202",
        "city":          "Midland",
        "state":         "TX",
        "zip":           "79703",
        "calendar_id":   "13108851",
    },
    {
        "merchant_id":   "cprlabs-houston-north",
        "name":          "CPR Certification Labs — North Houston",
        "phone":         "+13463532291",
        "email":         "houstonnorth@cprcertificationlabs.com",
        "street":        "2930 Cypress Grove Meadows Dr",
        "city":          "Houston",
        "state":         "TX",
        "zip":           "77014",
        "calendar_id":   "12180117",
    },
    {
        "merchant_id":   "cprlabs-clearlake",
        "name":          "CPR Certification Labs — Houston Clear Lake",
        "phone":         "+17139873709",
        "email":         "clearlake@cprcertificationlabs.com",
        "street":        "100 Perkins Ave, Suite E",
        "city":          "League City",
        "state":         "TX",
        "zip":           "77573",
        "calendar_id":   "12180080",
    },
    {
        "merchant_id":   "cprlabs-fortworth",
        "name":          "CPR Certification Labs — Fort Worth",
        "phone":         "+18174207629",
        "email":         "fortworth@cprcertificationlabs.com",
        "street":        "6940 River Park Circle",
        "city":          "Fort Worth",
        "state":         "TX",
        "zip":           "76116",
        "calendar_id":   "12180071",
    },
    {
        "merchant_id":   "cprlabs-benbrook",
        "name":          "CPR Certification Labs — Fort Worth Benbrook",
        "phone":         "+16823421525",
        "email":         "benbrook@cprcertificationlabs.com",
        "street":        "6100 Southwest Blvd, Suite 200",
        "city":          "Benbrook",
        "state":         "TX",
        "zip":           "76109",
        "calendar_id":   "12179392",
    },
    {
        "merchant_id":   "cprlabs-dallas",
        "name":          "CPR Certification Labs — Dallas Oak Cliff",
        "phone":         "+19723625542",
        "email":         "dallas@cprcertificationlabs.com",
        "street":        "5787 S Hampton Rd, Suite 430",
        "city":          "Dallas",
        "state":         "TX",
        "zip":           "75232",
        "calendar_id":   "12655373",
    },
    {
        "merchant_id":   "cprlabs-carrollton",
        "name":          "CPR Certification Labs — Dallas Carrollton",
        "phone":         "+19724400527",
        "email":         "carrollton@cprcertificationlabs.com",
        "street":        "1406 Halsey Way, Suite 110",
        "city":          "Carrollton",
        "state":         "TX",
        "zip":           "75007",
        "calendar_id":   "12149404",
    },
]

# =============================================================================
# SERVICES — maps Acuity appointment type names → Google service IDs + type IDs
#
# COMPLIANCE NOTES (Google Appointments Redirect Policy):
# - "display_name": shown to users on Google — clear, properly capitalized, no ALL CAPS
# - "description":  must be descriptive and accurate; no URLs, emails, phone numbers,
#                   promotional language, or payment method info
# - "display_name" and "description" override whatever is in Acuity
# Type IDs extracted from your Acuity booking URLs (the number after /appointment/)
# =============================================================================
SERVICES = [
    {
        "service_id":      "bls-heartcode-complete",
        "acuity_name":     "BLS HeartCode Complete",
        "acuity_type_id":  "78548657",
        "display_name":    "BLS HeartCode Complete",
        "description":     "Basic Life Support certification course covering adult, child, and infant CPR, AED use, and relief of choking. Designed for healthcare professionals and students. Certification card issued upon successful completion.",
    },
    {
        "service_id":      "acls-heartcode-complete",
        "acuity_name":     "ACLS HeartCode Complete",
        "acuity_type_id":  "78755223",
        "display_name":    "ACLS HeartCode Complete",
        "description":     "Advanced Cardiovascular Life Support certification course for healthcare providers. Covers recognition and management of cardiac arrest, acute arrhythmias, stroke, and other cardiovascular emergencies.",
    },
    {
        "service_id":      "pals-heartcode-complete",
        "acuity_name":     "PALS HeartCode Complete",
        "acuity_type_id":  "78547910",
        "display_name":    "PALS HeartCode Complete",
        "description":     "Pediatric Advanced Life Support certification course for healthcare providers who respond to emergencies in infants and children. Covers systematic approach to pediatric assessment and resuscitation.",
    },
    {
        "service_id":      "acls-bls-complete-combo",
        "acuity_name":     "ACLS & BLS HeartCode Complete Combo",
        "acuity_type_id":  "78757249",
        "display_name":    "ACLS and BLS HeartCode Complete Combo",
        "description":     "Combined certification course covering both Basic Life Support and Advanced Cardiovascular Life Support. Ideal for healthcare providers who need both certifications.",
    },
    {
        "service_id":      "bls-pals-complete-combo",
        "acuity_name":     "BLS & PALS HeartCode Complete Combo",
        "acuity_type_id":  "78757690",
        "display_name":    "BLS and PALS HeartCode Complete Combo",
        "description":     "Combined certification course covering Basic Life Support and Pediatric Advanced Life Support. Designed for healthcare providers who work with both adult and pediatric patients.",
    },
    {
        "service_id":      "acls-pals-complete-combo",
        "acuity_name":     "ACLS & PALS HeartCode Complete Combo",
        "acuity_type_id":  "78757576",
        "display_name":    "ACLS and PALS HeartCode Complete Combo",
        "description":     "Combined certification course covering Advanced Cardiovascular Life Support and Pediatric Advanced Life Support for healthcare providers managing both adult and pediatric emergencies.",
    },
    {
        "service_id":      "bls-pals-acls-complete-bundle",
        "acuity_name":     "BLS, PALS, & ACLS HeartCode Complete Bundle",
        "acuity_type_id":  "78757818",
        "display_name":    "BLS, PALS, and ACLS HeartCode Complete Bundle",
        "description":     "Comprehensive certification bundle covering Basic Life Support, Pediatric Advanced Life Support, and Advanced Cardiovascular Life Support. Complete all three certifications in one enrollment.",
    },
]

# How many weeks ahead to fetch availability
WEEKS_AHEAD = 8

# Output file
OUTPUT_FILE = "feed.xml"

# Acuity account hash (from your booking URLs: cprcertificationlabs.as.me/schedule/HASH/...)
ACUITY_ACCOUNT_HASH = "9f579705"

# =============================================================================
# ACUITY API
# =============================================================================
ACUITY_BASE = "https://acuityscheduling.com/api/v1"

def acuity_get(endpoint, params=None):
    url = f"{ACUITY_BASE}/{endpoint}"
    try:
        resp = requests.get(
            url, params=params,
            auth=(ACUITY_USER_ID, ACUITY_API_KEY),
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        print(f"    ✗ API error {endpoint}: {e.response.status_code}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"    ✗ Network error: {e}")
        return None

def months_in_range(num_weeks):
    today = date.today()
    end   = today + timedelta(weeks=num_weeks)
    months, cur = set(), today.replace(day=1)
    while cur <= end:
        months.add(cur.strftime("%Y-%m"))
        cur = cur.replace(month=cur.month % 12 + 1,
                          year=cur.year + (1 if cur.month == 12 else 0))
    return sorted(months)

def fetch_slots_for_location(type_id, calendar_id):
    """
    Fetch available dates, then for each date fetch ONLY the first time slot.
    This shows Google a real available time (not synthetic), while keeping
    API calls to a minimum: ~2 date calls + 1 times call per available date.
    Users see the correct first slot time on Google; all slots visible in Acuity.
    """
    slots = []
    today_str = date.today().isoformat()
    for month_str in months_in_range(WEEKS_AHEAD):
        dates = acuity_get("availability/dates", params={
            "appointmentTypeID": type_id,
            "calendarID":        calendar_id,
            "month":             month_str,
        }) or []
        for d in dates:
            if d["date"] < today_str:
                continue
            # Fetch times but take ONLY the first slot — reduces API calls ~10x
            times = acuity_get("availability/times", params={
                "appointmentTypeID": type_id,
                "calendarID":        calendar_id,
                "date":              d["date"],
            }) or []
            if times:
                slots.append(times[0])   # first available slot of the day
    return slots

def acuity_booking_url(type_id, calendar_id):
    return (f"https://cprcertificationlabs.as.me/schedule/{ACUITY_ACCOUNT_HASH}"
            f"/appointment/{type_id}/calendar/{calendar_id}")

# =============================================================================
# FEED BUILDER
# =============================================================================
def format_dt(raw_time, duration_min=0, end=False):
    """Parse Acuity time string and return RFC3339."""
    try:
        # Acuity: "2026-03-15T10:00:00-0500" (no colon in offset)
        if len(raw_time) >= 24 and raw_time[-5] in ("+", "-"):
            iso = raw_time[:-2] + ":" + raw_time[-2:]
        else:
            iso = raw_time
        dt = datetime.fromisoformat(iso)
        if end:
            dt = dt + timedelta(minutes=duration_min)
        s = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
        return s[:-2] + ":" + s[-2:]
    except Exception:
        return raw_time

def build_feed(all_data):
    """
    all_data: list of {location, service, slots, apt_type_info}
    """
    ns = "http://schema.googleapis.com/application/commerce/action/appointment"
    ET.register_namespace("", ns)
    root = ET.Element("FeedMapping", attrib={"xmlns": ns, "version": "1"})

    # One Merchant per location
    for loc in LOCATIONS:
        m = ET.SubElement(root, "Merchant")
        ET.SubElement(m, "merchant_id").text = loc["merchant_id"]
        ET.SubElement(m, "name").text        = loc["name"]
        tel = ET.SubElement(m, "telephone")
        ET.SubElement(tel, "number").text    = loc["phone"]
        url_el = ET.SubElement(m, "url")
        ET.SubElement(url_el, "url_value").text = "https://www.cprcertificationlabs.com"
        addr_el = ET.SubElement(ET.SubElement(m, "location"), "address")
        ET.SubElement(addr_el, "address_component", attrib={"type": "STREET_ADDRESS"}).text             = loc["street"]
        ET.SubElement(addr_el, "address_component", attrib={"type": "LOCALITY"}).text                   = loc["city"]
        ET.SubElement(addr_el, "address_component", attrib={"type": "ADMINISTRATIVE_AREA_LEVEL_1"}).text = loc["state"]
        ET.SubElement(addr_el, "address_component", attrib={"type": "POSTAL_CODE"}).text                = loc["zip"]
        ET.SubElement(addr_el, "address_component", attrib={"type": "COUNTRY"}).text                    = "US"
        ET.SubElement(m, "timezone").text = "America/Chicago"

    # Services and availability per location
    for entry in all_data:
        loc     = entry["location"]
        svc     = entry["service"]
        slots   = entry["slots"]
        apt     = entry["apt_info"]   # from Acuity: name, duration, price

        # Service element
        svc_el = ET.SubElement(root, "Service")
        ET.SubElement(svc_el, "merchant_id").text = loc["merchant_id"]
        ET.SubElement(svc_el, "service_id").text  = svc["service_id"]
        # Use our own display_name and description (not Acuity's) for policy compliance.
        # Google policy: no URLs, emails, phones, promo content, or payment info in these fields.
        ET.SubElement(svc_el, "name").text        = svc.get("display_name", svc["acuity_name"])
        ET.SubElement(svc_el, "description").text = svc.get("description", svc["acuity_name"])

        price = float(apt.get("price", "0") or 0)
        p = ET.SubElement(svc_el, "price")
        ET.SubElement(p, "currency_code").text = "USD"
        ET.SubElement(p, "units").text         = str(int(price))
        ET.SubElement(p, "nanos").text         = str(int((price % 1) * 1_000_000_000))

        duration = apt.get("duration", 60)
        h, m_ = divmod(duration, 60)
        ET.SubElement(svc_el, "duration").text = f"PT{h}H{m_}M" if m_ else f"PT{h}H"

        # action_link points to Webflow /book page — NOT directly to Acuity.
        # Google appends ?merchant_id=X&service_id=Y&start_time=Z to this URL.
        # The Webflow /book page JavaScript reads those params and redirects to Acuity.
        action = ET.SubElement(svc_el, "action_link")
        ET.SubElement(action, "url").text = "https://www.cprcertificationlabs.com/book"

        # Availability
        if not slots:
            continue
        avail_el = ET.SubElement(root, "ServiceAvailability")
        ET.SubElement(avail_el, "merchant_id").text = loc["merchant_id"]
        ET.SubElement(avail_el, "service_id").text  = svc["service_id"]

        for slot in slots:
            sl = ET.SubElement(avail_el, "availability")
            ET.SubElement(sl, "start_time").text  = format_dt(slot["time"])
            ET.SubElement(sl, "end_time").text    = format_dt(slot["time"], duration, end=True)
            ET.SubElement(sl, "spots_open").text  = str(slot.get("slotsAvailable", 1))
            ET.SubElement(sl, "spots_total").text = str(slot.get("slotsAvailable", 1))

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

# =============================================================================
# MAIN
# =============================================================================
def main():
    print("=" * 60)
    print("Book with Google — Multi-Location Feed Generator")
    print(f"Locations: {len(LOCATIONS)} | Services: {len(SERVICES)}")
    print("=" * 60)

    if not ACUITY_USER_ID or not ACUITY_API_KEY:
        print("\n✗ ERROR: ACUITY_USER_ID and ACUITY_API_KEY not set.")
        sys.exit(1)

    # Fetch appointment type info once (name, price, duration)
    print("\n[1/2] Fetching appointment type info from Acuity...")
    raw_types = acuity_get("appointment-types") or []
    type_info = {str(t["id"]): t for t in raw_types}

    all_data = []
    total_slots = 0

    print("\n[2/2] Fetching availability per location × service...")
    for loc in LOCATIONS:
        print(f"\n  📍 {loc['name'].split('—')[-1].strip()}")
        for svc in SERVICES:
            apt = type_info.get(svc["acuity_type_id"], {"name": svc["acuity_name"], "duration": 60, "price": "0"})
            slots = fetch_slots_for_location(svc["acuity_type_id"], loc["calendar_id"])
            total_slots += len(slots)
            status = f"{len(slots)} slots" if slots else "no slots"
            print(f"    {svc['service_id']:35s} → {status}")
            all_data.append({
                "location": loc,
                "service":  svc,
                "slots":    slots,
                "apt_info": apt,
            })

    print(f"\nBuilding feed.xml — {total_slots} total slots across {len(LOCATIONS)} locations...")
    root = build_feed(all_data)
    indent_xml(root)
    ET.ElementTree(root).write(OUTPUT_FILE, xml_declaration=True, encoding="UTF-8")

    print(f"\n{'=' * 60}")
    print(f"  ✓  {OUTPUT_FILE} written")
    print(f"     Locations:    {len(LOCATIONS)}")
    print(f"     Services:     {len(SERVICES)}")
    print(f"     Total slots:  {total_slots}")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
