#!/usr/bin/env python3
"""
Naturals Salon & Spa — Static Site Builder
Run: python build/build.py     
"""

import sys
import os
import json
import re
import subprocess
import requests
import datetime
from datetime import datetime as dt
from pathlib import Path
from urllib.parse import quote, urlparse
from collections import defaultdict
from typing import Dict, List, Any, Optional

# Add the build directory to the path
BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BUILD_DIR)  # Go up one level to project root
sys.path.insert(0, BUILD_DIR)
sys.path.insert(0, PROJECT_ROOT)  # Add project root to Python path
sys.path.insert(0, os.path.join(BUILD_DIR, 'utils'))  # Add utils directory to Python path

import shutil
from zoneinfo import ZoneInfo
from jinja2 import Environment, FileSystemLoader, select_autoescape
from drive_offers import process_offers
from campaign_engine import process_campaigns, get_campaigns_for_store

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

# Environment Variables (for easy domain switching)
# Set WEBSITE_BASE_URL environment variable to change domain
# Local: export WEBSITE_BASE_URL=http://localhost:8000
# Production: export WEBSITE_BASE_URL=https://your-custom-domain.com
WEBSITE_BASE_URL = os.getenv('WEBSITE_BASE_URL', 'https://naturals-blr.github.io')

# Tracking IDs (set when ready)
GTM_ID = ""    # e.g. "GTM-XXXXXXX"
PIXEL_ID = ""  # e.g. "1234567890123456"

# Timezone and business hours
IST = ZoneInfo("Asia/Kolkata")
OFFER_CUTOFF_HOUR_IST = 20  # 8 PM IST

# ============================================================================
# END CONFIGURATION
# ============================================================================

# ── Config ────────────────────────────────────────────────────────────────────

SHEET_ID = "1wy0_josh4L-C0GXWNnRG8QEO9F8km5SMrDefemChFUo"
BUILD_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BUILD_DIR)
OUTPUT_DIR = os.path.join(ROOT_DIR, "out")  # Standard output folder
TMPL_DIR = os.path.join(BUILD_DIR, "templates")
STORES_DIR = os.path.join(OUTPUT_DIR, "stores")

STORE_ORDER = ["Store_N78", "Store_N77", "Store_N36", "Store_N05", "Store_N43"]
STORE_ORDER_SERVICES = ["store_n78", "store_n77", "store_n36", "store_n05", "store_n43"]

# City standardization for consistent URLs
DEFAULT_CITY_SLUG = "bangalore"
CITY_NAME_MAPPINGS = {
    "bengaluru": "bangalore",
    "bangalore": "bangalore",
    "chennai": "chennai", 
    "hyderabad": "hyderabad",
    # Add more city mappings as needed for expansion
}

GTM_ID = ""    # e.g. "GTM-XXXXXXX"
PIXEL_ID = ""  # e.g. "1234567890123"
WEBSITE_BASE_URL = os.getenv('WEBSITE_BASE_URL', 'https://naturals-blr.github.io')  # Dynamic base URL with fallback

IST = ZoneInfo("Asia/Kolkata")
OFFER_CUTOFF_HOUR_IST = 20  # 8 PM IST

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

# Reuse one HTTP session for all sheet pulls
HTTP = requests.Session()

# ── Fetch ─────────────────────────────────────────────────────────────────────

def force_refresh_from_google_sheets(filename):
    """Force refresh specific data from Google Sheets by clearing cache and re-fetching"""
    try:
        from utils.cacheManager import CacheManager
        cache_manager = CacheManager()
        cache_key = filename.replace('.json', '')
        
        # Clear cache to force refresh
        cache_manager.force_refresh(cache_key)
        
        # Also clear the local JSON file to force Google Sheets fetch
        json_path = os.path.join(BUILD_DIR, "data", filename)
        if os.path.exists(json_path):
            os.remove(json_path)
            print(f"🗑️ Removed local cache file: {filename}")
        
        print(f"🔄 Forced refresh from Google Sheets for: {filename}")
        return True
    except Exception as e:
        print(f"❌ Error forcing refresh for {filename}: {e}")
        return False


def load_json_data(filename):
    """Load JSON data with cache support"""
    # Import cache manager
    try:
        from utils.cacheManager import CacheManager
        cache_manager = CacheManager()
        cache_key = filename.replace('.json', '')
        
        # Try cache first
        if cache_manager.is_valid(cache_key):
            print(f"📋 Using cached data: {filename}")
            return cache_manager.get(cache_key)
        
        # Fallback to original file if cache is invalid
        print(f"📂 Loading from disk: {filename}")
        
        # Use the original function
        json_path = os.path.join(BUILD_DIR, "data", filename)
        
        if os.path.exists(json_path):
            print(f"  Loading from cache: {filename} ...")
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            print(f"  ⚠️  Cache not found: {filename}")
            print(f"  Run: npm run export:build-data")
            print(f"  Falling back to direct Google Sheets fetch...")
            data = fetch_sheet_fallback(filename.replace('.json', ''))
            print(f"  🔄 Fresh data fetched from Google Sheets: {len(data) if isinstance(data, list) else 1} items")
        
        # Save to cache for next time (whether from disk or Google Sheets)
        cache_manager.set(cache_key, data, ttl=30*60*1000)  # 30 minutes
        return data
        
    except ImportError as e:
        print(f"⚠️ Cache manager not available: {e}")
        print("Using direct file loading")
        
        # Fallback to original function
        json_path = os.path.join(BUILD_DIR, "data", filename)
        
        if os.path.exists(json_path):
            print(f"  Loading from cache: {filename} ...")
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"  ⚠️  Cache not found: {filename}")
            print(f"  Run: npm run export:build-data")
            print(f"  Falling back to direct Google Sheets fetch...")
            return fetch_sheet_fallback(filename.replace('.json', ''))

    # Handle both flat and nested structures
    if isinstance(data, dict):
        if "careers" in data:
            careers_list = data["careers"]
        else:
            careers_list = data
    elif isinstance(data, list):
        careers_list = data
    else:
        print(f"  ⚠️  Invalid careers data structure: {type(data)}")
        return

    return careers_list


def fetch_sheet_fallback(sheet_name: str):
    """
    Fallback: Fetch directly from Google Sheets if JSON cache doesn't exist.
    """
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/gviz/tq?tqx=out:csv&sheet={requests.utils.quote(sheet_name)}"
    )
    print(f"  Fetching from Google Sheets: {sheet_name} ...")
    r = HTTP.get(url, timeout=30)
    r.raise_for_status()
    return parse_csv(r.text)


def parse_csv(text: str):
    import csv, io
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {k.strip(): v.strip() for k, v in row.items() if k}
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


# ── Phone helpers ─────────────────────────────────────────────────────────────

def normalise_phone(raw):
    """
    raw = '918792642299'  (12 digits, starts with 91)
    display  → '+91 87926 42299'
    tel      → '+918792642299'
    wa       → '918792642299'  (wa.me wants no +)
    """
    digits = re.sub(r"\D", "", str(raw))
    if not digits:
        return raw, raw, raw  # display, tel, wa

    # Strip leading 91 if 12 digits
    if len(digits) == 12 and digits.startswith("91"):
        local = digits[2:]   # 10 digits
    elif len(digits) == 10:
        local = digits
    else:
        local = digits[-10:] if len(digits) > 10 else digits

    display = f"+91 {local[:5]} {local[5:]}"
    tel = f"+91{local}"
    wa = f"+91{local}"
    return display, tel, wa


def enrich_store_phones(store):
    """Add Phone_Display, Phone_Tel, WhatsApp_Number normalised from Phone_Raw."""
    raw = get_field(store, "Phone_Raw", get_field(store, "Phone_Mobile", ""))
    display, tel, wa = normalise_phone(raw)
    store["Phone_Display"] = display
    store["Phone_Tel"] = tel
    store["WhatsApp_Number"] = wa

    # Also normalise Landline if present
    landline_raw = get_field(store, "Landline_Raw", "")
    if landline_raw:
        ld, lt, _ = normalise_phone(landline_raw)
        store["Landline_Display"] = ld
        store["Landline_Tel"] = lt

    return store


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(text):
    """Convert text to URL-friendly slug"""
    if not text:
        return ''
    return text.lower().replace(" ", '-').replace("[^a-z0-9-]", '').replace("-+", '-').replace("^-|-$", '')

def standardize_city_slug(city_name):
    """Standardize city name to consistent slug with mapping support"""
    if not city_name:
        return DEFAULT_CITY_SLUG
    
    # First slugify the city name
    slug = slugify(city_name)
    
    # Then apply mappings (e.g., bengaluru -> bangalore)
    return CITY_NAME_MAPPINGS.get(slug, slug)

def get_job_url(job, website_base_url, city_slug, store_slug):
    """Generate clean job URL with explicit path construction"""
    job_slug = job.get('job_slug', '')
    
    # Prioritize job.store.slug over passed store_slug
    effective_store_slug = job.get('store', {}).get('slug', store_slug) if job.get('store') else store_slug
    
    if not all([website_base_url, city_slug, effective_store_slug, job_slug]):
        return "#"
    
    # Explicit path construction to avoid variable scope issues
    path_parts = [
        website_base_url.rstrip('/'),
        'careers',
        city_slug,
        effective_store_slug,
        job_slug
    ]
    return '/'.join(filter(None, path_parts)) + '/'


def get_field(obj, field, default=""):
    """
    Case-insensitive field access for dictionaries.
    Tries exact match first, then case-insensitive match.
    Returns default if field not found.
    
    Examples:
        get_field(store, "Store_ID") → works
        get_field(store, "store_id") → works
        get_field(store, "STORE_ID") → works
        get_field(service, "Store_N78") → matches "store_n78"
    """
    if not isinstance(obj, dict):
        return default
    
    # Try exact match first (fastest)
    if field in obj:
        return obj[field]
    
    # Try case-insensitive match
    field_lower = field.lower()
    for key in obj.keys():
        if key.lower() == field_lower:
            return obj[key]
    
    # Return default if not found
    return default


def is_yes(val):
    """
    Check if value represents a truthy boolean.
    Handles: yes, YES, Yes, y, Y, true, TRUE, True, t, T, 1
    Case-insensitive.
    """
    return str(val).strip().lower() in ("yes", "y", "true", "t", "1")


def is_no(val):
    """
    Check if value represents a falsy boolean.
    Handles: no, NO, No, n, N, false, FALSE, False, f, F, 0
    Case-insensitive.
    """
    return str(val).strip().lower() in ("no", "n", "false", "f", "0", "")


def norm_gender(raw):
    g = str(raw).strip().lower()
    if g in ("female", "women", "f", "w"):
        return "female"
    if g in ("male", "men", "m"):
        return "male"
    return "unisex"


def get_stylist_photo_fallback(stylist):
    """
    Determine the appropriate stylist photo fallback based on gender and photo status.
    Returns the filename to use as fallback.
    
    New field names (prioritized):
    - stylist_name, stylist_gender, has_profile_photo
    
    Legacy field names (fallback):
    - Stylist_Name, Stylist_Gender, Photo_Status
    """
    # Try new field names first, then fall back to legacy names
    gender = get_field(stylist, 'stylist_gender', get_field(stylist, 'Stylist_Gender', '')).strip()
    stylist_name = get_field(stylist, 'stylist_name', get_field(stylist, 'Stylist_Name', '')).strip()
    has_photo = get_field(stylist, 'has_profile_photo', get_field(stylist, 'Photo_Status', 'no')).strip()
    
    # Generate the primary photo filename
    stylist_slug = stylist_name.lower().replace(' ', '_').replace("'", '')
    primary_photo = f"{stylist_slug}.png"
    
    # Check if primary photo exists (in the published site)
    # For build time, we'll assume the photos are in naturals-blr.github.io
    photos_dir = os.path.join(os.path.dirname(ROOT_DIR), "naturals-blr.github.io", "images", "stylists")
    primary_path = os.path.join(photos_dir, primary_photo)
    
    if os.path.exists(primary_path):
        return primary_photo
    
    # Use gender-based fallback with specific case handling
    if gender.lower() in ("female", "f"):
        return "stylist_default_female.jpg"
    elif gender.lower() in ("male", "m"):
        return "stylist_default_male.jpg"
    else:
        # Default to female for unisex/unknown
        return "stylist_default_female.jpg"


def parse_date_any(val):
    """Parse date strings like 13-Mar-2026, 26-Feb-2026, 26/02/2026, 2026-02-26."""
    if not val:
        return None
    v = str(val).strip()
    if not v or v == "-":
        return None
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return dt.strptime(v, fmt)
        except ValueError:
            pass
    return None


def offer_expiry_dt_ist(valid_till_str):
    """
    Offer is valid until Valid_till date at 8:00 PM IST.
    Returns timezone-aware datetime in IST or None if empty/unparseable.
    """
    d = parse_date_any(valid_till_str)
    if not d:
        return None
    return dt(d.year, d.month, d.day, OFFER_CUTOFF_HOUR_IST, 0, 0, tzinfo=IST)


def offer_start_dt(valid_from_str):
    """Used for NEW badge; treat as local date start (00:00) naive."""
    return parse_date_any(valid_from_str)


def is_offer_active(o, now_ist=None):
    """
    Check if an offer should be shown on the website using campaign fields:
    1. content_type must be 'offer'
    2. approval_status must be 'Yes'
    3. is_expired must not be 'Yes'
    4. end_date must not be in the past
    """
    if now_ist is None:
        now_ist = datetime.now(IST)

    # Must be content_type = offer
    if get_field(o, "content_type", "").strip().lower() != "offer":
        return False

    # Must be approved
    if not is_yes(get_field(o, "approval_status", "no")):
        return False

    # Must not be manually marked expired
    if is_yes(get_field(o, "is_expired", "no")):
        return False

    # Must not be past end_date
    end_date = get_field(o, "end_date", "")
    if end_date:
        exp = offer_expiry_dt_ist(end_date)
        if exp and now_ist > exp:
            return False

    return True


def offer_days_left(valid_till_str, now_ist=None):
    """
    Days left until cutoff (8 PM IST). Returns int or None.
    For ribbon: show if 0..6 (less than 7 days).
    """
    if now_ist is None:
        now_ist = datetime.now(IST)
    exp = offer_expiry_dt_ist(valid_till_str)
    if not exp:
        return None
    delta = exp - now_ist
    return int(delta.total_seconds() // 86400)


def offer_sort_key(o):
    """
    Sort: soonest-expiring first, then newest created (start_date newest first).
    Missing expiry -> far future.
    Missing start_date -> oldest.
    """
    exp = offer_expiry_dt_ist(get_field(o, "end_date", "") or get_field(o, "Valid_till", ""))
    if exp is None:
        exp = datetime(9999, 12, 31, 0, 0, tzinfo=IST)
    vf = offer_start_dt(get_field(o, "start_date", "") or get_field(o, "Valid_From", "")) or datetime(1970, 1, 1)
    return (exp, -vf.timestamp())


def enrich_offer(o, now_ist=None):
    """
    Add computed fields used by templates:
      _expiry_iso, _days_left, _valid_from_iso
    """
    if now_ist is None:
        now_ist = dt.now(IST)

    o2 = dict(o)
    
    # Add computed fields for expiry
    valid_till_str = get_field(o2, "end_date", "")
    if valid_till_str:
        exp = offer_expiry_dt_ist(valid_till_str)
        if exp:
            o2["_expiry_iso"] = exp.isoformat()
            o2["_days_left"] = max(0, (exp - now_ist).days)
            o2["_valid_from_iso"] = now_ist.isoformat()
    
    # Add media fields
    media_asset_name = get_field(o2, "media_asset_name", "")
    if media_asset_name:
        o2["Image_Name"] = media_asset_name
        o2["Image_Available"] = "Yes"
        if not any(media_asset_name.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
            # Find the actual file with extension in campaigns/offer/03_published
            image_dir = "campaigns/offer/03_published"
            if os.path.exists(image_dir):
                for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
                    full_path = os.path.join(image_dir, media_asset_name + ext)
                    if os.path.exists(full_path):
                        o2["Image_Name"] = f"{media_asset_name}{ext}"
                        o2["Image_Available"] = "Yes"
                        break
                else:
                    # Default to .jpg if file not found
                    o2["Image_Name"] = f"{media_asset_name}.jpg"
                    o2["Image_Available"] = "Yes"
            else:
                # Default to .jpg if directory doesn't exist yet
                o2["Image_Name"] = f"{media_asset_name}.jpg"
                o2["Image_Available"] = "Yes"
        else:
            o2["Image_Name"] = media_asset_name
            o2["Image_Available"] = "Yes"
    else:
        o2["Image_Name"] = ""
        o2["Image_Available"] = "No"
    
    return o2


def check_individual_store_targeting(offer, store_id, store_id_short=""):
    """
    Check if an offer targets a specific store when active_stores is not provided.
    This is used by get_featured_offers to see if offer is available to ANY active store.
    """
    # Normalize store_id to get the store code (handle all formats)
    store_id_normalized = store_id.strip().upper()
    if store_id_normalized.startswith("STORE_"):
        store_code = store_id_normalized[6:]  # Remove "STORE_" prefix
    else:
        store_code = store_id_normalized
    
    # Also try store_id_short if available
    store_id_short_normalized = store_id_short.strip().upper() if store_id_short else ""
    
    # Try both full store ID and short store ID for targeting
    for code in [store_code, store_id_short_normalized]:
        if not code:
            continue
            
        # Check if offer targets this specific store
        target_field = f"target_store_{code.lower()}"
        target_val = get_field(offer, target_field, "")
        
        if is_yes(target_val):
            return True
    
    return False  # No store targeting match found


def is_offer_for_store(offer, store_id, store_id_short="", active_stores=None):
    """
    Check if an offer should be displayed for a specific store.
    Logic: Only show offer if store is active (active_status = Yes).
    """
    
    # If no active_stores provided (e.g., in get_featured_offers), assume all stores are active
    if active_stores is None:
        # Check if offer targets all stores
        target_all = get_field(offer, "target_all_stores", "")
        if is_yes(target_all):
            return True
        
        # When active_stores is None, we still need to check individual store targeting
        # because get_featured_offers wants to know if offer is available to ANY active store
        return check_individual_store_targeting(offer, store_id, store_id_short)
    
    # When active_stores are provided, check if this specific store is active and targeted
    store_map = {s.get("Store_ID", "").strip().upper(): s for s in active_stores}
    store_key = store_id.strip().upper()
    
    if store_key not in store_map:
        return False  # Store not found in active stores
    
    store = store_map[store_key]
    is_active = is_yes(get_field(store, "active_status", "yes"))
    
    if not is_active:
        return False  # Store is not active
    
    # Check if offer targets all stores
    target_all = get_field(offer, "target_all_stores", "")
    if is_yes(target_all):
        return True  # Store is active and offer targets all stores
    
    # Check individual store targeting
    store_id_short_normalized = store_id_short.strip().upper() if store_id_short else ""
    
    # Try both full store ID and short store ID
    for code in [store_key, store_id_short_normalized]:
        if not code:
            continue
            
        # Remove "STORE_" prefix if present
        if code.startswith("STORE_"):
            store_code = code[6:]
        else:
            store_code = code
        
        # Check if offer targets this specific store
        target_field = f"target_store_{store_code.lower()}"
        target_val = get_field(offer, target_field, "")
        
        if is_yes(target_val):
            return True
    
    return False  # No store targeting match found


def get_featured_offers(all_offers, active_stores, n=3):
    """
    Featured offers for homepage are:
    - Only active offers
    - Priority = 1 (high priority)
    - Available to at least one active store (Store_All = Yes OR any Store_N78 = Yes)
    - Sorted by offer_sort_key
    - Enriched with computed fields
    - Deduplicated by campaign_id or content_title
    
    For homepage, we pick the first store that has this offer for contact info.
    """
    store_map = {get_field(s, "Store_ID"): s for s in active_stores}
    store_ids = set(store_map.keys())
    now_ist = dt.now(IST)

    active = []
    seen_offers = set()  # Track unique offers
    
    for o in all_offers:
        # Check if offer has Priority = 1
        if get_field(o, "Priority", "") != "1":
            continue
        
        # Create a unique identifier for offer
        offer_id = get_field(o, "campaign_id", "") or get_field(o, "content_title", "")
        
        # Skip if we've already seen this offer
        if offer_id in seen_offers:
            continue
        
        # Check if offer is active
        if not is_offer_active(o, now_ist=now_ist):
            continue
        
        # Check if offer is available to at least one active store
        available_to_any_store = False
        first_store_id = None
        
        for store_id in store_ids:
            store = store_map[store_id]
            store_id_short = get_field(store, "store_id_short", "")
            if is_offer_for_store(o, store_id, store_id_short):  # Don't pass active_stores
                available_to_any_store = True
                if first_store_id is None:
                    first_store_id = store_id
                break
        
        if not available_to_any_store:
            continue
        
        # Mark this offer as seen
        seen_offers.add(offer_id)
        
        # Add enrichment fields directly
        o2 = dict(o)
        now_ist = dt.now(IST)
        
        # Add computed fields for expiry
        valid_till_str = get_field(o, "end_date", "")
        if valid_till_str:
            exp = offer_expiry_dt_ist(valid_till_str)
            if exp:
                o2["_expiry_iso"] = exp.isoformat()
                o2["_days_left"] = max(0, (exp - now_ist).days)
                o2["_valid_from_iso"] = now_ist.isoformat()
        
        # Media fields for template compatibility
        media_asset_name = get_field(o, "media_asset_name", "")
        if media_asset_name:
            o2["Image_Name"] = media_asset_name
            o2["Image_Available"] = "Yes"
        else:
            o2["Image_Name"] = ""
            o2["Image_Available"] = "No"
        
        # Add store contact info from the first store that has this offer
        if first_store_id:
            first_store = store_map[first_store_id]
            o2["_store_name"] = get_field(first_store, "Store_Name", "")
            o2["_store_phone"] = get_field(first_store, "Phone_Mobile", "")
            o2["_store_wa"] = get_field(first_store, "WhatsApp_Number", "")
            o2["_store_call"] = get_field(first_store, "Phone_Tel", "")
        
        active.append(o2)
    
    # Sort and limit to n offers
    active.sort(key=offer_sort_key)
    return active[:n]


def build_offers_by_store(all_offers, active_stores):
    """
    Build offers grouped by store, respecting current field structure.
    
    Each offer can be:
    - Available to all stores (target_all_stores = Yes)
    - Available to specific stores (target_store_n78 = Yes, etc.)
    """
    result = {get_field(s, "Store_ID"): [] for s in active_stores}
    store_ids = list(result.keys())
    store_map = {sid: s for s in active_stores for sid in [get_field(s, "Store_ID")] if sid == get_field(s, "Store_ID")}
    now_ist = datetime.now(IST)

    print(f"   DEBUG - Processing {len(all_offers)} offers for {len(active_stores)} stores")

    for o in all_offers:
        # Check if offer is active (not expired)
        if not is_offer_active(o, now_ist=now_ist):
            continue
        
        offer_title = get_field(o, "content_title", "Unknown")
        target_all = get_field(o, "target_all_stores", "").strip().lower()
        print(f"   DEBUG - Processing offer: {offer_title} (target_all: {target_all})")
        
        # CRITICAL FIX: Ensure "Target All" offers are added to EVERY store
        if target_all == "yes":
            print(f"   DEBUG - Adding '{offer_title}' to ALL stores (target_all=yes)")
            for store_id in store_ids:
                result[store_id].append(enrich_offer(o, now_ist=now_ist))
        else:
            # Handle specific store targeting
            stores_added = []
            for store_id in store_ids:
                store = store_map[store_id]
                store_id_short = get_field(store, "store_id_short", "")
                if is_offer_for_store(o, store_id, store_id_short, active_stores):
                    result[store_id].append(enrich_offer(o, now_ist=now_ist))
                    stores_added.append(store_id)
            
            print(f"   DEBUG - Offer added to stores: {stores_added}")

    # Sort offers for each store
    for sid in result:
        result[sid].sort(key=offer_sort_key)

    # Debug: Print final counts
    for sid in result:
        print(f"   DEBUG - Store {sid}: {len(result[sid])} offers")

    return result


def flatten_offers(offers_by_store, stores):
    """All offers list with store info merged in for offer-sorted view."""
    store_map = {}
    for s in stores:
        store_id = get_field(s, "store_id") or get_field(s, "Store_ID")
        if store_id:
            store_map[store_id] = s

    out = []
    seen_offers = set()  # Track seen offers to prevent duplicates
    
    for sid, arr in offers_by_store.items():
        st = store_map.get(sid, {})
        for o in arr:
            # Create a unique identifier for each offer
            offer_id = get_field(o, "content_hash", "")
            
            # Only add if we haven't seen this offer before
            if offer_id not in seen_offers:
                seen_offers.add(offer_id)
                o2 = dict(o)
                o2["_store_name"] = get_field(st, "store_display_name", sid)
                o2["_store_appointment"] = get_field(st, "Appointment_URL", "")
                o2["_store_wa"] = get_field(st, "WhatsApp_Number", "")
                o2["_store_call"] = get_field(st, "Phone_Tel", "")
                o2["Store_ID"] = sid  # Add Store_ID field for filtering
                
                # Add enrichment fields using actual Google Sheets field names
                o2["content_type"] = get_field(o, "content_type", "")
                o2["campaign_id"] = get_field(o, "campaign_id", "")
                o2["campaign_priority"] = get_field(o, "campaign_priority", "")
                o2["content_title"] = get_field(o, "content_title", "")
                o2["content_body"] = get_field(o, "content_body", "")
                o2["start_date"] = get_field(o, "start_date", "")
                o2["end_date"] = get_field(o, "end_date", "")
                o2["approval_status"] = get_field(o, "approval_status", "")
                o2["social_enabled"] = get_field(o, "social_enabled", "")
                o2["post_facebook"] = get_field(o, "post_facebook", "")
                o2["post_instagram"] = get_field(o, "post_instagram", "")
                o2["post_google"] = get_field(o, "post_google", "")
                o2["post_website"] = get_field(o, "post_website", "")
                o2["is_expired"] = get_field(o, "is_expired", "")
                o2["target_all_stores"] = get_field(o, "target_all_stores", "")
                o2["target_store_n78"] = get_field(o, "target_store_n78", "")
                o2["target_store_n77"] = get_field(o, "target_store_n77", "")
                o2["target_store_n36"] = get_field(o, "target_store_n36", "")
                o2["target_store_n05"] = get_field(o, "target_store_n05", "")
                o2["target_store_n43"] = get_field(o, "target_store_n43", "")
                o2["has_media"] = get_field(o, "has_media", "")
                o2["media_asset_name"] = get_field(o, "media_asset_name", "")
                o2["caption_template"] = get_field(o, "caption_template", "")
                o2["cta_text"] = get_field(o, "cta_text", "")
                o2["hashtags"] = get_field(o, "hashtags", "")
                o2["content_hash"] = get_field(o, "content_hash", "")
                
                # Add computed fields
                now_ist = dt.now(IST)
                valid_till_str = get_field(o2, "end_date", "")
                if valid_till_str:
                    exp = offer_expiry_dt_ist(valid_till_str)
                    if exp:
                        o2["_expiry_iso"] = exp.isoformat()
                        o2["_days_left"] = max(0, (exp - now_ist).days)
                        o2["_valid_from_iso"] = now_ist.isoformat()
                
                # Media fields for template compatibility
                media_asset_name = get_field(o2, "media_asset_name", "")
                if media_asset_name:
                    o2["Image_Name"] = media_asset_name
                    o2["Image_Available"] = "Yes"
                else:
                    o2["Image_Name"] = ""
                    o2["Image_Available"] = "No"
                
                out.append(o2)
    try:
        out.sort(key=offer_sort_key)
        return out
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
            cat = get_field(svc, "Category", "").lower()
            if not any(kw in cat for kw in keywords):
                continue
            for price_field in ("Regular_Cost", "Price", "Cost", "MRP"):
                p = parse_price(get_field(svc, price_field, ""))
                if p and p > 0:
                    min_p = p if (min_p is None or p < min_p) else min_p
                    break
        result[display_name] = int(min_p) if min_p else None
    return result


def build_reviews_by_store(all_reviews, active_stores):
    """Group approved reviews by store_id."""
    store_ids = {get_field(s, "Store_ID") for s in active_stores}
    # Also collect Google Place IDs for matching
    place_ids = {get_field(s, "google_place_id", "") for s in active_stores}
    result = {get_field(s, "Store_ID"): [] for s in active_stores}

    for r in all_reviews:
        sid = get_field(r, "store_id", "").strip()  # Use store_id (lowercase) from reviews data
        
        # Match by Store_ID or Google Place ID
        matched_store_id = None
        if sid in store_ids:
            matched_store_id = sid
        elif sid.startswith("locations/"):
            # Extract location ID and match with place_id
            location_id = sid
            for store in active_stores:
                store_place_id = get_field(store, "google_place_id", "")
                # Convert place_id to location_id format
                if store_place_id and f"locations/{store_place_id}" == location_id:
                    matched_store_id = get_field(store, "Store_ID")
                    break
        
        if matched_store_id:
            show_in_website = get_field(r, "show_it_in_website", "")
            # Include reviews if show_it_in_website is "Yes" or empty (default to show)
            if is_yes(show_in_website) or show_in_website == "":
                # Convert Stars to int
                try:
                    r["Stars"] = int(float(get_field(r, "Stars", 5)))
                except (ValueError, TypeError):
                    r["Stars"] = 5
                result[matched_store_id].append(r)

    return result


def get_featured_reviews(reviews_by_store, n=6):
    """Collect top reviews from across stores for the homepage."""
    all_approved = []
    for sid in reviews_by_store:
        all_approved.extend(reviews_by_store[sid])
    return all_approved[:n]


# ── HTML minification ─────────────────────────────────────────────────────────

def minify_html(html):
    """
    Lightweight HTML minification:
    - Collapse multiple blank lines to one
    - Strip leading whitespace from lines
    - Remove HTML comments (preserve IE conditionals <!--[if)
    """
    html = re.sub(r"<!--(?!\[if).*?-->", "", html, flags=re.DOTALL)
    html = re.sub(r"\n{3,}", "\n\n", html)
    lines = [line.lstrip() for line in html.split("\n")]
    html = "\n".join(lines)
    html = re.sub(r"[ \t]{2,}", " ", html)
    return html.strip()


# ── Page writers ──────────────────────────────────────────────────────────────

def write(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    html = minify_html(html)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    size_kb = len(html.encode()) / 1024
    print(f"  Written: {os.path.relpath(path, ROOT_DIR)} ({size_kb:.1f} KB)")


def get_service_categories_with_icons(services):
    """
    Extract specific service categories with their icon names from services data.
    Returns list of dicts: [{'name': 'Category Name', 'icon_name': 'filename.jpg'}]
    """
    target_categories = [
        'HAIR STYLING - FEMALE', 
        'HAIR WASH AND BLOW DRY', 
        'COLOURING AND HIGHLIGHTS', 
        'TEXTURE', 
        'HAIR STYLING', 
        'HEAD MASSAGE'
    ]
    
    categories = {}
    
    for service in services:
        category = get_field(service, "Category", "").strip()
        icon_name = get_field(service, "service_icon_name", "").strip()
        
        if category in target_categories and icon_name and icon_name != 'NA':
            # Use the first icon found for each category
            if category not in categories:
                categories[category] = {
                    'name': category,
                    'icon_name': icon_name,
                    'href': 'services/'
                }
    
    # Return categories in target order
    result = []
    for target_cat in target_categories:
        if target_cat in categories:
            result.append(categories[target_cat])
        else:
            # Fallback to default if category not found
            result.append({
                'name': target_cat,
                'icon_name': 'service_default.jpg',
                'href': 'services/'
            })
    
    return result


def build_seo_lookup(page_seo_config):
    """
    Build a url_slug → seo_config lookup table from page_seo_config list.
    Keys are normalised (trailing slash stripped, lowercase) for robust matching.
    """
    lookup = {}
    for config in (page_seo_config or []):
        slug = config.get('url_slug', '').rstrip('/')
        if slug:
            lookup[slug.lower()] = config
    return lookup


def seo_for_path(seo_lookup, dest_path):
    """
    Return the SEO config dict for a given destination path, or {}.
    dest_path examples: '/index.html', '/offers/index.html',
                        '/stores/bangalore/jp-nagar-5th-phase/index.html'
    Tries exact match first, then strips trailing '/index.html' for directory match.
    """
    key = dest_path.rstrip('/').lower()
    if key in seo_lookup:
        return seo_lookup[key]
    # Try without /index.html suffix (matches directory-style slugs)
    if key.endswith('/index.html'):
        key2 = key[:-len('/index.html')]
        if key2 in seo_lookup:
            return seo_lookup[key2]
    return {}


def build_index(stores, featured_offers, min_prices, featured_reviews, env, services=None, service_categories_count=6, page_seo_config=None):
    # Extract city_slug for global use
    city_slug = "bangalore"  # Default fallback
    if stores and len(stores) > 0:
        first_store = stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            city_slug = slugify(address_city)

    # Extract service categories with icons
    service_categories = get_service_categories_with_icons(services) if services else []

    # SEO lookup by url_slug
    seo_lookup = build_seo_lookup(page_seo_config)
    home_seo = seo_for_path(seo_lookup, '/index.html')

    dest_path = os.path.join(OUTPUT_DIR, "index.html")
    html = env.get_template("index.html.j2").render(
        stores=stores,
        featured_offers=featured_offers,
        min_prices=min_prices,
        featured_reviews=featured_reviews,
        services=services or [],
        service_categories=service_categories,
        service_categories_count=service_categories_count,
        city_slug=city_slug,
        website_base_url=WEBSITE_BASE_URL,
        site_url=WEBSITE_BASE_URL,
        home_seo=home_seo,
        seo_title=home_seo.get('seo_title', ''),
        meta_description=home_seo.get('meta_description', ''),
        h1_heading=home_seo.get('h1_heading', ''),
        og_image=home_seo.get('og_image', ''),
        canonical_url=home_seo.get('canonical_url', ''),
        schema_type=home_seo.get('schema_type', 'Organization'),
    )
    write(dest_path, html)
    print(f'[SEO Check] Applied title "{home_seo.get("seo_title", "")}" to {home_seo.get("url_slug", "/index.html")}')


def format_text_professionally(text):
    """
    Format text to be more professional and readable.
    - Converts ALL CAPS to Title Case with proper grammar rules
    - Keeps small words lowercase (except at start)
    - Preserves acronyms and special terms
    - Handles special characters properly
    """
    if not text or not isinstance(text, str):
        return text
    
    text = text.strip()
    
    # If text is empty or just a dash, return as-is
    if not text or text == "-":
        return text
    
    # If text is already in mixed case (not all caps), return as-is
    if not text.isupper():
        return text
    
    # Words that should be lowercase in title case (unless at start)
    small_words = {
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'in', 'of', 
        'on', 'or', 'the', 'to', 'up', 'via', 'with', 'from', 'into'
    }
    
    # Split by common delimiters but preserve them
    words = []
    current_word = []
    
    for char in text:
        if char in (' ', '/', '|', '(', ')', '-', '&', ',', '.', '+'):
            if current_word:
                words.append(''.join(current_word))
                current_word = []
            words.append(char)
        else:
            current_word.append(char)
    
    if current_word:
        words.append(''.join(current_word))
    
    # Convert each word to title case with proper rules
    formatted_words = []
    word_index = 0  # Track actual word position (not delimiter position)
    
    for i, word in enumerate(words):
        # If it's a delimiter, keep as-is
        if word in (' ', '/', '|', '(', ')', '-', '&', ',', '.', '+'):
            formatted_words.append(word)
        else:
            word_lower = word.lower()
            
            # Always capitalize first word and words after opening parenthesis
            is_first = word_index == 0
            prev_is_open_paren = i > 0 and words[i-1] == '('
            
            if is_first or prev_is_open_paren:
                formatted_words.append(word.capitalize())
            elif word_lower in small_words:
                # Keep small words lowercase
                formatted_words.append(word_lower)
            elif len(word) <= 2:
                # Keep very short words/acronyms uppercase (like "UV", "pH")
                formatted_words.append(word.upper())
            else:
                formatted_words.append(word.capitalize())
            
            word_index += 1
    
    return ''.join(formatted_words)


def normalize_service(svc):
    """
    Normalize service field names for template compatibility.
    Maps lowercase field names to capitalized versions.
    Also formats service names and descriptions professionally.
    """
    normalized = dict(svc)
    
    # Field name mappings (lowercase → Capitalized)
    field_mappings = {
        "category": "Category",
        "service_name": "Service_Name",
        "duration": "Duration",
        "regular_cost": "Regular_Cost",
        "member_cost": "Member_Cost",
        "gender": "Gender",
        "description": "Description",
        "service_icon_name": "Service_Icon_Name",
    }
    
    for old_name, new_name in field_mappings.items():
        if old_name in svc and new_name not in svc:
            value = svc[old_name]
            
            # Format service names and descriptions professionally
            if old_name in ("service_name", "category"):
                value = format_text_professionally(value)
            elif old_name == "description":
                # For descriptions, convert to sentence case
                if value and isinstance(value, str) and value.strip() and value.strip() != "-":
                    value = format_text_professionally(value)
            
            normalized[new_name] = value

    # Map store availability fields: store_n78 → Store_N78
    for key in list(svc.keys()):
        if key.lower().startswith("store_n") and key != key.upper():
            capitalized = "Store_" + key[len("store_"):].upper()
            if capitalized not in normalized:
                normalized[capitalized] = svc[key]

    return normalized


def build_services(stores, env, active_store_ids=None, page_seo_config=None):
    # Extract city_slug for global use
    city_slug = "bangalore"  # Default fallback
    if stores and len(stores) > 0:
        first_store = stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            city_slug = slugify(address_city)

    # SEO lookup by url_slug
    seo_lookup = build_seo_lookup(page_seo_config)
    services_seo = seo_for_path(seo_lookup, '/services/index.html')

    # If no active_store_ids provided, extract from stores
    if active_store_ids is None:
        active_store_ids = [get_field(s, "Store_ID") for s in stores]

    # Normalize services from Google Sheets
    all_services = load_json_data("services.json")
    normalized_services = []
    seen_cats = set()

    for s in all_services:
        # Skip services not assigned to any store
        if not any(is_yes(get_field(s, store_id, "")) for store_id in STORE_ORDER_SERVICES):
            continue

        normalized = normalize_service(s)
        if normalized:
            normalized_services.append(normalized)
            seen_cats.add(normalized["Category"])

    services_dir = os.path.join(OUTPUT_DIR, "services")
    os.makedirs(services_dir, exist_ok=True)

    html = env.get_template("services.html.j2").render(
        services_json=json.dumps(normalized_services, ensure_ascii=False),
        services_list=normalized_services,
        categories=seen_cats,
        stores=stores,
        active_store_ids=active_store_ids,
        city_slug=city_slug,
        website_base_url=WEBSITE_BASE_URL,
        site_url=WEBSITE_BASE_URL,
        services_seo=services_seo,
        seo_title=services_seo.get('seo_title', ''),
        meta_description=services_seo.get('meta_description', ''),
        h1_heading=services_seo.get('h1_heading', ''),
        og_image=services_seo.get('og_image', ''),
        canonical_url=services_seo.get('canonical_url', ''),
        schema_type=services_seo.get('schema_type', 'Service'),
    )
    write(os.path.join(services_dir, "index.html"), html)
    print(f'[SEO Check] Applied title "{services_seo.get("seo_title", "")}" to {services_seo.get("url_slug", "/services/index.html")}')


def build_store(store, all_services, all_offers, all_stylists, reviews_by_store, active_stores, env, seo_data=None):
    store_id = get_field(store, "Store_ID")
    store_id_short = get_field(store, "store_id_short", "")

    # Derive store slug (used for URL path)
    store_slug = slugify(get_field(store, "store_display_name", "") or get_field(store, "store_id_short", ""))
    city = get_field(store, "address_city", "bangalore").lower().replace(" ", "-")
    dest_url_slug = f"/stores/{city}/{store_slug}"

    # Look up SEO by url_slug from merged seo_data dict
    store_seo_data = {}
    if seo_data:
        # seo_data is keyed by url_slug (from merge_seo_with_store_data)
        key = dest_url_slug.lower().rstrip('/')
        store_seo_data = seo_data.get(key, seo_data.get(dest_url_slug, {}))
        if not store_seo_data:
            # Fallback: match by page_id using display-name slug (new format: jp_nagar_5th_phase)
            # or legacy short id (n78), or Store_ID
            display_name_slug = get_field(store, "store_display_name", "").lower().replace(" ", "_").replace("-", "_")
            for url_slug, seo_info in seo_data.items():
                pid = seo_info.get('page_id', '')
                if (pid == store_id or
                        pid == store_id_short.lower() or
                        pid == display_name_slug or
                        seo_info.get('Store_ID') == store_id):
                    store_seo_data = seo_info
                    break
    
    # Filter services for this store using BOTH Store_ID and store_id_short
    # Services may have fields like "Store_N78" or "store_n78" (case-insensitive)
    svc_list = []
    for s in all_services:
        # Try both Store_ID (e.g., "Store_N78") and store_id_short (e.g., "N78")
        # get_field handles case-insensitive matching
        if is_yes(get_field(s, store_id, "")) or is_yes(get_field(s, f"store_{store_id_short.lower()}", "")):
            normalized = normalize_service(s)
            if normalized:
                svc_list.append(normalized)
    
    # Filter offers for this store using campaign field names
    eligible_offers = []
    
    for o in all_offers:
        is_eligible = False
        
        # Try direct Store_ID match first
        if get_field(o, "Store_ID") == store_id:
            is_eligible = True
        # Check if offer targets all stores
        elif is_yes(get_field(o, "target_all_stores", "")):
            is_eligible = True
        else:
            # Try campaign field names (case-insensitive)
            store_short = store_id.replace("Store_", "").lower()
            campaign_field = f"target_store_{store_short}"
            if is_yes(get_field(o, campaign_field, "")):
                is_eligible = True
        
        if is_eligible:
            eligible_offers.append(o)
    
    # Take only the first 2 eligible offers
    offers = eligible_offers[:2]
    
    # Filter stylists for this store (using store_id_short which stylists data uses)
    store_id_short = get_field(store, "store_id_short", "")
    stylists = [s for s in all_stylists if get_field(s, "store_id_short") == store_id_short]
    
    # Get reviews for this store
    store_reviews = reviews_by_store.get(store_id, [])
    
    # Create enriched store object with SEO data
    enriched_store = {
        **store,  # Original store data
        **store_seo_data,  # Merged SEO data (store-specific overrides)
        's': store,  # Add s variable for template compatibility
        'slug': store_slug,  # Add slug for template use
        'city_slug': slugify(get_field(store, "address_city", "bangalore")),  # Add city_slug for navigation
        'services_json': json.dumps(svc_list, ensure_ascii=False),
        'services': svc_list,
        'offers': offers,
        'stylists': stylists,
        'reviews': store_reviews,
    }
    
    idx = next((i for i, s in enumerate(active_stores) if get_field(s, "Store_ID") == store_id), 0)
    prev_store = active_stores[(idx - 1) % len(active_stores)]
    next_store = active_stores[(idx + 1) % len(active_stores)]

    store_reviews = reviews_by_store.get(store_id, [])

    # Use display name slug for filename (e.g., jp-nagar-5th-phase)
    display_name = get_field(store, "store_display_name", "") or get_field(store, "store_id_short", "")
    slug = slugify(display_name)
    
    # Add slug to store object for template use
    store_with_slug = dict(store)
    store_with_slug['slug'] = slug
    
    html = env.get_template("store.html.j2").render(
        store=store_with_slug,
        s=store_with_slug,  # Add s variable for template compatibility
        slug=slug,  # Add slug for template use
        city_slug=slugify(get_field(store, "address_city", "bangalore")),  # Add city_slug for navigation
        services_json=json.dumps(svc_list, ensure_ascii=False),
        services=svc_list,
        offers=offers,
        stylists=stylists,
        reviews=store_reviews,
        website_base_url=WEBSITE_BASE_URL,
        site_url=WEBSITE_BASE_URL,
        prev_store=prev_store,
        next_store=next_store,
        all_stores=active_stores,
        store_seo=store_seo_data,
        seo_title=store_seo_data.get('seo_title', ''),
        meta_description=store_seo_data.get('meta_description', ''),
        h1_heading=store_seo_data.get('h1_heading', ''),
        og_image=store_seo_data.get('og_image', ''),
        canonical_url=store_seo_data.get('canonical_url', ''),
        schema_type=store_seo_data.get('schema_type', 'HairSalon'),
    )

    # Use new slug-based URL structure
    city = get_field(store, "address_city", "bangalore").lower().replace(" ", "-")
    city_dir = os.path.join(STORES_DIR, city)
    os.makedirs(city_dir, exist_ok=True)

    # Create store directory and index.html
    store_dir = os.path.join(city_dir, slug)
    os.makedirs(store_dir, exist_ok=True)
    write(os.path.join(store_dir, "index.html"), html)
    print(f'[SEO Check] Applied title "{store_seo_data.get("seo_title", "")}" to {dest_url_slug}')


def build_contact(stores, env, page_seo_config=None):
    # Extract city_slug for global use
    city_slug = "bangalore"  # Default fallback
    if stores and len(stores) > 0:
        first_store = stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            city_slug = slugify(address_city)

    seo_lookup = build_seo_lookup(page_seo_config)
    contact_seo = seo_for_path(seo_lookup, '/contact/index.html')

    # Create contact directory
    contact_dir = os.path.join(OUTPUT_DIR, "contact")
    os.makedirs(contact_dir, exist_ok=True)

    html = env.get_template("contact.html.j2").render(
        stores=stores,
        city_slug=city_slug,
        website_base_url=WEBSITE_BASE_URL,
        site_url=WEBSITE_BASE_URL,
        contact_seo=contact_seo,
        seo_title=contact_seo.get('seo_title', ''),
        meta_description=contact_seo.get('meta_description', ''),
        h1_heading=contact_seo.get('h1_heading', ''),
        og_image=contact_seo.get('og_image', ''),
        canonical_url=contact_seo.get('canonical_url', ''),
        schema_type=contact_seo.get('schema_type', 'ContactPage'),
    )
    write(os.path.join(contact_dir, "index.html"), html)
    print(f'[SEO Check] Applied title "{contact_seo.get("seo_title", "")}" to {contact_seo.get("url_slug", "/contact/index.html")}')


def build_offers_page(stores, offers_by_store, env, page_seo_config=None):
    # Collect all offers from all stores without deduplication (like stores page)
    offers_all = []
    for store_id, store_offers in offers_by_store.items():
        offers_all.extend(store_offers)

    # Sort by priority and date
    offers_all.sort(key=offer_sort_key)

    # Extract city_slug for global use
    city_slug = "bangalore"  # Default fallback
    if stores and len(stores) > 0:
        first_store = stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            city_slug = slugify(address_city)

    # SEO lookup by url_slug
    seo_lookup = build_seo_lookup(page_seo_config)
    offers_seo = seo_for_path(seo_lookup, '/offers/index.html')

    # Create offers directory
    offers_dir = os.path.join(OUTPUT_DIR, "offers")
    os.makedirs(offers_dir, exist_ok=True)

    html = env.get_template("offers.html.j2").render(
        stores=stores,
        offers_by_store=offers_by_store,
        offers_all=offers_all,
        city_slug=city_slug,
        total_offers=sum(len(v) for v in offers_by_store.values()),
        now_ist_iso=dt.now(IST).isoformat(),
        website_base_url=WEBSITE_BASE_URL,
        site_url=WEBSITE_BASE_URL,
        offers_seo=offers_seo,
        seo_title=offers_seo.get('seo_title', ''),
        meta_description=offers_seo.get('meta_description', ''),
        h1_heading=offers_seo.get('h1_heading', ''),
        og_image=offers_seo.get('og_image', ''),
        canonical_url=offers_seo.get('canonical_url', ''),
        schema_type=offers_seo.get('schema_type', 'Offer'),
    )
    write(os.path.join(offers_dir, "index.html"), html)
    print(f'[SEO Check] Applied title "{offers_seo.get("seo_title", "")}" to {offers_seo.get("url_slug", "/offers/index.html")}')


def build_store_offers_pages(stores, offers_by_store, env, page_seo_config=None):
    """
    Build store-specific offer pages at /stores/bangalore/[store-slug]/offers/index.html
    """
    print("\n📋 Building store-specific offer pages...")

    # Extract city_slug for global use
    city_slug = "bangalore"  # Default fallback
    if stores and len(stores) > 0:
        first_store = stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            city_slug = slugify(address_city)

    # Build SEO lookup keyed by url_slug
    seo_lookup = build_seo_lookup(page_seo_config)

    built_count = 0

    for store in stores:
        store_id = get_field(store, "Store_ID")
        store_slug = slugify(get_field(store, "store_display_name", "") or get_field(store, "store_id_short", ""))

        if not store_slug:
            continue

        # Get offers for this store
        store_offers = offers_by_store.get(store_id, [])

        # Filter campaigns for this specific store (match store_id in applicable_stores or global)
        store_specific_campaigns = []
        for offer in store_offers:
            # Check if this offer targets this store specifically or is global
            if (get_field(offer, "target_all_stores") == "Yes" or
                    get_field(offer, f"target_store_{store_id.lower().replace('store_', 'n')}") == "Yes" or
                    get_field(offer, "Store_ID") == store_id):
                store_specific_campaigns.append(offer)

        # SEO lookup by destination url_slug
        dest_slug = f"/stores/bangalore/{store_slug}/offers"
        store_offers_seo = seo_for_path(seo_lookup, dest_slug + '/index.html') or seo_for_path(seo_lookup, dest_slug)

        # Create output path
        offers_dir = os.path.join(OUTPUT_DIR, "stores", "bangalore", store_slug, "offers")
        os.makedirs(offers_dir, exist_ok=True)

        # Render the localized template
        from datetime import datetime
        current_date = datetime.now().strftime('%Y-%m-%d')

        html = env.get_template("store_offers.html.j2").render(
            store=store,
            campaigns=store_specific_campaigns,
            city_slug=city_slug,
            website_base_url=WEBSITE_BASE_URL,
            site_url=WEBSITE_BASE_URL,
            all_stores=stores,
            store_seo=store_offers_seo,
            seo_title=store_offers_seo.get('seo_title', ''),
            meta_description=store_offers_seo.get('meta_description', ''),
            h1_heading=store_offers_seo.get('h1_heading', ''),
            og_image=store_offers_seo.get('og_image', ''),
            canonical_url=store_offers_seo.get('canonical_url', ''),
            schema_type=store_offers_seo.get('schema_type', 'Offer'),
            current_date=current_date
        )

        write(os.path.join(offers_dir, "index.html"), html)
        built_count += 1
        print(f"   ✅ Built offers page for {get_field(store, 'store_display_name', store_id)}")
        print(f'[SEO Check] Applied title "{store_offers_seo.get("seo_title", "")}" to {dest_slug}')

    print(f"   ✅ Built {built_count} store-specific offer pages")


def build_cancellation_policy(stores, env, page_seo_config=None):
    # Extract city_slug for global use
    city_slug = "bangalore"  # Default fallback
    if stores and len(stores) > 0:
        first_store = stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            city_slug = slugify(address_city)

    seo_lookup = build_seo_lookup(page_seo_config)
    cancel_seo = seo_for_path(seo_lookup, '/cancellation-policy/index.html')

    # Create cancellation-policy directory
    cancellation_dir = os.path.join(OUTPUT_DIR, "cancellation-policy")
    os.makedirs(cancellation_dir, exist_ok=True)

    html = env.get_template("cancellation-policy.html.j2").render(
        stores=stores,
        city_slug=city_slug,
        website_base_url=WEBSITE_BASE_URL,
        site_url=WEBSITE_BASE_URL,
        cancel_seo=cancel_seo,
        seo_title=cancel_seo.get('seo_title', ''),
        meta_description=cancel_seo.get('meta_description', ''),
        h1_heading=cancel_seo.get('h1_heading', ''),
        og_image=cancel_seo.get('og_image', ''),
        canonical_url=cancel_seo.get('canonical_url', ''),
        schema_type=cancel_seo.get('schema_type', 'WebPage'),
    )
    write(os.path.join(cancellation_dir, "index.html"), html)
    print(f'[SEO Check] Applied title "{cancel_seo.get("seo_title", "")}" to {cancel_seo.get("url_slug", "/cancellation-policy/index.html")}')


def build_booking_policy(stores, env, page_seo_config=None):
    # Extract city_slug for global use
    city_slug = "bangalore"  # Default fallback
    if stores and len(stores) > 0:
        first_store = stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            city_slug = slugify(address_city)

    seo_lookup = build_seo_lookup(page_seo_config)
    booking_seo = seo_for_path(seo_lookup, '/booking-policy/index.html')

    # Create booking-policy directory
    booking_dir = os.path.join(OUTPUT_DIR, "booking-policy")
    os.makedirs(booking_dir, exist_ok=True)

    html = env.get_template("booking-policy.html.j2").render(
        stores=stores,
        city_slug=city_slug,
        website_base_url=WEBSITE_BASE_URL,
        site_url=WEBSITE_BASE_URL,
        booking_seo=booking_seo,
        seo_title=booking_seo.get('seo_title', ''),
        meta_description=booking_seo.get('meta_description', ''),
        h1_heading=booking_seo.get('h1_heading', ''),
        og_image=booking_seo.get('og_image', ''),
        canonical_url=booking_seo.get('canonical_url', ''),
        schema_type=booking_seo.get('schema_type', 'WebPage'),
    )
    write(os.path.join(booking_dir, "index.html"), html)
    print(f'[SEO Check] Applied title "{booking_seo.get("seo_title", "")}" to {booking_seo.get("url_slug", "/booking-policy/index.html")}')


def build_about(active_stores, env, page_seo_config=None):
    # Extract city_slug for global use
    city_slug = "bangalore"  # Default fallback
    if active_stores and len(active_stores) > 0:
        first_store = active_stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            city_slug = slugify(address_city)

    seo_lookup = build_seo_lookup(page_seo_config)
    about_seo = seo_for_path(seo_lookup, '/about/index.html')

    # Create about directory
    about_dir = os.path.join(OUTPUT_DIR, "about")
    os.makedirs(about_dir, exist_ok=True)

    html = env.get_template("about.html.j2").render(
        stores=active_stores,
        city_slug=city_slug,
        website_base_url=WEBSITE_BASE_URL,
        site_url=WEBSITE_BASE_URL,
        about_seo=about_seo,
        seo_title=about_seo.get('seo_title', ''),
        meta_description=about_seo.get('meta_description', ''),
        h1_heading=about_seo.get('h1_heading', ''),
        og_image=about_seo.get('og_image', ''),
        canonical_url=about_seo.get('canonical_url', ''),
        schema_type=about_seo.get('schema_type', 'AboutPage'),
    )
    write(os.path.join(about_dir, "index.html"), html)
    print(f'[SEO Check] Applied title "{about_seo.get("seo_title", "")}" to {about_seo.get("url_slug", "/about/index.html")}')


def build_intranet(active_stores, env, trainings):
    """Build intranet staff portal pages"""
    # Create intranet directory
    intranet_dir = os.path.join(OUTPUT_DIR, "intranet")
    os.makedirs(intranet_dir, exist_ok=True)
    
    # Build intranet home page
    html = env.get_template("intranet/index.html.j2").render(stores=active_stores)
    write(os.path.join(intranet_dir, "index.html"), html)
    
    # Create QR code directory and page
    qrcode_dir = os.path.join(intranet_dir, "qrcode")
    os.makedirs(qrcode_dir, exist_ok=True)
    
    # Prepare data for Filter Engine
    stores_data = [
        {
            'label': s.get('store_display_name', s.get('brand_store_name', s.get('Store_ID', ''))),
            'value': s.get('store_id_short', s.get('Store_ID', ''))  # Use actual store_id_short like N78
        }
        for s in active_stores
    ]
    
    qr_types_data = [
        {'label': 'Google Review', 'value': 'google'},
        {'label': 'Instagram', 'value': 'instagram'},
        {'label': 'Facebook', 'value': 'facebook'}
    ]
    
    html = env.get_template("intranet/qrcode/index.html.j2").render(
        stores=active_stores,
        stores_data=stores_data,
        qr_types_data=qr_types_data
    )
    write(os.path.join(qrcode_dir, "index.html"), html)
    
    # Create training directory and page
    training_dir = os.path.join(intranet_dir, "training")
    os.makedirs(training_dir, exist_ok=True)
    
    html = env.get_template("intranet/training/index.html.j2").render(stores=active_stores, trainings=trainings)
    write(os.path.join(training_dir, "index.html"), html)
    
    # Create intranetclone test directory and page
    intranetclone_dir = os.path.join(OUTPUT_DIR, "intranetclone")
    os.makedirs(intranetclone_dir, exist_ok=True)
    
    html = env.get_template("intranetclone/index.html.j2").render(stores=active_stores, all_stores=active_stores)
    write(os.path.join(intranetclone_dir, "index.html"), html)
    print(f"   ✅ Built intranetclone test page")


# ── Add Image Copy Step ──────────────────────────────────────────────────────
def copy_qr_images_for_intranet():
    """No-op function since using root images/qrcodes"""
    pass
    import shutil
    
    source_dir = os.path.join(os.getcwd(), 'images', 'qrcodes')
    target_dir = os.path.join(os.getcwd(), 'intranet', 'images', 'qrcodes')
    
    if os.path.exists(source_dir):
        os.makedirs(target_dir, exist_ok=True)
        for filename in os.listdir(source_dir):
            if filename.endswith('.png'):
                source_path = os.path.join(source_dir, filename)
                target_path = os.path.join(target_dir, filename)
                shutil.copy2(source_path, target_path)
        print(f"✅ Copied {len(os.listdir(source_dir))} QR code images to intranet")
    else:
        print(f"⚠️  Source QR code directory not found: {source_dir}")


def copy_offer_images(processed_offers):
    """No-op function for backward compatibility.
    Images are now served directly from /campaigns/offer/03_published."""
    print("✅ Using images directly from /campaigns/offer/03_published")


# ── Main ──────────────────────────────────────────────────────────────────────

def build_careers(active_stores, careers_data, env, page_seo_config=None):
    """Build careers pages"""
    # Extract careers array from data object
    if isinstance(careers_data, dict) and "careers" in careers_data:
        careers_list = careers_data["careers"]
    else:
        careers_list = careers_data or []
    
    print("📋 Building careers pages...")
    
    # Extract city from store data and standardize it
    city_slug = DEFAULT_CITY_SLUG  # Default fallback
    if active_stores and len(active_stores) > 0:
        first_store = active_stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            city_slug = standardize_city_slug(address_city)
    
    # Get SEO config for careers page
    seo_lookup = build_seo_lookup(page_seo_config)
    careers_seo = seo_for_path(seo_lookup, '/careers/bangalore/index.html') or seo_for_path(seo_lookup, '/careers/bangalore/')
    
    print(f"   📍 Using city_slug: {city_slug}")
    
    # Group careers by store and enrich all careers
    careers_by_store = {}
    enriched_careers_list = []
    
    for career in careers_list:
        store_id_short = get_field(career, "store_id_short", "")
        
        # Find matching store by store_id_short (case-insensitive fallback)
        matching_store = next((s for s in active_stores if get_field(s, "store_id_short", "").lower() == store_id_short.lower()), None)
        if not matching_store:
            # Fallback: try direct comparison
            matching_store = next((s for s in active_stores if get_field(s, "store_id_short", "") == store_id_short), None)
        if matching_store:
            store_id = get_field(matching_store, "Store_ID", "")
            if store_id not in careers_by_store:
                careers_by_store[store_id] = []
            
            # Enrich career with store object and slugs
            enriched_career = dict(career)
            enriched_career["store"] = {
                "display_name": get_field(matching_store, "store_display_name", store_id),
                "slug": slugify(get_field(matching_store, "store_display_name", "") or get_field(matching_store, "store_id_short", "")),
                "address_line_1": get_field(matching_store, "address_line_1", ""),
                "address_pincode": get_field(matching_store, "address_pincode", ""),
                "street_address": get_field(matching_store, "address_full", get_field(matching_store, "address_line_1", "")),
                "postal_code": get_field(matching_store, "address_pincode", "")
            }
            # Create job slug from job_title
            job_title = get_field(career, "job_title", "")
            enriched_career["job_slug"] = job_title.lower().replace(" ", "-").replace("/", "-").replace("_", "-")
            
            careers_by_store[store_id].append(enriched_career)
            enriched_careers_list.append(enriched_career)
    
    # Build main careers page
    careers_dir = os.path.join(OUTPUT_DIR, "careers", "bangalore")
    os.makedirs(careers_dir, exist_ok=True)
    
    # Prepare stores with job counts for template
    stores_with_counts = []
    for store in active_stores:
        store_id = get_field(store, "Store_ID")
        job_count = len(careers_by_store.get(store_id, []))
        
        # Get store slug using same logic as store pages
        store_id_short = get_field(store, "store_id_short", "")
        slug = slugify(store_id_short.replace(' ', '-'))
        
        # Create store object with slug property
        store_with_slug = dict(store)
        store_with_slug['slug'] = slug
        
        # Create context stores list for template
    context_stores = []
    for s in active_stores:
        # Get job count for this store
        store_id = get_field(s, "Store_ID")
        job_count = len(careers_by_store.get(store_id, []))
        
        # Create professional slug from store_display_name
        store_display_name = get_field(s, "store_display_name", "store")
        final_slug = store_display_name.lower().replace(' ', '-').replace('&', 'and').strip()
        
        context_stores.append({
            'final_name': store_display_name,
            'final_slug': final_slug,
            'store_id_short': get_field(s, "store_id_short", ""),
            'job_count': job_count
        })
    
    # Create clean context for careers page
    career_context = {
        'career_stores': context_stores,  # For career filter buttons
        'all_stores': active_stores,      # For header navigation
        'city_slug': city_slug,
        'jobs': enriched_careers_list,
        'website_base_url': WEBSITE_BASE_URL,
        'site_url': WEBSITE_BASE_URL,
        'careers_data': enriched_careers_list,
        'careers_by_store': careers_by_store,
        'get_job_url': get_job_url,
        'current_store_slug': None,  # No store selected on main page
        'careers_seo': careers_seo,
        'seo_title': careers_seo.get('seo_title', ''),
        'meta_description': careers_seo.get('meta_description', ''),
        'h1_heading': careers_seo.get('h1_heading', ''),
        'og_image': careers_seo.get('og_image', ''),
        'canonical_url': careers_seo.get('canonical_url', ''),
        'schema_type': careers_seo.get('schema_type', 'JobPosting'),
    }

    html = env.get_template("careers-city.html.j2").render(**career_context)

    write(os.path.join(careers_dir, "index.html"), html)
    print(f'[SEO Check] Applied title "{careers_seo.get("seo_title", "")}" to {careers_seo.get("url_slug", "/careers/bangalore/")}')
    
    # Create context stores list for template (same as main careers page) - MOVE OUTSIDE LOOP
    context_stores = []
    for s in active_stores:
        # Get job count for this store
        store_id = get_field(s, "Store_ID")
        job_count = len(careers_by_store.get(store_id, []))
        
        # Create professional slug from store_display_name
        store_display_name = get_field(s, "store_display_name", "store")
        final_slug = store_display_name.lower().replace(' ', '-').replace('&', 'and').strip()
        
        context_stores.append({
            'final_name': store_display_name,
            'final_slug': final_slug,
            'store_id_short': get_field(s, "store_id_short", ""),
            'job_count': job_count
        })
    
    # Build individual store career pages for ALL stores (even those without jobs)
    for store in active_stores:
        store_id = get_field(store, "Store_ID")
        store_id_short = get_field(store, "store_id_short", "")
        store_careers = careers_by_store.get(store_id, [])
        
        # Use same professional slug logic as template
        display_name = get_field(store, "store_display_name", "") or get_field(store, "store_id_short", "")
        slug = display_name.lower().replace(' ', '-').replace('&', 'and').strip()
        
        # DEBUG: Print slug generation
        print(f"DEBUG: {display_name} -> slug: {slug}")
        
        store_dir = os.path.join(careers_dir, slug)
        os.makedirs(store_dir, exist_ok=True)
        
        # Clean up old .html files before building new structure
        for item in os.listdir(store_dir):
            if item.endswith('.html') and item != 'index.html':
                old_file = os.path.join(store_dir, item)
                try:
                    os.remove(old_file)
                    print(f"    🗑️  Removed old file: {item}")
                except OSError:
                    pass
        
        _store_careers_seo = seo_for_path(seo_lookup, f'/careers/bangalore/{slug}')
        html = env.get_template("careers-store.html.j2").render(
            store=store,
            jobs=store_careers,
            career_stores=context_stores,  # For career filter buttons
            all_stores=active_stores,      # For header navigation
            website_base_url=WEBSITE_BASE_URL,
            site_url=WEBSITE_BASE_URL,
            city_slug=city_slug,  # Use dynamic city_slug
            store_slug=slug,  # Use actual store slug
            current_store_slug=slug,  # For active button logic
            get_job_url=get_job_url,
            careers_seo=_store_careers_seo,
            seo_title=_store_careers_seo.get('seo_title', ''),
            meta_description=_store_careers_seo.get('meta_description', ''),
            h1_heading=_store_careers_seo.get('h1_heading', ''),
            og_image=_store_careers_seo.get('og_image', ''),
            canonical_url=_store_careers_seo.get('canonical_url', ''),
            schema_type=_store_careers_seo.get('schema_type', 'JobPosting'),
        )

        write(os.path.join(store_dir, "index.html"), html)
        print(f'[SEO Check] Applied title "{_store_careers_seo.get("seo_title", "")}" to /careers/bangalore/{slug}')
        
        # Build individual job detail pages
        for career in store_careers:
            job_slug = career.get('job_slug', '')
            if job_slug:
                job_html = env.get_template("careers-job.html.j2").render(
                    job=career,  # Pass the enriched career object
                    store=career.get('store', {}),  # Use enriched store from career
                    all_stores=active_stores,      # For header navigation
                    website_base_url=WEBSITE_BASE_URL,
                    city_slug=city_slug,  # Use dynamic city_slug
                    store_slug=slug,  # Pass the correct store slug
                    get_job_url=get_job_url
                )
                # Create directory structure: job-slug/index.html
                job_dir = os.path.join(store_dir, job_slug)
                os.makedirs(job_dir, exist_ok=True)
                job_file = os.path.join(job_dir, "index.html")
                write(job_file, job_html)
    
    print(f"   ✅ Built {len(enriched_careers_list)} career listings across {len(careers_by_store)} stores")
    for store_id, careers in careers_by_store.items():
        store_name = next((s.get("store_display_name", s.get("Store_ID")) for s in active_stores if s.get("Store_ID") == store_id), store_id)
        print(f"      • {store_name}: {len(careers)} openings")


def merge_seo_with_store_data(page_seo_config, store_details):
    """
    Merge SEO configuration with store data based on Store Merge Rule.
    Supports new page_id format (display-name slug, e.g. jp_nagar_5th_phase)
    as well as legacy formats (n78, Store_N78).
    """
    merged_data = {}

    for page_config in page_seo_config:
        url_slug = page_config.get('url_slug', '')
        page_type = page_config.get('page_type', '')

        # Apply Store Merge Rule
        if page_type == 'store':
            page_id = page_config.get('page_id', '').strip().lower()
            store_match = None

            for store in store_details:
                store_id = store.get('Store_ID', '')
                store_short = store.get('store_id_short', store.get('store_short_id', ''))
                display_name = store.get('store_display_name', '')
                # New format: display name slugified with underscores (jp_nagar_5th_phase)
                display_slug = display_name.lower().replace(' ', '_').replace('-', '_')

                if (page_id == store_id.lower() or
                        page_id == store_short.lower() or
                        page_id == display_slug):
                    store_match = store
                    break

            if store_match:
                # Store-specific SEO priority
                merged_data[url_slug] = {
                    **page_config,
                    **store_match,
                    # Override with store-specific data
                    'seo_title': store_match.get('seo_title') or page_config.get('seo_title'),
                    'meta_description': store_match.get('meta_description') or page_config.get('meta_description'),
                    'h1_heading': store_match.get('h1_heading') or page_config.get('h1_heading'),
                    'about_store_text': store_match.get('about_store_text') or page_config.get('about_store_text'),
                    'hero_tagline': store_match.get('hero_tagline') or page_config.get('hero_tagline'),
                    'local_neighborhood': store_match.get('local_neighborhood'),
                    'nearby_landmarks': store_match.get('nearby_landmarks'),
                    'whatsapp_msg': store_match.get('whatsapp_msg'),
                    'schema_latitude': store_match.get('schema_latitude'),
                    'schema_longitude': store_match.get('schema_longitude')
                }
            else:
                print(f"   ⚠️  No store match for page_id='{page_id}' (url_slug={url_slug})")
                merged_data[url_slug] = page_config
        else:
            merged_data[url_slug] = page_config

    return merged_data


def copy_images_to_output():
    """Copy images directory to output, with explicit favicon handling."""
    images_src = os.path.join(PROJECT_ROOT, "images")
    images_dst = os.path.join(OUTPUT_DIR, "images")

    if os.path.exists(images_src):
        if os.path.exists(images_dst):
            shutil.rmtree(images_dst)
        shutil.copytree(images_src, images_dst)
        print(f"   ✅ Copied images to output")
    else:
        print(f"   ⚠️  Images directory not found: {images_src}")

    # ── Favicon: ensure /images/favicon/ is present and copy root fallback ──
    favicon_src_dir = os.path.join(PROJECT_ROOT, "images", "favicon")
    favicon_dst_dir = os.path.join(OUTPUT_DIR, "images", "favicon")
    favicon_ico_src = os.path.join(favicon_src_dir, "favicon.ico")
    favicon_ico_root = os.path.join(OUTPUT_DIR, "favicon.ico")

    if os.path.exists(favicon_src_dir):
        # Ensure destination folder exists (already copied above, but guard anyway)
        os.makedirs(favicon_dst_dir, exist_ok=True)

        # Copy favicon.ico to site root for SEO / Google Search compatibility
        if os.path.exists(favicon_ico_src):
            shutil.copy2(favicon_ico_src, favicon_ico_root)
        else:
            print(f"   ⚠️  favicon.ico not found at {favicon_ico_src}")

        # Validation: confirm expected assets are in place
        expected = ["favicon.ico", "apple-touch-icon.png", "favicon-32x32.png", "favicon-16x16.png"]
        missing = [f for f in expected if not os.path.exists(os.path.join(favicon_dst_dir, f))]
        if missing:
            print(f"   ⚠️  Missing favicon assets in output: {missing}")
        else:
            print(f"   ✅ Favicon assets confirmed in out/images/favicon/ ({len(expected)} files)")

        if os.path.exists(favicon_ico_root):
            print(f"   ✅ Root favicon.ico confirmed at out/favicon.ico")
        else:
            print(f"   ⚠️  Root favicon.ico missing from out/")
    else:
        print(f"   ⚠️  Favicon source directory not found: {favicon_src_dir}")

def copy_campaigns_to_output():
    """Copy campaigns directory to output"""
    campaigns_src = os.path.join(PROJECT_ROOT, "campaigns")
    campaigns_dst = os.path.join(OUTPUT_DIR, "campaigns")
    
    if os.path.exists(campaigns_src):
        if os.path.exists(campaigns_dst):
            shutil.rmtree(campaigns_dst)
        shutil.copytree(campaigns_src, campaigns_dst)
        print(f"   ✅ Copied campaigns to output")
    else:
        print(f"   ⚠️  Campaigns directory not found: {campaigns_src}")

def generate_sitemap(active_stores, env):
    """Generate sitemap.xml"""
    sitemap_path = os.path.join(OUTPUT_DIR, "sitemap.xml")
    
    # Base URLs
    urls = [WEBSITE_BASE_URL]
    
    # Add store URLs
    for store in active_stores:
        store_slug = slugify(get_field(store, "store_display_name", "") or get_field(store, "store_id_short", ""))
        if store_slug:
            urls.append(f"{WEBSITE_BASE_URL}/stores/bangalore/{store_slug}/")
    
    # Add store-specific offers URLs (NEW)
    for store in active_stores:
        store_slug = slugify(get_field(store, "store_display_name", "") or get_field(store, "store_id_short", ""))
        if store_slug:
            urls.append(f"{WEBSITE_BASE_URL}/stores/bangalore/{store_slug}/offers/")
    
    # Add other page URLs
    other_pages = ["services", "contact", "offers", "about", "cancellation-policy", "booking-policy"]
    for page in other_pages:
        urls.append(f"{WEBSITE_BASE_URL}/{page}/")
    
    # Generate sitemap XML
    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for url in urls:
        sitemap_xml += f'  <url>\n    <loc>{url}</loc>\n  </url>\n'
    
    sitemap_xml += '</urlset>'
    
    with open(sitemap_path, 'w', encoding='utf-8') as f:
        f.write(sitemap_xml)
    
    print(f"   ✅ Generated sitemap.xml with {len(urls)} URLs")

def get_review_response_limit():
    """Get the number of reviews to respond to from global settings."""
    try:
        global_settings = load_json_data("aris_global_settings.json")
        for setting in global_settings:
            section = get_field(setting, "section", "")
            key = get_field(setting, "key", "")
            if section == "review_handling" and key == "no_of_reviews_to_respond_at_time":
                value = get_field(setting, "value", "2")
                try:
                    return int(value)
                except ValueError:
                    return 2
    except Exception:
        pass
    return 2  # Default fallback

def generate_review_response(customer_name, rating, review_date, review_comment):
    """Generate personalized response based on rating and review content."""
    try:
        rating = int(float(rating))
    except (ValueError, TypeError):
        rating = 5

    responses = {
        5: f"Thank you so much {customer_name}! We're thrilled you had a 5-star experience. Your kind words mean the world to our team. Looking forward to serving you again soon!",
        4: f"Thank you {customer_name} for the 4-star rating! We're glad you had a great experience. Your feedback helps us keep improving. Hope to see you again soon!",
        3: f"Thank you {customer_name} for your feedback. We'd love to make your next visit a 5-star one — please reach out to us with any suggestions!",
        2: f"Thank you {customer_name} for sharing your experience. We're sorry it didn't fully meet expectations. Please contact our store manager so we can make things right.",
        1: f"Dear {customer_name}, we're truly sorry about your experience. Please contact our manager directly — we'd like to resolve this personally and make it right.",
    }

    response = responses.get(rating, responses[4])

    review_lower = (review_comment or "").lower()
    if "slow" in review_lower or "wait" in review_lower:
        response = response.replace("experience", "visit")
    elif "rude" in review_lower or "unprofessional" in review_lower:
        response = response.replace("great", "positive")
    elif "clean" in review_lower or "hygienic" in review_lower:
        response = response.replace("great", "clean and welcoming")

    return response


def auto_respond_to_reviews(reviews_data, active_stores):
    """Automatically respond to latest unanswered reviews PER STORE."""
    from datetime import datetime

    # Get response limit from global settings (default to 2)
    response_limit = get_review_response_limit()
    print(f"   [Review Auto-Responder] Using response limit: {response_limit} reviews per store")
    
    total_responded = 0
    reviews_by_store = defaultdict(list)

    for review in reviews_data:
        sid = get_field(review, "store_id", "").strip()
        if sid:
            reviews_by_store[sid].append(review)

    for store in active_stores:
        store_id = get_field(store, "Store_ID", "")
        store_reviews = reviews_by_store.get(store_id, [])
        store_name = get_field(store, "store_display_name", store_id)

        # Sort newest first
        try:
            store_reviews.sort(
                key=lambda r: datetime.strptime(
                    get_field(r, "date_posted", "01-Jan-2020"), "%d-%b-%Y"
                ),
                reverse=True
            )
        except Exception:
            pass

        responded_this_store = 0

        for review in store_reviews:
            if responded_this_store >= response_limit:
                break

            existing = (get_field(review, "response", "") or "").strip()
            if existing:
                continue

            customer_name  = get_field(review, "Customer_Name", "Valued Customer")
            rating         = get_field(review, "Stars", "5")
            review_date    = get_field(review, "date_posted", "")
            review_comment = get_field(review, "Review_Comments", "")

            response_text = generate_review_response(
                customer_name, rating, review_date, review_comment
            )

            review["response"]      = response_text
            review["response_date"] = datetime.now().strftime("%d-%b-%Y")
            responded_this_store   += 1
            total_responded        += 1

            print(
                f"   [Review Auto-Responder] {store_name} → "
                f"{customer_name} ({rating}★) {review_date}"
            )

    if total_responded > 0:
        try:
            reviews_path = os.path.join(BUILD_DIR, "data", "reviews.json")
            with open(reviews_path, "w", encoding="utf-8") as f:
                json.dump(reviews_data, f, indent=2, ensure_ascii=False)
            print(
                f"   [Review Auto-Responder] Done — "
                f"{total_responded} responses across {len(active_stores)} stores"
            )
        except Exception as e:
            print(f"   [Review Auto-Responder] Error saving: {e}")




def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Naturals Salon Static Site Builder')
    parser.add_argument('--refresh', nargs='*', help='Force refresh specific data from Google Sheets (e.g., stores, services, page_seo_config)')
    parser.add_argument('--refresh-all', action='store_true', help='Force refresh all data from Google Sheets')
    args = parser.parse_args()
    
    print("Naturals Build — loading data from Node.js cache...")
    
    # Handle force refresh options
    if args.refresh_all:
        print("🔄 Force refreshing all data from Google Sheets...")
        data_types = ['stores.json', 'services.json', 'campaigns.json', 'stylists.json', 
                     'reviews.json', 'trainings.json', 'careers.json']
        for data_type in data_types:
            force_refresh_from_google_sheets(data_type)
    elif args.refresh:
        print(f"🔄 Force refreshing specific data from Google Sheets: {args.refresh}")
        for data_type in args.refresh:
            if not data_type.endswith('.json'):
                data_type += '.json'
            force_refresh_from_google_sheets(data_type)
    
    try:
        # Load from JSON files exported by Node.js MasterLoader
        # This uses the existing cache and Google Sheets service
        store_details = load_json_data("stores.json")
        services_data = load_json_data("services.json")
        campaigns_data = load_json_data("campaigns.json")
        stylists_data = load_json_data("stylists.json")
        reviews_data = load_json_data("reviews.json")
        trainings_data = load_json_data("trainings.json")
        careers_data = load_json_data("careers.json")
        
        # Load global settings for homepage configuration
        global_settings = load_json_data("aris_global_settings.json")
        
        # Get number of featured offers to show from settings
        featured_offers_count = 3  # default fallback
        service_categories_count = 6  # default fallback
        
        if global_settings and isinstance(global_settings, list):
            # Find the homepage settings in the list
            for item in global_settings:
                if item.get("section brand brand brand brand brand brand brand response_style response_style") == "settings_page_home":
                    key = item.get("key name short_name tagline city country timezone currency sign_off tone")
                    value = item.get("value Naturals Unisex Salon Naturals India's No.1 Unisex Salon Bangalore India IST INR With love, Team Naturals {store.area} warm, professional, personal")
                    
                    if key == "no_of_featured_offers_to_show":
                        featured_offers_count = int(value or "3")
                    elif key == "no_of_service_categories_to_show":
                        service_categories_count = int(value or "6")
        
        # Load SEO configuration data with cache support
        try:
            # Load page_seo_config from JSON file (exported from Google Sheets)
            page_seo_config = load_json_data("page_seo_config.json")
            print(f"✅ Loaded {len(page_seo_config)} page SEO configurations from Google Sheets")
            # Build url_slug → config lookup table for O(1) lookups during build
            seo_lookup = build_seo_lookup(page_seo_config)
            print(f"✅ SEO lookup table built with {len(seo_lookup)} entries: {list(seo_lookup.keys())[:5]}")
        except Exception as e:
            print(f"❌ Error loading SEO config: {e}")
            page_seo_config = []
            seo_lookup = {}
    except Exception as e:
        print(f"ERROR loading data: {e}")
        print(f"\nTo export data, run: npm run export:build-data")
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════════
    # STEP 1: Filter ACTIVE stores first
    # ═══════════════════════════════════════════════════════════════
    print("\n📋 Filtering active stores...")
    
    # Get all stores with active_status = "Yes" (case-insensitive)
    active_map = {
        get_field(s, "Store_ID"): s 
        for s in store_details 
        if is_yes(get_field(s, "active_status", "yes")) and get_field(s, "Store_ID")
    }
    
    if not active_map:
        print("❌ No active stores found!")
        sys.exit(1)
    
    active_stores = list(active_map.values())
    active_store_ids = set(active_map.keys())
    
    print(f"   ✅ Found {len(active_stores)} active stores")
    for s in active_stores:
        print(f"      • {get_field(s, 'store_display_name', get_field(s, 'Store_ID'))}")
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 2: Process offers and campaigns
    # ═══════════════════════════════════════════════════════════════
    print("\n📋 Processing offers and campaigns...")
    
    # Process offers directly from campaigns data
    processed_offers = []
    for campaign in campaigns_data:
        if campaign.get('content_type') == 'offer' and campaign.get('approval_status') == 'Yes':
            # Check if offer is active
            if campaign.get('is_expired') == 'No' and campaign.get('post_website') == 'Yes':
                # Map campaign to offer format
                offer = dict(campaign)
                
                # Add Store_ID field based on targeting
                store_ids = []
                if campaign.get('target_all_stores') == 'Yes':
                    # For target_all_stores, create one offer that can be used everywhere
                    offer = dict(campaign)
                    offer['Store_ID'] = 'ALL_STORES'  # Special marker for all stores
                    offer['Priority'] = '1' if campaign.get('campaign_priority') == 'high' else '2'
                    offer['Active'] = 'Yes'
                    offer['target_all_stores'] = 'Yes'  # Preserve the original field
                    
                    processed_offers.append(offer)
                else:
                    # Check individual store targeting
                    store_mapping = {
                        'target_store_n78': 'Store_N78',
                        'target_store_n77': 'Store_N77', 
                        'target_store_n36': 'Store_N36',
                        'target_store_n05': 'Store_N05',
                        'target_store_n43': 'Store_N43'
                    }
                    for field, store_id in store_mapping.items():
                        if campaign.get(field) == 'Yes':
                            store_ids.append(store_id)
                    
                    # Create separate offers for each targeted store
                    if store_ids:
                        for store_id in store_ids:
                            offer = dict(campaign)
                            offer['Store_ID'] = store_id
                            offer['Priority'] = '1' if campaign.get('campaign_priority') == 'high' else '2'
                            offer['Active'] = 'Yes'
                            
                            processed_offers.append(offer)
    
    # Process campaigns with campaign_engine.py
    all_campaigns = process_campaigns(campaigns_data, active_stores)
    
    # Filter offers for active stores only (include ALL_STORES offers)
    offer_campaigns = [
        offer for offer in processed_offers 
        if get_field(offer, "Store_ID") in active_store_ids or get_field(offer, "Store_ID") == 'ALL_STORES'
    ]
    
    # Group offers by store for easy lookup
    offers_by_store = defaultdict(list)
    
    # Add store-specific offers
    for offer in offer_campaigns:
        # Check if this is an all-stores offer
        if get_field(offer, "target_all_stores") == "Yes":
            # Add to all stores
            for store_id in active_store_ids:
                offers_by_store[store_id].append(offer)
        else:
            # Check individual store targeting fields and add to each matching store
            if get_field(offer, "target_store_n78", "") == "Yes":
                offers_by_store["Store_N78"].append(offer)
            if get_field(offer, "target_store_n77", "") == "Yes":
                offers_by_store["Store_N77"].append(offer)
            if get_field(offer, "target_store_n36", "") == "Yes":
                offers_by_store["Store_N36"].append(offer)
            if get_field(offer, "target_store_n05", "") == "Yes":
                offers_by_store["Store_N05"].append(offer)
            if get_field(offer, "target_store_n43", "") == "Yes":
                offers_by_store["Store_N43"].append(offer)
    
    # Get featured offers (priority 1, active, limited to configured number)
    featured_offers = get_featured_offers(offer_campaigns, active_stores, n=featured_offers_count)
    
    print(f"   ✅ Processed {len(offer_campaigns)} offers across {len(offers_by_store)} stores")
    print(f"   ✅ Found {len(featured_offers)} featured offers")
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 3: Process reviews
    # ═══════════════════════════════════════════════════════════════
    print("\n📋 Processing reviews...")
    
    # Group reviews by store
    reviews_by_store = defaultdict(list)
    for review in reviews_data:
        store_id = get_field(review, "store_id", "").strip()
        if store_id and store_id in active_store_ids:
            reviews_by_store[store_id].append(review)
    
    # Get featured reviews (priority 1)
    featured_reviews = []
    for store_id, store_reviews in reviews_by_store.items():
        priority_reviews = [
            r for r in store_reviews 
            if get_field(r, "priority", "") == "1"
        ]
        if priority_reviews:
            featured_reviews.extend(priority_reviews[:2])  # Max 2 per store
    
    print(f"   ✅ Processed {len(reviews_data)} reviews across {len(reviews_by_store)} stores")
    print(f"   ✅ Found {len(featured_reviews)} featured reviews")
    
    # Auto-respond to latest unanswered Google reviews (respond to 2 at a time)
    auto_respond_to_reviews(reviews_data, active_stores)
    """Automatically respond to latest 2 unanswered reviews PER STORE"""
    from datetime import datetime

    total_responded = 0
    reviews_by_store = defaultdict(list)
    
    for review in reviews_data:
        sid = get_field(review, "store_id", "").strip()
        if sid:
            reviews_by_store[sid].append(review)

    for store in active_stores:
        store_id = get_field(store, "Store_ID", "")
        store_reviews = reviews_by_store.get(store_id, [])
        store_name = get_field(store, "store_display_name", store_id)

        # Sort newest first
        try:
            store_reviews.sort(
                key=lambda r: datetime.strptime(
                    get_field(r, "date_posted", "01-Jan-2020"), "%d-%b-%Y"
                ),
                reverse=True
            )
        except Exception:
            pass

        responded_this_store = 0

        for review in store_reviews:
            if responded_this_store >= 2:
                break

            # Only check: is it unanswered?
            existing = (get_field(review, "response", "") or "").strip()
            if existing:
                continue

            customer_name  = get_field(review, "Customer_Name", "Valued Customer")
            rating         = get_field(review, "Stars", "5")
            review_date    = get_field(review, "date_posted", "")
            review_comment = get_field(review, "Review_Comments", "")

            response_text = generate_review_response(
                customer_name, rating, review_date, review_comment
            )

            review["response"]      = response_text
            review["response_date"] = datetime.now().strftime("%d-%b-%Y")
            responded_this_store   += 1
            total_responded        += 1

            print(
                f"   [Review Auto-Responder] {store_name} → "
                f"{customer_name} ({rating}★) {review_date}"
            )

    if total_responded > 0:
        try:
            reviews_path = os.path.join(BUILD_DIR, "data", "reviews.json")
            with open(reviews_path, "w", encoding="utf-8") as f:
                json.dump(reviews_data, f, indent=2, ensure_ascii=False)
            print(
                f"   [Review Auto-Responder] Done — "
                f"{total_responded} responses across {len(active_stores)} stores"
            )
        except Exception as e:
            print(f"   [Review Auto-Responder] Error saving: {e}")

    
    def should_auto_respond(review_date, last_response_date=None):
        """Check if review should get auto-response based on timing"""
        try:
            review_dt = datetime.strptime(review_date, '%d-%b-%Y')
            if last_response_date:
                last_response_dt = datetime.strptime(last_response_date, '%d-%b-%Y')
                # Only respond if review is newer than last response by at least 1 day
                return review_dt > last_response_dt + timedelta(days=1)
            else:
                # No previous responses, respond to reviews from last 7 days
                cutoff_date = datetime.now() - timedelta(days=7)
                return review_dt >= cutoff_date
        except:
            # If date parsing fails, don't respond (avoid errors)
            return False
    
    # ═══════════════════════════════════════════════════════════════
    print("\n Processing stylists...")
    
    # Filter stylists for active stores only (using store_id_short)
    active_store_shorts = [get_field(s, "store_id_short", "") for s in active_stores]
    filtered_stylists = [
        stylist for stylist in stylists_data
        if get_field(stylist, "store_id_short") in active_store_shorts
    ]
    
    print(f"   ✅ Found {len(filtered_stylists)} stylists for active stores")
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 5: Calculate minimum prices
    # ═══════════════════════════════════════════════════════════════
    print("\n📋 Calculating minimum prices...")
    
    min_prices = {}
    for store_id in active_store_ids:
        store_services = [
            s for s in services_data 
            if is_yes(get_field(s, store_id, ""))
        ]
        if store_services:
            prices = [
                int(get_field(s, "Member_Cost", "0")) 
                for s in store_services 
                if get_field(s, "Member_Cost", "").isdigit()
            ]
            min_prices[store_id] = min(prices) if prices else 0
        else:
            min_prices[store_id] = 0
    
    print(f"   ✅ Calculated minimum prices for {len(min_prices)} stores")
    
    # Filter services for active stores only (for store pages)
    filtered_services = [
        s for s in services_data
        if any(is_yes(get_field(s, store_id, "")) for store_id in active_store_ids)
    ]
    
    print(f"   ✅ Found {len(filtered_services)} services for active stores")
    
    # Filter trainings for active stores only
    filtered_trainings = [
        t for t in trainings_data
        if (t.get('target_role') == 'All' and t.get('is_active') == 'Yes') or
           any(is_yes(get_field(t, store_id, "")) for store_id in active_store_ids)
    ]
    
    print(f"   ✅ Found {len(filtered_trainings)} trainings for active stores")
    
    # ═══════════════════════════════════════════════════════════════
    # STEP 6: Setup Jinja2 environment
    # ═══════════════════════════════════════════════════════════════
    print("\n📋 Setting up template environment...")
    
    env = Environment(
        loader=FileSystemLoader(os.path.join(BUILD_DIR, "templates")),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True
    )
    
    # Add utility functions to templates
    env.globals['is_yes'] = is_yes
    env.globals['get_field'] = get_field
    env.globals['slugify'] = slugify
    
    # Import all macros from macros.j2
    try:
        with open(os.path.join(BUILD_DIR, "templates", "macros.j2"), 'r') as f:
            macros_content = f.read()
            env.globals['macros'] = macros_content
    except FileNotFoundError:
        print("   ⚠️  macros.j2 not found, some features may not work")
    
    # Add global city slug for all templates
    global_city_slug = DEFAULT_CITY_SLUG
    if active_stores and len(active_stores) > 0:
        first_store = active_stores[0]
        address_city = get_field(first_store, "address_city", "")
        if address_city:
            global_city_slug = standardize_city_slug(address_city)
    env.globals["city_slug"] = global_city_slug

    # Merge SEO data with store data
    merged_seo_data = merge_seo_with_store_data(page_seo_config, store_details)
    
    print("\n🔨 Building pages...")
    # Load services data for home page
    all_services = load_json_data("services.json")
    build_index(active_stores, featured_offers, min_prices, featured_reviews, env, services=all_services, service_categories_count=service_categories_count, page_seo_config=page_seo_config)
    build_services(active_stores, env, active_store_ids, page_seo_config)

    # Add Hero_Number to each store (auto-generated)
    for i, store in enumerate(active_stores, 1):
        store["Hero_Number"] = i
        build_store(store, filtered_services, offer_campaigns, filtered_stylists, reviews_by_store, active_stores, env, merged_seo_data)

    build_contact(active_stores, env, page_seo_config)
    build_offers_page(active_stores, offers_by_store, env, page_seo_config)
    build_store_offers_pages(active_stores, offers_by_store, env, page_seo_config)
    build_cancellation_policy(active_stores, env, page_seo_config)
    build_booking_policy(active_stores, env, page_seo_config)
    build_about(active_stores, env, page_seo_config)
    build_intranet(active_stores, env, filtered_trainings)
    build_careers(active_stores, careers_data, env, page_seo_config)
    
    # Copy folders to output directory
    copy_images_to_output()
    copy_campaigns_to_output()
    
    # Generate sitemap
    generate_sitemap(active_stores, env)
    
    print("\n🎉 Build completed successfully!")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print(f"🏪 Built {len(active_stores)} store pages")
    print(f"🏠 Built home page with SEO data")
    print(f"🔍 Built sitemap.xml")


if __name__ == "__main__":
    main()
