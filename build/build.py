#!/usr/bin/env python3
"""
Naturals Salon & Spa — Static Site Builder
Fetches data from Google Sheets and bakes it into HTML files.
Run: python build/build.py
"""

import json
import os
import sys
import requests
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# ── Config ────────────────────────────────────────────────────────────────────

SHEET_ID   = "1wy0_josh4L-C0GXWNnRG8QEO9F8km5SMrDefemChFUo"
BUILD_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(BUILD_DIR)
TMPL_DIR   = os.path.join(BUILD_DIR, "templates")
STORES_DIR = os.path.join(ROOT_DIR, "stores")

STORE_ORDER = ["Store_N78", "Store_N77", "Store_N36", "Store_N05", "Store_N43"]

# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_sheet(sheet_name):
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={requests.utils.quote(sheet_name)}"
    )
    print(f"  Fetching: {sheet_name} ...")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return parse_csv(r.text)


def parse_csv(text):
    import csv, io
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {k.strip(): v.strip() for k, v in row.items() if k}
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_yes(val):
    return str(val).strip().lower() in ("yes", "y", "true", "1")


def norm_gender(raw):
    g = str(raw).strip().lower()
    if g in ("female", "women", "f", "w"):   return "female"
    if g in ("male",   "men",   "m"):         return "male"
    return "unisex"


def is_offer_active(valid_till_str):
    """
    Returns True if the offer has not yet expired.
    Handles format: 13-Mar-2026
    """
    if not valid_till_str or valid_till_str.strip() == '-':
        return True  # no date = always show
    try:
        expiry = datetime.strptime(valid_till_str.strip(), "%d-%b-%Y")
        return expiry.date() >= datetime.today().date()
    except ValueError:
        return True  # unparseable = show anyway


def build_offers_by_store(all_offers, active_stores):
    """
    Returns dict: { Store_ID: [active_offer, ...] }
    Only includes active (non-expired) offers for active stores.
    """
    store_ids = {s["Store_ID"] for s in active_stores}
    result = {s["Store_ID"]: [] for s in active_stores}
    for o in all_offers:
        sid = o.get("Store_ID", "").strip()
        if sid in store_ids and is_offer_active(o.get("Valid_till", "")):
            result[sid].append(o)
    return result


# ── Page builders ──────────────────────────────────────────────────────────────

def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written: {os.path.relpath(path, ROOT_DIR)}")


def build_index(stores, env):
    html = env.get_template("index.html.j2").render(stores=stores)
    write(os.path.join(ROOT_DIR, "index.html"), html)


def build_services(services, stores, env):
    seen_cats = []
    for svc in services:
        cat = svc.get("Category", "Other").strip()
        if cat and cat not in seen_cats:
            seen_cats.append(cat)
    services_json = json.dumps(services, ensure_ascii=False)
    html = env.get_template("services.html.j2").render(
        services_json=services_json,
        categories=seen_cats,
        stores=stores,
    )
    write(os.path.join(ROOT_DIR, "services.html"), html)


def build_store(store, all_services, all_offers, all_stylists, active_stores, env):
    store_id = store["Store_ID"]
    svc_list = [s for s in all_services if is_yes(s.get(store_id, ""))]
    offers   = [o for o in all_offers if o.get("Store_ID", "").strip() == store_id]
    stylists = [
        s for s in all_stylists
        if s.get("Store_ID", "").strip() == store_id
        and str(s.get("Active_Status", "yes")).strip().lower() != "no"
    ]
    idx        = next((i for i, s in enumerate(active_stores) if s["Store_ID"] == store_id), 0)
    prev_store = active_stores[(idx - 1) % len(active_stores)]
    next_store = active_stores[(idx + 1) % len(active_stores)]
    svc_json   = json.dumps(svc_list, ensure_ascii=False)

    html = env.get_template("store.html.j2").render(
        store=store,
        services_json=svc_json,
        services=svc_list,
        offers=offers,
        stylists=stylists,
        prev_store=prev_store,
        next_store=next_store,
        all_stores=active_stores,
    )
    slug = store.get("Store_Page_URL", "").replace("stores/", "").replace(".html", "")
    if not slug:
        slug = store_id.lower().replace("_", "-")
    write(os.path.join(STORES_DIR, f"{slug}.html"), html)


def build_contact(stores, env):
    html = env.get_template("contact.html.j2").render(stores=stores)
    write(os.path.join(ROOT_DIR, "contact.html"), html)


def build_offers_page(stores, offers_by_store, env):
    # Flatten all active offers for count display
    total = sum(len(v) for v in offers_by_store.values())
    html = env.get_template("offers.html.j2").render(
        stores=stores,
        offers_by_store=offers_by_store,
        total_offers=total,
    )
    write(os.path.join(ROOT_DIR, "offers.html"), html)


def build_cancellation_policy(stores, env):
    html = env.get_template("cancellation-policy.html.j2").render(stores=stores)
    write(os.path.join(ROOT_DIR, "cancellation-policy.html"), html)


def build_booking_policy(stores, env):
    html = env.get_template("booking-policy.html.j2").render(stores=stores)
    write(os.path.join(ROOT_DIR, "booking-policy.html"), html)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Naturals Build — fetching Google Sheets data...")

    try:
        store_details = fetch_sheet("store_details")
        services_data = fetch_sheet("services")
        offers_data   = fetch_sheet("offers")
        stylists_data = fetch_sheet("stylists")
    except Exception as e:
        print(f"ERROR fetching sheets: {e}")
        sys.exit(1)

    # Sort + filter to active stores only
    store_map     = {s["Store_ID"]: s for s in store_details if s.get("Store_ID")}
    all_stores    = [store_map[sid] for sid in STORE_ORDER if sid in store_map]
    active_stores = [s for s in all_stores if is_yes(s.get("Active_Status", "yes"))]

    if not active_stores:
        print("ERROR: No active stores found.")
        sys.exit(1)

    inactive = [s.get("Store_Name", s["Store_ID"]) for s in all_stores
                if not is_yes(s.get("Active_Status", "yes"))]
    if inactive:
        print(f"  Skipping inactive stores: {', '.join(inactive)}")

    # Build offers dict — expired offers filtered out
    offers_by_store = build_offers_by_store(offers_data, active_stores)
    active_offer_count = sum(len(v) for v in offers_by_store.values())

    print(f"  Active stores: {len(active_stores)} | "
          f"Services: {len(services_data)} | "
          f"Active offers: {active_offer_count} | "
          f"Stylists: {len(stylists_data)}")

    # Jinja2 env
    env = Environment(
        loader=FileSystemLoader(TMPL_DIR),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["is_yes"]      = is_yes
    env.globals["norm_gender"] = norm_gender

    print("Building pages...")
    build_index(active_stores, env)
    build_services(services_data, active_stores, env)
    for store in active_stores:
        build_store(store, services_data, offers_data, stylists_data, active_stores, env)
    build_contact(active_stores, env)
    build_offers_page(active_stores, offers_by_store, env)
    build_cancellation_policy(active_stores, env)
    build_booking_policy(active_stores, env)

    print(f"\nBuild complete — {4 + len(active_stores) + 2} pages generated.")


if __name__ == "__main__":
    main()
