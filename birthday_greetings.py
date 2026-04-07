#!/usr/bin/env python3
"""
Birthday Greetings Generator for Naturals Salon Stylists

Automatically detects stylist birthdays and generates personalized greeting images
for posting to Facebook and Instagram. Runs daily at 6:00 AM IST.

Features:
- Detects birthdays from stylists.json (DD-Mon-YYYY format)
- Generates 1080x1080 greeting images with Pillow
- Creates campaign objects for social media posting
- Integrates with existing social_publisher.py
- Logs to CSV files for monitoring
"""

import os
import sys
import json
import hashlib
import locale
import random
import shutil
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple
import pytz
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Add parent directory to path for imports
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT_DIR)

# IST timezone
IST = pytz.timezone('Asia/Kolkata')

# Image constants
IMAGE_SIZE = (1080, 1080)
IMAGE_QUALITY = 95


def load_stylists(filepath: str) -> List[Dict]:
    """
    Load stylist data from JSON file.
    
    Args:
        filepath: Path to stylists.json file
        
    Returns:
        List of stylist dictionaries
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Stylists file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data if isinstance(data, list) else []


def load_birthday_wishes(filepath: str) -> List[Dict]:
    """
    Load birthday wish templates from JSON file.
    
    Args:
        filepath: Path to birthday_wishes.json file
        
    Returns:
        List of template dictionaries
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Birthday wishes file not found: {filepath}")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return data.get('templates', [])


def parse_birth_date(date_str: str) -> Optional[date]:
    """
    Parse birth date in DD-Mon-YYYY format.
    
    Args:
        date_str: Date string (e.g., "15-Mar-1990")
        
    Returns:
        datetime.date object or None if parsing fails
        
    Examples:
        >>> parse_birth_date("15-Mar-1990")
        datetime.date(1990, 3, 15)
        >>> parse_birth_date("invalid")
        None
    """
    if not date_str or not date_str.strip():
        return None
    
    try:
        # Try to set locale for month name parsing
        try:
            locale.setlocale(locale.LC_TIME, 'en_IN.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
            except locale.Error:
                pass  # Use default locale
        
        # Parse date with format DD-Mon-YYYY
        date_obj = datetime.strptime(date_str.strip(), "%d-%b-%Y")
        return date_obj.date()
    
    except ValueError as e:
        print(f"⚠️  Failed to parse date: {date_str} - {e}")
        return None


def is_birthday_today(birth_date: date, current_date_ist: date) -> bool:
    """
    Check if birth date matches current date (day and month only).
    
    Args:
        birth_date: Stylist's birth date
        current_date_ist: Current date in IST timezone
        
    Returns:
        True if day and month match (year is ignored)
        
    Examples:
        >>> is_birthday_today(date(1990, 3, 15), date(2026, 3, 15))
        True
        >>> is_birthday_today(date(1990, 3, 15), date(2026, 3, 16))
        False
    """
    return (birth_date.day == current_date_ist.day and 
            birth_date.month == current_date_ist.month)


def get_field(record: Dict, field_name: str, default: str = "") -> str:
    """
    Get field value with case-insensitive lookup and fallback support.
    
    Args:
        record: Dictionary to search
        field_name: Field name to look up
        default: Default value if field not found
        
    Returns:
        Field value or default
    """
    # Try exact match first
    if field_name in record:
        return str(record[field_name])
    
    # Try case-insensitive match
    field_lower = field_name.lower()
    for key, value in record.items():
        if key.lower() == field_lower:
            return str(value)
    
    return default


def is_yes(value: str) -> bool:
    """
    Check if a value represents 'yes' (case-insensitive).
    
    Args:
        value: String value to check
        
    Returns:
        True if value is 'yes', 'y', 'true', or '1'
    """
    return str(value).strip().lower() in ('yes', 'y', 'true', '1')


def detect_birthdays(stylists: List[Dict], current_date_ist: date) -> List[Dict]:
    """
    Filter stylists with birthdays today (active only).
    
    Args:
        stylists: List of stylist dictionaries
        current_date_ist: Current date in IST timezone
        
    Returns:
        List of stylists with birthdays today
    """
    birthday_stylists = []
    
    for stylist in stylists:
        # Check if stylist is active
        is_active = get_field(stylist, 'is_active', get_field(stylist, 'Active_Status', 'yes'))
        if not is_yes(is_active):
            continue
        
        # Get birth date
        birth_date_str = get_field(stylist, 'stylist_birth_date', '')
        if not birth_date_str:
            print(f"⚠️  Skipping stylist (no birth date): {get_field(stylist, 'stylist_name', 'Unknown')}")
            continue
        
        # Parse birth date
        birth_date = parse_birth_date(birth_date_str)
        if not birth_date:
            print(f"⚠️  Skipping stylist (invalid birth date): {get_field(stylist, 'stylist_name', 'Unknown')}")
            continue
        
        # Check if birthday matches today
        if is_birthday_today(birth_date, current_date_ist):
            birthday_stylists.append(stylist)
    
    return birthday_stylists


def compute_content_hash(date_str: str, store_id: str, stylist_name: str) -> str:
    """
    Compute content hash for deduplication.
    
    Args:
        date_str: Date in YYYYMMDD format (e.g., "20260315")
        store_id: Store identifier (e.g., "Store_N78")
        stylist_name: Stylist name (e.g., "Sonam")
        
    Returns:
        First 16 characters of SHA-256 hash
        
    Examples:
        >>> compute_content_hash("20260315", "Store_N78", "Sonam")
        'a1b2c3d4e5f6g7h8'  # Example hash
    """
    combined = f"{date_str}{store_id}{stylist_name}birthday"
    hash_obj = hashlib.sha256(combined.encode('utf-8'))
    return hash_obj.hexdigest()[:16]


def sanitize_filename(name: str) -> str:
    """
    Sanitize a name for use in filenames.
    
    Args:
        name: Name to sanitize
        
    Returns:
        Sanitized name with spaces replaced by underscores and special characters removed
        
    Examples:
        >>> sanitize_filename("Priya Reddy")
        'Priya_Reddy'
        >>> sanitize_filename("O'Brien")
        'OBrien'
    """
    # Replace spaces with underscores
    sanitized = name.replace(' ', '_')
    
    # Remove special characters (keep only alphanumeric and underscores)
    sanitized = ''.join(c for c in sanitized if c.isalnum() or c == '_')
    
    return sanitized


def select_background_style(index: int) -> Tuple[str, Tuple]:
    """
    Select background style by rotating through 4 styles.
    
    Args:
        index: Index for rotation (0-based)
        
    Returns:
        Tuple of (style_name, color_tuple)
        
    Styles:
        0: Soft pastel gradient (pink to lavender)
        1: Elegant gold on cream
        2: Festive confetti (multicolor on white)
        3: Brand yellow with white
    """
    styles = [
        ("pastel_gradient", ((255, 182, 193), (230, 230, 250))),  # Pink to Lavender
        ("gold_cream", ((255, 248, 220), (255, 215, 0))),          # Cream to Gold
        ("confetti_white", ((255, 255, 255), (255, 255, 255))),    # White (confetti overlay)
        ("brand_yellow", ((255, 223, 0), (255, 255, 255)))         # Yellow to White
    ]
    
    style_index = index % len(styles)
    return styles[style_index]


def create_gradient_background(size: Tuple[int, int], color1: Tuple, color2: Tuple) -> Image.Image:
    """
    Create a gradient background image.
    
    Args:
        size: Image size (width, height)
        color1: Starting color (R, G, B)
        color2: Ending color (R, G, B)
        
    Returns:
        PIL Image with gradient background
    """
    base = Image.new('RGB', size, color1)
    top = Image.new('RGB', size, color2)
    mask = Image.new('L', size)
    mask_data = []
    for y in range(size[1]):
        mask_data.extend([int(255 * (y / size[1]))] * size[0])
    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base


def get_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Get font with fallback support.
    
    Args:
        font_name: Preferred font name
        size: Font size in pixels
        
    Returns:
        ImageFont object
    """
    # Try to load preferred font
    font_paths = [
        f"/usr/share/fonts/truetype/{font_name.lower()}/{font_name}.ttf",
        f"/System/Library/Fonts/{font_name}.ttc",
        f"/usr/share/fonts/{font_name.lower()}.ttf",
    ]
    
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except:
                pass
    
    # Fallback to default font
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except:
        return ImageFont.load_default()


def generate_greeting_image(
    stylist: Dict,
    store_data: Dict,
    output_dir: str,
    current_date: date,
    style_index: int = 0
) -> str:
    """
    Generate 1080x1080 birthday greeting image using Pillow.
    
    Args:
        stylist: Stylist dictionary with name, gender, photo status
        store_data: Store dictionary with display name and brand name
        output_dir: Directory to save image
        current_date: Current date for filename
        style_index: Index for background style rotation
        
    Returns:
        Generated image filename
    """
    # Get stylist and store information
    stylist_name = get_field(stylist, 'stylist_name', 'Stylist')
    store_id = get_field(stylist, 'store_id', 'Store')
    store_display_name = get_field(store_data, 'store_display_name', 'Naturals Salon')
    brand_store_name = get_field(store_data, 'brand_store_name', f'Naturals {store_display_name}')
    
    # Generate filename
    date_str = current_date.strftime('%Y%m%d')
    sanitized_name = sanitize_filename(stylist_name)
    filename = f"{date_str}_{store_id}_Birthday_{sanitized_name}.jpg"
    filepath = os.path.join(output_dir, filename)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Select background style
    style_name, (color1, color2) = select_background_style(style_index)
    
    # Create base image with gradient
    img = create_gradient_background(IMAGE_SIZE, color1, color2)
    draw = ImageDraw.Draw(img)
    
    # Load fonts
    font_large = get_font("Playfair-Display", 80)
    font_xlarge = get_font("Montserrat", 120)
    font_medium = get_font("Poppins", 50)
    font_small = get_font("Lato", 40)
    
    # Draw text elements
    width, height = IMAGE_SIZE
    
    # "HAPPY BIRTHDAY" - Large, centered at top
    text1 = "HAPPY BIRTHDAY"
    try:
        bbox1 = draw.textbbox((0, 0), text1, font=font_large)
        text1_width = bbox1[2] - bbox1[0]
    except:
        text1_width = len(text1) * 40
    x1 = (width - text1_width) // 2
    y1 = 150
    draw.text((x1, y1), text1, fill=(50, 50, 50), font=font_large)
    
    # Stylist Name - Very Large, centered
    try:
        bbox2 = draw.textbbox((0, 0), stylist_name, font=font_xlarge)
        text2_width = bbox2[2] - bbox2[0]
    except:
        text2_width = len(stylist_name) * 60
    x2 = (width - text2_width) // 2
    y2 = 400
    draw.text((x2, y2), stylist_name, fill=(200, 100, 50), font=font_xlarge)
    
    # Store Display Name - Medium, centered
    try:
        bbox3 = draw.textbbox((0, 0), store_display_name, font=font_medium)
        text3_width = bbox3[2] - bbox3[0]
    except:
        text3_width = len(store_display_name) * 25
    x3 = (width - text3_width) // 2
    y3 = 650
    draw.text((x3, y3), store_display_name, fill=(80, 80, 80), font=font_medium)
    
    # "Team Naturals - [Store Name]" - Small, centered at bottom
    footer_text = f"Team {brand_store_name}"
    try:
        bbox4 = draw.textbbox((0, 0), footer_text, font=font_small)
        text4_width = bbox4[2] - bbox4[0]
    except:
        text4_width = len(footer_text) * 20
    x4 = (width - text4_width) // 2
    y4 = 900
    draw.text((x4, y4), footer_text, fill=(100, 100, 100), font=font_small)
    
    # Save image
    img.save(filepath, 'JPEG', quality=IMAGE_QUALITY)
    
    return filename


def generate_caption(stylist: Dict, store_data: Dict, templates: List[Dict]) -> str:
    """
    Generate caption with random template and placeholder substitution.
    
    Args:
        stylist: Stylist dictionary
        store_data: Store dictionary
        templates: List of caption templates
        
    Returns:
        Generated caption with placeholders replaced
    """
    if not templates:
        # Fallback caption if no templates available
        stylist_name = get_field(stylist, 'stylist_name', 'our stylist')
        store_name = get_field(store_data, 'store_display_name', 'Naturals Salon')
        return f"🎉 Happy Birthday {stylist_name}! 🎉\n\nWishing you an amazing day from all of us at {store_name}!\n\n#HappyBirthday #NaturalsSalon #SalonFamily #TeamNaturals"
    
    # Select random template
    template = random.choice(templates)
    message = template.get('message', '')
    
    # Get values for placeholders
    stylist_name = get_field(stylist, 'stylist_name', 'our stylist')
    store_display_name = get_field(store_data, 'store_display_name', 'Naturals Salon')
    
    # Replace placeholders
    caption = message.replace('{{stylist_name}}', stylist_name)
    caption = caption.replace('{{store_display_name}}', store_display_name)
    
    return caption


def create_campaign_object(
    stylist: Dict,
    store_data: Dict,
    image_filename: str,
    caption: str,
    content_hash: str,
    current_date: date,
    all_stores: List[Dict]
) -> Dict:
    """
    Create campaign object matching content_engine schema.
    
    Args:
        stylist: Stylist dictionary
        store_data: Store dictionary
        image_filename: Generated image filename
        caption: Generated caption
        content_hash: Content hash for deduplication
        current_date: Current date
        all_stores: List of all stores for targeting
        
    Returns:
        Campaign object dictionary
    """
    stylist_name = get_field(stylist, 'stylist_name', 'Stylist')
    store_id = get_field(stylist, 'store_id', '')
    store_display_name = get_field(store_data, 'store_display_name', 'Naturals Salon')
    
    # Create campaign ID
    date_str = current_date.strftime('%Y%m%d')
    sanitized_name = sanitize_filename(stylist_name)
    campaign_id = f"birthday_{date_str}_{store_id}_{sanitized_name}"
    
    # Create base campaign object
    campaign = {
        # Content identification
        "content_type": "greeting",
        "content_title": f"Happy Birthday {stylist_name}",
        "content_body": caption,
        "campaign_id": campaign_id,
        
        # Media
        "has_media": "Yes",
        "media_asset_name": image_filename,
        "Image_Name": image_filename,  # Legacy field
        
        # Status and approval
        "approval_status": "Yes",
        "social_enabled": "Yes",
        "is_expired": "No",
        
        # Platform targeting
        "post_facebook": "Yes",
        "post_instagram": "Yes",
        "post_google": "No",
        "post_website": "No",
        
        # Store targeting - default all to No
        "target_all_stores": "No",
        
        # Deduplication
        "content_hash": content_hash,
        
        # Dates
        "start_date": current_date.strftime('%d-%b-%Y'),
        "end_date": current_date.strftime('%d-%b-%Y'),
        
        # Priority
        "campaign_priority": "high"
    }
    
    # Set store targeting - only stylist's store
    for store in all_stores:
        store_key = get_field(store, 'Store_ID', '')
        if store_key:
            # Convert Store_N78 to target_store_n78
            target_key = f"target_store_{store_key.lower().replace('store_', '')}"
            campaign[target_key] = "Yes" if store_key == store_id else "No"
    
    return campaign


def main():
    """Main execution function."""
    print("🎂 Birthday Greeting Generator - Starting")
    print(f"   Current time: {datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    # Get current date in IST
    current_date_ist = datetime.now(IST).date()
    print(f"   Current date (IST): {current_date_ist}")
    
    # Load stylists data
    stylists_path = os.path.join(ROOT_DIR, 'data', 'stylists.json')
    try:
        stylists = load_stylists(stylists_path)
        print(f"   Loaded {len(stylists)} stylist records")
    except Exception as e:
        print(f"❌ Failed to load stylists: {e}")
        return
    
    # Load stores data
    stores_path = os.path.join(ROOT_DIR, 'data', 'stores.json')
    try:
        with open(stores_path, 'r', encoding='utf-8') as f:
            all_stores = json.load(f)
        print(f"   Loaded {len(all_stores)} store records")
    except Exception as e:
        print(f"❌ Failed to load stores: {e}")
        return
    
    # Create store lookup dictionary
    stores_by_id = {get_field(s, 'Store_ID', ''): s for s in all_stores}
    
    # Load birthday wishes templates
    wishes_path = os.path.join(os.path.dirname(ROOT_DIR), 'config', 'birthday_wishes.json')
    try:
        templates = load_birthday_wishes(wishes_path)
        print(f"   Loaded {len(templates)} birthday wish templates")
    except FileNotFoundError:
        print(f"   ℹ️  birthday_wishes.json not found — using built-in templates")
        templates = []  # generate_caption() has a built-in fallback
    except Exception as e:
        print(f"⚠️  Failed to load birthday wishes: {e} — using built-in templates")
        templates = []
    
    # Detect birthdays
    birthday_stylists = detect_birthdays(stylists, current_date_ist)
    
    if not birthday_stylists:
        print("   No birthdays detected today")
        print("✅ Birthday Greeting Generator - Complete (0 birthdays)")
        return []
    
    print(f"\n🎉 Detected {len(birthday_stylists)} birthday(s) today:")
    for stylist in birthday_stylists:
        stylist_name = get_field(stylist, 'stylist_name', 'Unknown')
        store_id = get_field(stylist, 'store_id', 'Unknown')
        store_data = stores_by_id.get(store_id, {})
        store_display_name = get_field(store_data, 'store_display_name', 'Unknown')
        print(f"   - {stylist_name} ({store_id} - {store_display_name})")
    
    # Create output directory for images — use greeting campaign folder
    greeting_published = os.path.join(os.path.dirname(ROOT_DIR), 'assets', 'greeting', '03_published')
    greeting_facebook  = os.path.join(os.path.dirname(ROOT_DIR), 'assets', 'greeting', 'facebook')
    greeting_instagram = os.path.join(os.path.dirname(ROOT_DIR), 'assets', 'greeting', 'instagram')
    os.makedirs(greeting_published, exist_ok=True)
    os.makedirs(greeting_facebook,  exist_ok=True)
    os.makedirs(greeting_instagram, exist_ok=True)
    output_dir = greeting_published
    
    # Import social publisher — no longer used here; campaigns go through campaign_engine
    # Process each birthday stylist
    success_count = 0
    error_count = 0
    birthday_campaigns = []
    
    for index, stylist in enumerate(birthday_stylists):
        stylist_name = get_field(stylist, 'stylist_name', 'Unknown')
        store_id = get_field(stylist, 'store_id', '')
        
        if not store_id or store_id not in stores_by_id:
            print(f"\n⚠️  Skipping {stylist_name}: Invalid or missing store_id")
            error_count += 1
            continue
        
        store_data = stores_by_id[store_id]
        store_display_name = get_field(store_data, 'store_display_name', 'Unknown')
        
        print(f"\n📸 Processing birthday greeting for {stylist_name} ({store_display_name})...")
        
        try:
            # Generate greeting image → saved to campaigns/greeting/03_published/
            image_filename = generate_greeting_image(
                stylist,
                store_data,
                output_dir,
                current_date_ist,
                style_index=index
            )
            print(f"   ✅ Generated image: {image_filename}")

            # Copy to facebook/ and instagram/ subfolders with platform suffixes
            base, ext = os.path.splitext(image_filename)
            src = os.path.join(output_dir, image_filename)

            fb_filename = f"{base}_facebook{ext}"
            ig_filename = f"{base}_instagram{ext}"
            fb_path = os.path.join(greeting_facebook,  fb_filename)
            ig_path = os.path.join(greeting_instagram, ig_filename)
            shutil.copy2(src, fb_path)
            shutil.copy2(src, ig_path)
            print(f"   ✅ Copied to facebook/instagram subfolders")

            # Generate caption
            caption = generate_caption(stylist, store_data, templates)
            print(f"   ✅ Generated caption ({len(caption)} chars)")

            # Compute content hash
            date_str = current_date_ist.strftime('%Y%m%d')
            content_hash = compute_content_hash(date_str, store_id, stylist_name)
            print(f"   ✅ Content hash: {content_hash}")

            # Create campaign object — media_asset_name is the base name (no ext)
            campaign = create_campaign_object(
                stylist,
                store_data,
                base,          # media_asset_name without extension
                caption,
                content_hash,
                current_date_ist,
                all_stores
            )
            print(f"   ✅ Created campaign object (content_type=greeting)")

            birthday_campaigns.append(campaign)
            success_count += 1
        
        except Exception as e:
            print(f"   ❌ Error processing {stylist_name}: {e}")
            error_count += 1
            continue

    # Summary
    print(f"\n✅ Birthday Greeting Generator - Complete")
    print(f"   Total birthdays: {len(birthday_stylists)}")
    print(f"   Successfully processed: {success_count}")
    print(f"   Errors: {error_count}")

    return birthday_campaigns


if __name__ == "__main__":
    main()
