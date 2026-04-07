#!/usr/bin/env python3

import os
import json
import shutil
import requests
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load .env file if it exists
def load_env():
    """Load environment variables from .env file"""
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value

# Load .env at module import
load_env()

# Import social publisher
try:
    from social_publisher import SocialPublisher
    SOCIAL_PUBLISHER_AVAILABLE = True
except ImportError:
    SOCIAL_PUBLISHER_AVAILABLE = False
    print("⚠️  Social publisher not available")

# ============================== 
# CONFIG
# ==============================

SERVICE_ACCOUNT_FILE = "service_account.json"
SPREADSHEET_ID = os.getenv("SHEET_ID", "1wy0_josh4L-C0GXWNnRG8QEO9F8km5SMrDefemChFUo")
SHEET_NAME = "campaigns"

DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT_FOLDER_ID", "YOUR_DRIVE_FOLDER_ID")  # Parent folder

def get_staff_uploads_path(campaign_type="offer"):
    """
    Get the correct staff uploads path based on campaign type.
    """
    return f"campaigns/{campaign_type}/01_staff_uploads"

STAFF_UPLOADS_PATH = get_staff_uploads_path()  # Path to staff uploads folder

OFFERS_BASE = "campaigns/offer"

DOWNLOADED_DIR = os.path.join(OFFERS_BASE, "01_downloaded")
PROCESSING_DIR = os.path.join(OFFERS_BASE, "02_processing")
PUBLISHED_DIR = os.path.join(OFFERS_BASE, "03_published")
ARCHIVE_DIR = os.path.join(OFFERS_BASE, "04_archived")

# Facebook and Instagram folders at root level for backward compatibility
FACEBOOK_DIR = os.path.join(OFFERS_BASE, "facebook")
INSTAGRAM_DIR = os.path.join(OFFERS_BASE, "instagram")

# ==============================
# CREATE FOLDERS
# ==============================

for d in [
    DOWNLOADED_DIR,
    PROCESSING_DIR,
    PUBLISHED_DIR,
    ARCHIVE_DIR,
    FACEBOOK_DIR,
    INSTAGRAM_DIR
]:
    os.makedirs(d, exist_ok=True)

# ==============================
# SHEET VALIDATION
# ==============================

REQUIRED_COLUMNS = [
    "content_type",
    "content_title",
    "is_expired"
]

# ==============================
# BOOLEAN PARSER
# ==============================

TRUE_VALUES = {"yes","y","true","t","1"}
FALSE_VALUES = {"no","n","false","f","0",""}

def parse_bool(value):
    """Parse boolean value case-insensitively"""
    if value is None:
        return False

    v = str(value).strip().lower()

    if v in TRUE_VALUES:
        return True

    if v in FALSE_VALUES:
        return False

    # Default to False for unknown values
    return False

def is_image_available(value):
    """Check if image is marked as available (Yes/yes/Y/True/true)"""
    if value is None:
        return False
    
    v = str(value).strip().lower()
    return v in {"yes", "y", "true", "t", "1"}

# ==============================
# CHECK IF OFFER IS VALID
# ==============================

def is_offer_valid(offer):
    """
    Check if offer should be displayed:
    - content_type must be 'offer'
    - approval_status must be 'Yes'
    - is_expired must not be 'Yes'
    - end_date must not be in the past
    """
    # Must be content_type = offer
    if s(offer, "content_type").strip().lower() != "offer":
        return False

    # Must be approved
    if not parse_bool(s(offer, "approval_status")):
        return False

    # Check if explicitly marked as expired
    if parse_bool(s(offer, "is_expired")):
        return False
    
    # Check end_date
    end_date = s(offer, "end_date")
    if end_date:
        try:
            from dateutil import parser
            valid_date = parser.parse(end_date, dayfirst=True)
            today = datetime.now()
            if valid_date.date() < today.date():
                return False
        except:
            pass
    
    return True

def s(row,key):
    """Case-insensitive string access"""
    # Try exact match first
    if key in row:
        return str(row[key]).strip()
    
    # Try case-insensitive match
    for k in row.keys():
        if k.lower() == key.lower():
            return str(row[k]).strip()
    
    # Return empty string if not found
    return ""

# ==============================
# GOOGLE AUTH
# ==============================

# Global variables for caching
drive_service = None
sheets_service = None
_drive_available = None

def _load_credentials():
    """
    Load Google credentials from env var or file.
    Supports both service account JSON and OAuth2 client JSON (with refresh token).
    Returns (credentials_object, scopes) or raises on failure.
    """
    SCOPES = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets.readonly"
    ]

    raw = os.getenv("GOOGLE_OAUTH_CREDENTIALS")
    if raw:
        info = json.loads(raw)
    elif os.path.exists("service-account.json"):
        with open("service-account.json", "r") as f:
            info = json.load(f)
    else:
        raise FileNotFoundError("No credentials found (GOOGLE_OAUTH_CREDENTIALS env var or service-account.json)")

    # Service account
    if info.get("type") == "service_account" and info.get("client_email"):
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)

    # OAuth2 client credentials
    client_creds = info.get("installed") or info.get("web")
    if client_creds:
        from google.oauth2.credentials import Credentials
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
        if not refresh_token:
            raise ValueError(
                "GOOGLE_OAUTH_CREDENTIALS contains OAuth client credentials "
                "but GOOGLE_REFRESH_TOKEN is not set"
            )
        return Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_creds["client_id"],
            client_secret=client_creds["client_secret"],
            scopes=SCOPES,
        )

    raise ValueError("Unrecognised credential format in GOOGLE_OAUTH_CREDENTIALS")


def is_drive_available():
    """Check if Google Drive is available - cached result"""
    global _drive_available
    if _drive_available is None:
        try:
            creds = _load_credentials()
            service = build('drive', 'v3', credentials=creds)
            service.about().get(fields="user").execute()
            _drive_available = True
        except Exception as e:
            print(f"⚠️ Google Drive not available: {e}")
            _drive_available = False
    return _drive_available


def get_drive_service():
    """Get Google Drive service with proper error handling"""
    global drive_service
    if drive_service:
        return drive_service

    if not is_drive_available():
        return None

    try:
        creds = _load_credentials()
        drive_service = build("drive", "v3", credentials=creds)
        return drive_service
    except Exception as e:
        print(f"⚠️ Failed to create Drive service: {e}")
        return None


def get_sheets_service():
    """Get Google Sheets service with proper error handling"""
    global sheets_service
    if sheets_service:
        return sheets_service

    if not is_drive_available():
        return None

    try:
        creds = _load_credentials()
        sheets_service = build("sheets", "v4", credentials=creds)
        return sheets_service
    except Exception as e:
        print(f"⚠️ Failed to create Sheets service: {e}")
        return None

# ==============================
# LOG
# ==============================

def log(msg):
    print(datetime.now().strftime("%H:%M:%S"), msg)

# ==============================
# LOAD OFFERS
# ==============================

def load_offers():

    service = get_sheets_service()
    
    if not service:
        print("⚠️ Google Sheets service not available")
        return []

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_NAME
        ).execute()

        rows = result.get("values",[])

        headers = rows[0]

        offers = []

        for r in rows[1:]:

            row = {}

            for i,h in enumerate(headers):
                if i < len(r):
                    row[h] = r[i]

            offers.append(row)

        validate_columns(headers)

        return offers
        
    except Exception as e:
        print(f"⚠️ Failed to load offers: {e}")
        return []

# ==============================
# VALIDATE COLUMNS
# ==============================

def validate_columns(headers):
    """Case-insensitive column validation"""
    header_lower = [h.lower() for h in headers]
    
    for col in REQUIRED_COLUMNS:
        if col.lower() not in header_lower:
            raise ValueError(
                f"Missing required column '{col}' (case insensitive - found: {headers})"
            )

# ==============================
# BUILD LOOKUP
# ==============================

def build_offer_lookup(offers):
    """
    Build lookup for offers by media_asset_name.
    Since media_asset_name doesn't include extension, we create entries for all common extensions.
    """
    lookup = {}

    for offer in offers:
        name = s(offer, "media_asset_name").lower()
        if not name:
            continue
        
        # Add entries for all common image extensions
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]:
            lookup[name + ext] = offer

    return lookup

# ==============================
# CHECK VALID DRIVE IMAGE
# ==============================

def is_valid_upload(filename):
    """
    Check if a file is a valid image upload.
    - Must be an image file (.jpg, .jpeg, .png, .webp, .gif)
    - Must not be already processed (_processed suffix)
    """
    name = filename.lower()

    if "_processed" in name:
        return False

    if not name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return False

    return True

# ==============================
# FIND STAFF UPLOADS FOLDER
# ==============================

def get_staff_uploads_path(campaign_type="offer"):
    """
    Get the correct staff uploads path based on campaign type.
    """
    return f"campaigns/{campaign_type}/01_staff_uploads"

def find_staff_uploads_folder(campaign_type="offer"):
    """
    Find the campaigns/{campaign_type}/01_staff_uploads folder starting from parent folder.
    Returns the folder ID or None if not found.
    """
    service = get_drive_service()
    
    if not service:
        log("⚠️ Google Drive service not available")
        return None
    
    staff_uploads_path = get_staff_uploads_path(campaign_type)
    
    try:
        # Start from parent folder
        current_folder_id = DRIVE_FOLDER_ID
        path_parts = staff_uploads_path.split('/')
        
        log(f"Looking for folder path: {staff_uploads_path}")
        log(f"Looking for folder path: {STAFF_UPLOADS_PATH}")
        log(f"Starting from parent folder: {current_folder_id}")
        
        # Navigate through each part of the path
        for folder_name in path_parts:
            log(f"  Looking for subfolder: {folder_name}")
            
            # Search for folder with this name in current folder
            query = f"'{current_folder_id}' in parents and name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            
            result = service.files().list(
                q=query,
                fields="files(id,name)"
            ).execute()
            
            files = result.get("files", [])
            
            if not files:
                log(f"  ❌ Folder '{folder_name}' not found in parent")
                return None
            
            # Use the first matching folder
            current_folder_id = files[0]["id"]
            log(f"  ✅ Found: {folder_name} (ID: {current_folder_id})")
        
        log(f"✅ Staff uploads folder found: {current_folder_id}")
        return current_folder_id
        
    except Exception as e:
        log(f"⚠️ Failed to find staff uploads folder: {e}")
        return None


# ==============================
# SCAN GOOGLE DRIVE
# ==============================

def scan_staff_uploads(campaign_type="offer"):
    """
    Scan for new images in the appropriate campaign type folder.
    Returns list of file dicts (id, name, createdTime).
    """
    service = get_drive_service()
    if not service:
        log("⚠️ Google Drive service not available")
        return []
    
    staff_uploads_path = get_staff_uploads_path(campaign_type)

    try:
        # Find the staff uploads folder
        staff_uploads_folder_id = find_staff_uploads_folder(campaign_type)
        
        if not staff_uploads_folder_id:
            log("⚠️ Could not find staff uploads folder")
            return []
        
        log(f"Scanning Drive folder: {staff_uploads_folder_id}")
        query = f"'{staff_uploads_folder_id}' in parents and trashed=false"

        result = service.files().list(
            q=query,
            fields="files(id,name,mimeType)"
        ).execute()

        files = result.get("files", [])
        log(f"Found {len(files)} files in Drive folder")

        valid = []

        for f in files:
            filename = f["name"]
            log(f"  Checking: {filename}")
            
            if is_valid_upload(filename):
                valid.append(f)
                log(f"    ✅ Valid image file")
            else:
                log(f"    ⏭️  Skipped (not valid or already processed)")

        log(f"Found {len(valid)} valid images to process")
        return valid
        
    except Exception as e:
        log(f"⚠️ Failed to scan Drive: {e}")
        import traceback
        traceback.print_exc()
        return []

# ==============================
# DOWNLOAD DRIVE FILE
# ==============================

def download_drive_file(file_id,filename):

    service = get_drive_service()
    
    if not service:
        print("⚠️ Google Drive service not available")
        return None

    try:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

        headers = {
            "Authorization": f"Bearer {service._http.credentials.token}"
        }

        r = requests.get(url,headers=headers)

        path = os.path.join(DOWNLOADED_DIR,filename)

        with open(path,"wb") as f:
            f.write(r.content)

        return path
        
    except Exception as e:
        print(f"⚠️ Failed to download {filename}: {e}")
        return None

# ==============================
# RENAME DRIVE FILE
# ==============================

def mark_drive_file_processed(file_id, filename):
    """
    Rename file in Google Drive by appending '_processed' to indicate it has been
    successfully published to the public repo.
    
    This should ONLY be called after verifying the file exists in the public repo.
    
    Example: 20260305_SummerHairSpa.jpg → 20260305_SummerHairSpa_processed.jpg
    """
    service = get_drive_service()
    
    if not service:
        log("⚠️ Google Drive service not available - cannot rename file")
        return False

    try:
        name, ext = os.path.splitext(filename)
        new_name = f"{name}_processed{ext}"

        # Ensure token is valid (important in CI runners)
        if hasattr(service, '_http') and service._http:
            creds = service._http.credentials
            if hasattr(creds, 'expired') and creds.expired:
                creds.refresh(service._http.request)

        service.files().update(
            fileId=file_id,
            body={"name": new_name}
        ).execute()

        log(f"✅ Renamed in Drive: {filename} → {new_name}")
        return True

    except Exception as e:
        log(f"⚠️ Failed to rename {filename} in Drive: {e}")
        return False

# ==============================
# GENERATE OFFER IMAGE
# ==============================

def generate_offer_image(offer):

    base = s(offer, "media_asset_name")

    website = base+".jpg"
    facebook = base+"_facebook.jpg"
    instagram = base+"_instagram.jpg"

    website_path = os.path.join(PROCESSING_DIR,website)
    facebook_path = os.path.join(FACEBOOK_DIR,facebook)
    instagram_path = os.path.join(INSTAGRAM_DIR,instagram)

    title = s(offer, "content_title")
    text = s(offer, "content_body") if s(offer, "content_body") else s(offer, "content_title")  # Fallback to title
    store = s(offer,"store_display_name") if s(offer,"store_display_name") else "Naturals Salon"  # Fallback to default

    def create_image(w,h,path):

        img = Image.new("RGB",(w,h),(255,255,255))
        draw = ImageDraw.Draw(img)

        try:
            font_big = ImageFont.truetype("DejaVuSans-Bold.ttf",int(h*0.08))
            font_text = ImageFont.truetype("DejaVuSans.ttf",int(h*0.05))
        except:
            font_big = ImageFont.load_default()
            font_text = ImageFont.load_default()

        draw.text((50,50),store,fill=(0,0,0),font=font_big)
        draw.text((50,200),title,fill=(200,0,0),font=font_big)
        draw.text((50,350),text,fill=(0,0,0),font=font_text)

        img.save(path,quality=92)

    create_image(1200,1200,website_path)
    create_image(1200,630,facebook_path)
    create_image(1080,1920,instagram_path)

    return website

# ==============================
# PUBLISH IMAGES
# ==============================

def copy_to_social_folders(filename):
    """
    COPY image from 03_published to facebook and instagram folders with appropriate suffixes.
    These are the ONLY copies - the main workflow uses MOVE operations.
    
    Example:
    - Source: campaigns/offer/03_published/20260305_SummerHairSpa.jpg
    - Facebook: campaigns/offer/facebook/20260305_SummerHairSpa_facebook.jpg
    - Instagram: campaigns/offer/instagram/20260305_SummerHairSpa_instagram.jpg
    """
    src = os.path.join(PUBLISHED_DIR, filename)
    
    if not os.path.exists(src):
        log(f"⚠️  Source file not found: {src}")
        return
    
    # Split filename and extension
    name, ext = os.path.splitext(filename)
    
    # Copy to facebook folder with _facebook suffix
    fb_filename = f"{name}_facebook{ext}"
    fb_dst = os.path.join(FACEBOOK_DIR, fb_filename)
    shutil.copy2(src, fb_dst)
    log(f"  📘 Copied to facebook: {fb_filename}")
    
    # Copy to instagram folder with _instagram suffix
    ig_filename = f"{name}_instagram{ext}"
    ig_dst = os.path.join(INSTAGRAM_DIR, ig_filename)
    shutil.copy2(src, ig_dst)
    log(f"  📷 Copied to instagram: {ig_filename}")

def publish_image(filename):
    """
    Publish image: MOVE from processing to published folder
    """
    src = os.path.join(PROCESSING_DIR,filename)
    dst = os.path.join(PUBLISHED_DIR,filename)

    if os.path.exists(src):
        # Move to published folder (not copy)
        shutil.move(src,dst)
        log(f"Published {filename}")

def publish_processed_images(files):
    """
    Publish multiple images: MOVE from processing to published folder
    Compatible with build.py import
    """
    for filename in files:
        publish_image(filename)

def copy_existing_published_images():
    """
    No-op function for backward compatibility.
    Images are now served directly from /campaigns/offer/03_published.
    """
    log("✅ Using images directly from /campaigns/offer/03_published")
    return 0

# PROCESS DRIVE IMAGES
# ==============================

def process_new_images(campaign_type="offer"):
    """
    Process new images from Google Drive:
    1. Find images in campaigns/{campaign_type}/01_staff_uploads
    2. Download to campaigns/{campaign_type}/01_downloaded
    3. MOVE to campaigns/{campaign_type}/02_processing for processing
    4. MOVE to campaigns/{campaign_type}/03_published
    5. COPY to facebook/ and instagram/ folders with name appending
    6. Mark as processed in Drive (only after successful publish)
    
    Returns list of processed filenames
    """
    offers = load_offers()
    lookup = build_offer_lookup(offers)

    files = scan_staff_uploads()
    
    processed_images = []

    for f in files:
        filename = f["name"]
        file_id = f["id"]

        offer = lookup.get(filename.lower())

        if not offer:
            log(f"No offer match for {filename}")
            continue
        
        # Check if offer is valid (not expired, within Valid_Till date)
        if not is_offer_valid(offer):
            log(f"Skipping {filename} - offer expired or past Valid_Till date")
            continue
        
        # Check if image is marked as available
        if not is_image_available(s(offer, "Image_Available")):
            log(f"Skipping {filename} - Image_Available not marked as Yes")
            continue

        log(f"Downloading {filename}")

        # Step 1: Download to 01_downloaded
        local = download_drive_file(file_id, filename)
        
        if not local:
            continue

        # Step 2: MOVE to 02_processing (not copy)
        proc = os.path.join(PROCESSING_DIR, filename)
        shutil.move(local, proc)
        log(f"Moved to processing: {filename}")

        # Step 3: MOVE to 03_published (not copy)
        dst = os.path.join(PUBLISHED_DIR, filename)
        shutil.move(proc, dst)
        log(f"Published {filename}")
        
        # Step 4: COPY to facebook and instagram folders with name appending
        copy_to_social_folders(filename)

        # Step 5: Mark as processed in Drive (only after successful publish)
        mark_drive_file_processed(file_id, filename)
        
        processed_images.append(filename)
    
    return processed_images

# ==============================
# GENERATE MISSING IMAGES
# ==============================

def generate_missing_images(offers, processed_drive_images):
    """
    Generate images for offers where:
    - Image_Available = No/no/false/n/0 (case-insensitive)
    - Offer is valid (not expired, within Valid_Till date)
    - No Drive image exists
    - Image name follows the naming in Image_Name field
    
    Generated images are saved to:
    - /campaigns/offer/03_published
    - /campaigns/offer/facebook
    - /campaigns/offer/instagram
    """
    
    # Get Drive uploads currently present
    drive_files = scan_staff_uploads()
    drive_names = set()
    
    for f in drive_files:
        base = os.path.splitext(f["name"])[0]
        drive_names.add(base.lower())
    
    # Also track images already processed in this run
    processed_offers = set()
    for filename in processed_drive_images:
        base = os.path.splitext(filename)[0]
        processed_offers.add(base.lower())
    
    for offer in offers:
        
        # Check if offer is valid
        if not is_offer_valid(offer):
            continue
        
        # Check has_media and media_asset_name fields
        image_name = s(offer, "media_asset_name")
        has_media = parse_bool(s(offer, "has_media"))
        
        # If has_media = Yes, image should already exist — skip generation
        if has_media:
            log(f"Skipping {image_name} - image marked as available (has_media=Yes)")
            continue

        # Skip generation if Drive image exists OR already processed
        if image_name.lower() in drive_names or image_name.lower() in processed_offers:
            log(f"Skipping {image_name} - image exists in Drive or already processed")
            continue
        
        img = image_name + ".jpg"
        
        path = os.path.join(PUBLISHED_DIR, img)
        
        # Skip if already exists in published folder
        if os.path.exists(path):
            continue
        
        log(f"Generating image {img}")
        
        # Generate the image (saves to PROCESSING_DIR)
        gen = generate_offer_image(offer)
        
        # Publish to 03_published and public repo
        publish_image(gen)
        
        # Copy to facebook and instagram folders
        copy_to_social_folders(gen)

# ==============================
# SOCIAL MEDIA PUBLISHING
# ==============================

def publish_to_social_media(offers, processed_images, active_stores):
    """
    Publish new offers to Facebook and Instagram
    
    Args:
        offers: List of all offers
        processed_images: List of newly processed image filenames
        active_stores: List of active stores with social media IDs
    """
    if not SOCIAL_PUBLISHER_AVAILABLE:
        log("⏭️  Social publisher not available, skipping social media posting")
        return
    
    # Check if social publishing is enabled
    enable_social = os.getenv("ENABLE_SOCIAL_PUBLISHING", "false").lower() == "true"
    if not enable_social:
        log("⏭️  Social publishing disabled (set ENABLE_SOCIAL_PUBLISHING=true to enable)")
        return
    
    # Initialize publisher
    publisher = SocialPublisher()
    
    # Build offer lookup
    offer_lookup = {}
    for offer in offers:
        image_name = s(offer, "media_asset_name")
        if image_name:
            offer_lookup[image_name.lower()] = offer
    
    # Build store lookup by Store_ID
    store_lookup = {}
    for store in active_stores:
        store_id = s(store, "Store_ID")
        if store_id:
            store_lookup[store_id] = store
    
    # Publish each new offer
    for filename in processed_images:
        base_name = os.path.splitext(filename)[0].lower()
        
        # Find matching offer
        offer = offer_lookup.get(base_name)
        if not offer:
            log(f"⚠️  No offer found for {filename}")
            continue
        
        # Check if offer should be published to social media
        publish_social = s(offer, "Publish_Social")
        if not is_image_available(publish_social):
            log(f"⏭️  Social publishing disabled for {filename}")
            continue
        
        # Determine which stores this offer applies to
        # Check Store_All or specific store fields
        store_all = s(offer, "Store_All").lower() in {"yes", "y", "true", "t", "1"}
        
        target_stores = []
        if store_all:
            # Offer applies to all stores
            target_stores = active_stores
        else:
            # Check specific store fields
            for store in active_stores:
                store_id = s(store, "Store_ID")
                if s(offer, store_id).lower() in {"yes", "y", "true", "t", "1"}:
                    target_stores.append(store)
        
        if not target_stores:
            log(f"⚠️  No target stores for {filename}")
            continue
        
        # Publish to each target store's social media
        for store in target_stores:
            store_id = s(store, "Store_ID")
            store_name = s(store, "store_display_name") or "Naturals Salon"
            
            # Build store data dict with social media IDs
            store_data = {
                "store_display_name": store_name,
                "facebook_page_id": s(store, "facebook_page_id"),
                "instagram_business_account_id": s(store, "instagram_business_account_id"),
                "_store_call": s(store, "Phone_Tel"),
                "_store_wa": s(store, "WhatsApp_Number"),
                "_store_appointment": s(store, "Appointment_URL")
            }
            
            # Skip if no social media IDs configured
            if not store_data["facebook_page_id"] and not store_data["instagram_business_account_id"]:
                log(f"⚠️  No social media IDs configured for {store_name}")
                continue
            
            # Get image paths from 03_published subdirectories
            facebook_image = os.path.join(FACEBOOK_DIR, f"{base_name}_facebook.jpg")
            instagram_image = os.path.join(INSTAGRAM_DIR, f"{base_name}_instagram.jpg")
            
            # Publish to social media
            log(f"📱 Publishing to social media ({store_name}): {filename}")
            results = publisher.publish_offer(
                offer,
                store_data,
                facebook_image_path=facebook_image if os.path.exists(facebook_image) else None,
                instagram_image_path=instagram_image if os.path.exists(instagram_image) else None
            )
            
            if results["facebook"]:
                log(f"✅ Published to Facebook ({store_name}): {filename}")
            if results["instagram"]:
                log(f"✅ Published to Instagram ({store_name}): {filename}")

# ==============================
# ARCHIVE EXPIRED OFFERS
# ==============================

def archive_expired(offers):
    """
    Archive offers that are:
    - Marked as Offer_Expired = Yes/yes/Y/True/true
    - OR past their Valid_Till date
    
    Moves images from 03_published to 04_archived
    """
    for offer in offers:
        
        # Check if offer is no longer valid
        if is_offer_valid(offer):
            continue  # Still valid, don't archive

        img = s(offer, "media_asset_name") + ".jpg"

        src = os.path.join(PUBLISHED_DIR, img)
        dst = os.path.join(ARCHIVE_DIR, img)

        if os.path.exists(src):
            shutil.move(src, dst)
            log(f"Archived {img}")

# ==============================
# MAIN
# ==============================

def main():
    log("Offer automation started")

    offers = load_offers()

    processed_drive_images = process_new_images()

    generate_missing_images(offers, processed_drive_images)
    
    # Publish to social media (if enabled)
    # Note: For standalone execution, we need to load stores
    # In production, this is called from build.py which passes active_stores
    try:
        # Try to load stores for social publishing
        import json
        stores_path = os.path.join(os.path.dirname(__file__), "data", "stores.json")
        if os.path.exists(stores_path):
            with open(stores_path, 'r') as f:
                stores_data = json.load(f)
                active_stores = [s for s in stores_data if s.get("Active_Status", "").lower() in {"yes", "y", "true", "1"}]
                publish_to_social_media(offers, processed_drive_images, active_stores)
        else:
            log("⚠️  Stores data not found, skipping social media publishing")
    except Exception as e:
        log(f"⚠️  Could not load stores for social publishing: {e}")

    archive_expired(offers)

    log("Automation finished")

def process_offers(offers_data, active_stores):
    """
    Process offers for build.py compatibility.
    
    This function:
    1. Processes new images from Google Drive
    2. Generates missing images for offers without Drive images
    3. Publishes to social media (if enabled) - uses store-specific Facebook/Instagram IDs
    4. Archives expired offers
    
    Returns: (offers_data, processed_images)
    """
    log("Processing offers for build")
    
    # Step 1: Load offers from Google Sheets
    offers = load_offers()
    
    # Step 2: Process new images from Drive
    processed_drive_images = process_new_images()
    
    # Step 3: Generate missing images (where Image_Available = No)
    generate_missing_images(offers, processed_drive_images)
    
    # Step 4: Publish to social media (if enabled) - pass active_stores for social media IDs
    publish_to_social_media(offers, processed_drive_images, active_stores)
    
    # Step 5: Archive expired offers
    archive_expired(offers)
    
    log("Automation finished")
    
    # Return offers data and list of processed images
    return offers_data, processed_drive_images

if __name__ == "__main__":
    main()