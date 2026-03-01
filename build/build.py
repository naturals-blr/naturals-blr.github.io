#!/usr/bin/env python3
"""
Naturals Salon & Spa — Static Site Builder
Run: python build/build.py
"""

import json, os, re, sys, requests
from datetime import datetime
from jinja2 import Environment, FileSystemLoader

# ── Config ────────────────────────────────────────────────────────────────────

SHEET_ID   = "1wy0_josh4L-C0GXWNnRG8QEO9F8km5SMrDefemChFUo"
BUILD_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(BUILD_DIR)
TMPL_DIR   = os.path.join(BUILD_DIR, "templates")
STORES_DIR = os.path.join(ROOT_DIR, "stores")

STORE_ORDER = ["Store_N78", "Store_N77", "Store_N36", "Store_N05", "Store_N43"]

GTM_ID   = ""   # e.g. "GTM-XXXXXXX"
PIXEL_ID = ""   # e.g. "1234567890123"

# Homepage service categories → sheet category name fragment (lowercase, partial match)
# Order matches the 6 cards on the homepage
HOME_SERVICE_CATS = [
    ("Haircuts & Styling",       ["hair styling - female", "hair styling female"]),
    ("Hair Colour & Highlights", ["colouring", "highlights"]),
    ("Hair Spa & Treatments",    ["hair spa", "keratin", "smoothening", "treatment"]),
    ("Skin Care & Facials",      ["facial", "skin care", "de-tan", "cleanup"]),
    ("Bridal & Makeup",          ["bridal", "makeup", "mehendi"]),
    ("Men's Grooming",           ["hair styling - men", "mens", "men's"]),
]

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


# ── Phone helpers ──────────────────────────────────────────────────────────────

def normalise_phone(raw):
    """
    raw = '918792642299'  (12 digits, starts with 91)
    display  → '+91 87926 42299'
    tel      → '+918792642299'
    wa       → '918792642299'  (wa.me wants no +)
    """
    digits = re.sub(r'\D', '', str(raw))
    if not digits:
        return raw, raw, raw  # display, tel, wa
    # Strip leading 91 if 12 digits
    if len(digits) == 12 and digits.startswith('91'):
        local = digits[2:]   # 10 digits
    elif len(digits) == 10:
        local = digits
    else:
        local = digits[-10:] if len(digits) > 10 else digits
    # Format: +91 XXXXX XXXXX
    display = f"+91 {local[:5]} {local[5:]}"
    tel     = f"+91{local}"
    wa      = f"91{local}"
    return display, tel, wa


def enrich_store_phones(store):
    """Add Phone_Display, Phone_Tel, WhatsApp_Number normalised from Phone_Raw."""
    raw = store.get('Phone_Raw', store.get('Phone_Mobile', ''))
    display, tel, wa = normalise_phone(raw)
    store['Phone_Display'] = display
    store['Phone_Tel']     = tel
    store['WhatsApp_Number'] = wa
    # Also normalise Landline if present
    if store.get('Landline_Raw'):
        ld, lt, _ = normalise_phone(store['Landline_Raw'])
        store['Landline_Display'] = ld
        store['Landline_Tel']     = lt
    return store


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_yes(val):
    return str(val).strip().lower() in ("yes", "y", "true", "1")


def norm_gender(raw):
    g = str(raw).strip().lower()
    if g in ("female", "women", "f", "w"): return "female"
    if g in ("male", "men", "m"):           return "male"
    return "unisex"


def parse_expiry(val):
    """Parse 13-Mar-2026 → datetime."""
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(val.strip(), fmt)
        except (ValueError, AttributeError):
            pass
    return None


def is_offer_active(valid_till_str):
    if not valid_till_str or valid_till_str.strip() in ('', '-'):
        return True
    dt = parse_expiry(valid_till_str)
    return dt is None or dt.date() >= datetime.today().date()


def get_featured_offers(all_offers, active_stores, n=3):
    store_ids = {s["Store_ID"] for s in active_stores}
    active = [
        o for o in all_offers
        if o.get("Store_ID", "").strip() in store_ids
        and is_offer_active(o.get("Valid_till", ""))
    ]
    def sort_key(o):
        dt = parse_expiry(o.get("Valid_till", ""))
        return dt if dt else datetime(9999, 12, 31)
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


def parse_price(val):
    """Extract numeric price from strings like '₹500', '500', '500.00'."""
    if not val:
        return None
    digits = re.sub(r'[^\d.]', '', str(val))
    try:
        return float(digits)
    except ValueError:
        return None


def get_min_prices(services):
    """
    Returns dict: { display_category_name: min_price_int }
    for the 6 homepage categories.
    """
    result = {}
    for display_name, keywords in HOME_SERVICE_CATS:
        min_p = None
        for svc in services:
            cat = svc.get('Category', '').lower()
            matched = any(kw in cat for kw in keywords)
            if not matched:
                continue
            for price_field in ('Regular_Cost', 'Price', 'Cost', 'MRP'):
                p = parse_price(svc.get(price_field, ''))
                if p and p > 0:
                    if min_p is None or p < min_p:
                        min_p = p
                    break
        result[display_name] = int(min_p) if min_p else None
    return result


# ── HTML minification ─────────────────────────────────────────────────────────

def minify_html(html):
    """
    Lightweight HTML minification:
    - Collapse multiple blank lines to one
    - Strip leading whitespace from lines
    - Remove HTML comments (preserve IE conditionals <!--[if)
    """
    # Remove non-IE HTML comments
    html = re.sub(r'<!--(?!\[if).*?-->', '', html, flags=re.DOTALL)
    # Collapse runs of blank lines (3+ → 1)
    html = re.sub(r'\n{3,}', '\n\n', html)
    # Strip leading whitespace from each line (keeps indented code readable
    # but removes large indents from template rendering)
    lines = []
    for line in html.split('\n'):
        stripped = line.lstrip()
        lines.append(stripped)
    html = '\n'.join(lines)
    # Collapse multiple spaces inside tags (not inside <pre> or <script>)
    html = re.sub(r'[ \t]{2,}', ' ', html)
    return html.strip()


# ── Page writers ──────────────────────────────────────────────────────────────

def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    html = minify_html(html)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    size_kb = len(html.encode()) / 1024
    print(f"  Written: {os.path.relpath(path, ROOT_DIR)} ({size_kb:.1f} KB)")


def build_index(stores, featured_offers, min_prices, env):
    html = env.get_template("index.html.j2").render(
        stores=stores,
        featured_offers=featured_offers,
        min_prices=min_prices,
    )
    write(os.path.join(ROOT_DIR, "index.html"), html)


def build_services(services, stores, env):
    seen_cats = []
    for svc in services:
        cat = svc.get("Category", "Other").strip()
        if cat and cat not in seen_cats:
            seen_cats.append(cat)
    html = env.get_template("services.html.j2").render(
        services_json=json.dumps(services, ensure_ascii=False),
        categories=seen_cats,
        stores=stores,
    )
    write(os.path.join(ROOT_DIR, "services.html"), html)


def build_store(store, all_services, all_offers, all_stylists, active_stores, env):
    store_id = store["Store_ID"]
    svc_list = [s for s in all_services if is_yes(s.get(store_id, ""))]
    offers   = [o for o in all_offers
                if o.get("Store_ID", "").strip() == store_id
                and is_offer_active(o.get("Valid_till", ""))]
    stylists = [s for s in all_stylists
                if s.get("Store_ID", "").strip() == store_id
                and str(s.get("Active_Status", "yes")).strip().lower() != "no"]
    idx        = next((i for i, s in enumerate(active_stores) if s["Store_ID"] == store_id), 0)
    prev_store = active_stores[(idx - 1) % len(active_stores)]
    next_store = active_stores[(idx + 1) % len(active_stores)]

    html = env.get_template("store.html.j2").render(
        store=store,
        services_json=json.dumps(svc_list, ensure_ascii=False),
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
    html = env.get_template("offers.html.j2").render(
        stores=stores,
        offers_by_store=offers_by_store,
        total_offers=sum(len(v) for v in offers_by_store.values()),
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

    # Enrich phone numbers for all active stores
    active_stores = [enrich_store_phones(s) for s in active_stores]

    inactive = [s.get("Store_Name", s["Store_ID"]) for s in all_stores
                if not is_yes(s.get("Active_Status", "yes"))]
    if inactive:
        print(f"  Skipping inactive: {', '.join(inactive)}")

    featured_offers = get_featured_offers(offers_data, active_stores, n=3)
    offers_by_store = build_offers_by_store(offers_data, active_stores)
    min_prices      = get_min_prices(services_data)

    print(f"  Active stores: {len(active_stores)} | Services: {len(services_data)} | "
          f"Active offers: {sum(len(v) for v in offers_by_store.values())} | "
          f"Featured: {len(featured_offers)} | Stylists: {len(stylists_data)}")
    print(f"  Min prices: { {k: v for k, v in min_prices.items() if v} }")

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
    build_index(active_stores, featured_offers, min_prices, env)
    build_services(services_data, active_stores, env)
    for store in active_stores:
        build_store(store, services_data, offers_data, stylists_data, active_stores, env)
    build_contact(active_stores, env)
    build_offers_page(active_stores, offers_by_store, env)
    build_cancellation_policy(active_stores, env)
    build_booking_policy(active_stores, env)

    total = 2 + len(active_stores) + 4
    print(f"\n✅ Build complete — {total} pages generated.")
    if not GTM_ID:   print("  ⚠  GTM_ID empty — set in build.py when ready.")
    if not PIXEL_ID: print("  ⚠  PIXEL_ID empty — set in build.py when ready.")


if __name__ == "__main__":
    main()
