#!/usr/bin/env python3
"""
Naturals Salon & Spa — Static Site Builder
Fetches data from Google Sheets and generates static HTML.
Run: python build/build.py
"""

import json, os, sys, requests
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# ── Config ────────────────────────────────────────────────────────────────────

SHEET_ID   = "1wy0_josh4L-C0GXWNnRG8QEO9F8km5SMrDefemChFUo"
BUILD_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(BUILD_DIR)
TMPL_DIR   = os.path.join(BUILD_DIR, "templates")
STORES_DIR = os.path.join(ROOT_DIR, "stores")

STORE_ORDER = ["Store_N78", "Store_N77", "Store_N36", "Store_N05", "Store_N43"]

# ── Tracking IDs — set here, used as Jinja2 globals ──
# Leave empty strings until real IDs are obtained
GTM_ID    = ""   # e.g. "GTM-XXXXXXX"
PIXEL_ID  = ""   # e.g. "1234567890123"

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
    if g in ("female", "women", "f", "w"): return "female"
    if g in ("male", "men", "m"):           return "male"
    return "unisex"


def parse_expiry(val):
    """Parse 13-Mar-2026 → datetime. Returns None if unparseable."""
    try:
        return datetime.strptime(val.strip(), "%d-%b-%Y")
    except (ValueError, AttributeError):
        return None


def is_offer_active(valid_till_str):
    if not valid_till_str or valid_till_str.strip() in ('', '-'):
        return True
    dt = parse_expiry(valid_till_str)
    return dt is None or dt.date() >= datetime.today().date()


def get_featured_offers(all_offers, active_stores, n=3):
    """
    Returns up to n active offers with nearest expiry date.
    Offers without expiry date are placed last.
    Only includes offers for active stores.
    """
    store_ids = {s["Store_ID"] for s in active_stores}
    active = [
        o for o in all_offers
        if o.get("Store_ID", "").strip() in store_ids
        and is_offer_active(o.get("Valid_till", ""))
    ]

    def sort_key(o):
        dt = parse_expiry(o.get("Valid_till", ""))
        if dt is None:
            return datetime(9999, 12, 31)
        return dt

    active.sort(key=sort_key)
    return active[:n]


def build_offers_by_store(all_offers, active_stores):
    store_ids = {s["Store_ID"] for s in active_stores}
    result = {s["Store_ID"]: [] for s in active_stores}
    for o in all_offers:
        sid = o.get("Store_ID", "").strip()
        if sid in store_ids and is_offer_active(o.get("Valid_till", "")):
            result[sid].append(o)
    return result


# ── Page writers ──────────────────────────────────────────────────────────────

def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written: {os.path.relpath(path, ROOT_DIR)}")


def build_index(stores, featured_offers, env):
    html = env.get_template("index.html.j2").render(
        stores=stores,
        featured_offers=featured_offers,
    )
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
    offers   = [o for o in all_offers if o.get("Store_ID", "").strip() == store_id and is_offer_active(o.get("Valid_till",""))]
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

    # Filter + order active stores
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

    featured_offers = get_featured_offers(offers_data, active_stores, n=3)
    offers_by_store = build_offers_by_store(offers_data, active_stores)
    active_offer_count = sum(len(v) for v in offers_by_store.values())

    print(f"  Active stores: {len(active_stores)} | "
          f"Services: {len(services_data)} | "
          f"Active offers: {active_offer_count} | "
          f"Featured: {len(featured_offers)} | "
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
    env.globals["gtm_id"]      = GTM_ID
    env.globals["pixel_id"]    = PIXEL_ID

    print("Building pages...")
    build_index(active_stores, featured_offers, env)
    build_services(services_data, active_stores, env)
    for store in active_stores:
        build_store(store, services_data, offers_data, stylists_data, active_stores, env)
    build_contact(active_stores, env)
    build_offers_page(active_stores, offers_by_store, env)
    build_cancellation_policy(active_stores, env)
    build_booking_policy(active_stores, env)

    total_pages = 2 + len(active_stores) + 4
    print(f"\n✅ Build complete — {total_pages} pages generated.")
    if not GTM_ID:
        print("  ⚠  GTM_ID is empty — tracking not active. Set GTM_ID in build.py when ready.")
    if not PIXEL_ID:
        print("  ⚠  PIXEL_ID is empty — Meta Pixel not active. Set PIXEL_ID in build.py when ready.")


if __name__ == "__main__":
    main()
