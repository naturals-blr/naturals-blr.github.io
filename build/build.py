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
from jinja2 import Environment, FileSystemLoader

# ── Config ────────────────────────────────────────────────────────────────────

SHEET_ID   = "1wy0_josh4L-C0GXWNnRG8QEO9F8km5SMrDefemChFUo"
BUILD_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(BUILD_DIR)
TMPL_DIR   = os.path.join(BUILD_DIR, "templates")
STORES_DIR = os.path.join(ROOT_DIR, "stores")

STORE_ORDER = ["Store_N78", "Store_N77", "Store_N36", "Store_N05", "Store_N43"]

# ── Fetch Google Sheet as CSV ─────────────────────────────────────────────────

def fetch_sheet(sheet_name):
    """Fetch a sheet tab as list-of-dicts (header row = keys)."""
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={requests.utils.quote(sheet_name)}"
    )
    print(f"  Fetching sheet: {sheet_name} ...")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return parse_csv(r.text)


def parse_csv(text):
    """Parse CSV text into list of dicts keyed by header row."""
    import csv, io
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {k.strip(): v.strip() for k, v in row.items() if k}
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


# ── Data helpers ──────────────────────────────────────────────────────────────

def is_yes(val):
    return str(val).strip().lower() in ("yes", "y", "true", "1")


def norm_gender(raw):
    g = str(raw).strip().lower()
    if g in ("female", "women", "f", "w"):
        return "women"
    if g in ("male", "men", "m"):
        return "men"
    return "both"


# ── Build index.html ──────────────────────────────────────────────────────────

def build_index(stores, env):
    tmpl = env.get_template("index.html.j2")
    html = tmpl.render(stores=stores)
    out  = os.path.join(ROOT_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written: index.html")


# ── Build services.html ───────────────────────────────────────────────────────

def build_services(services, stores, env):
    # Collect unique categories (in order of first appearance)
    seen_cats = []
    for svc in services:
        cat = svc.get("Category", "Other").strip()
        if cat and cat not in seen_cats:
            seen_cats.append(cat)

    # Embed services as JSON inside the page
    services_json = json.dumps(services, ensure_ascii=False)

    tmpl = env.get_template("services.html.j2")
    html = tmpl.render(
        services_json=services_json,
        categories=seen_cats,
        stores=stores,
    )
    out = os.path.join(ROOT_DIR, "services.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written: services.html")


# ── Build store pages ─────────────────────────────────────────────────────────

def build_store(store, all_services, all_offers, all_stylists, stores, env):
    store_id = store["Store_ID"]

    # Filter services available at this store
    svc_list = [
        s for s in all_services
        if is_yes(s.get(store_id, ""))
    ]

    # Filter offers and stylists for this store
    offers   = [o for o in all_offers   if o.get("Store_ID", "").strip() == store_id]
    stylists = [
        s for s in all_stylists
        if s.get("Store_ID", "").strip() == store_id
        and str(s.get("Active_Status", "yes")).strip().lower() != "no"
    ]

    # Build prev/next store links for bottom nav
    idx       = next((i for i, s in enumerate(stores) if s["Store_ID"] == store_id), 0)
    prev_store = stores[(idx - 1) % len(stores)]
    next_store = stores[(idx + 1) % len(stores)]

    # Embed services as JSON (per-store subset)
    svc_json = json.dumps(svc_list, ensure_ascii=False)

    tmpl = env.get_template("store.html.j2")
    html = tmpl.render(
        store=store,
        services_json=svc_json,
        services=svc_list,
        offers=offers,
        stylists=stylists,
        prev_store=prev_store,
        next_store=next_store,
        all_stores=stores,
    )

    slug = store.get("Store_Page_URL", "").replace("stores/", "").replace(".html", "")
    if not slug:
        slug = store_id.lower().replace("_", "-")

    os.makedirs(STORES_DIR, exist_ok=True)
    out = os.path.join(STORES_DIR, f"{slug}.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written: stores/{slug}.html")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Naturals Build — fetching Google Sheets data...")

    # Fetch all sheets
    try:
        store_details = fetch_sheet("store_details")
        services_data = fetch_sheet("services")
        offers_data   = fetch_sheet("offers")
        stylists_data = fetch_sheet("stylists")
    except Exception as e:
        print(f"ERROR fetching sheets: {e}")
        sys.exit(1)

    # Sort stores in defined order
    store_map = {s["Store_ID"]: s for s in store_details if s.get("Store_ID")}
    stores    = [store_map[sid] for sid in STORE_ORDER if sid in store_map]

    if not stores:
        print("ERROR: No stores found in store_details sheet.")
        sys.exit(1)

    print(f"  Loaded {len(stores)} stores, {len(services_data)} services, "
          f"{len(offers_data)} offers, {len(stylists_data)} stylists")

    # Set up Jinja2
    env = Environment(
        loader=FileSystemLoader(TMPL_DIR),
        autoescape=False,          # HTML templates — we control escaping manually
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Register helpers as template globals
    env.globals["is_yes"]      = is_yes
    env.globals["norm_gender"] = norm_gender

    print("Building pages...")
    build_index(stores, env)
    build_services(services_data, stores, env)
    for store in stores:
        build_store(store, services_data, offers_data, stylists_data, stores, env)

    print("Build complete.")


if __name__ == "__main__":
    main()
