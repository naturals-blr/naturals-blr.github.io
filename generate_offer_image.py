#!/usr/bin/env python3
"""
Offer Image Generator
Creates placeholder images for offers when Image_Available = No
Uses PIL to generate branded offer images
"""

import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

IST = ZoneInfo("Asia/Kolkata")
IMAGE_OUTPUT_DIR = "campaigns/offer"

def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")

def generate_offer_image(offer_data, store_name):
    """
    Generate a branded offer image
    """
    
    # Create image
    width, height = 1080, 1080
    img = Image.new('RGB', (width, height), color='#632b6f')
    draw = ImageDraw.Draw(img)
    
    try:
        # Try to load a nice font
        font_title = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 48)
        font_details = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
        font_store = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 18)
        font_valid = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
    except:
        # Fallback to default font
        font_title = ImageFont.load_default()
        font_details = ImageFont.load_default()
        font_store = ImageFont.load_default()
        font_valid = ImageFont.load_default()
    
    # Add store name at top
    store_text = f"Naturals {store_name}"
    draw.text((20, 30), store_text, fill='white', font=font_store)
    
    # Add offer title (centered)
    title = offer_data.get("Offer_Title", "Special Offer")
    title_lines = wrap_text(title, 40)
    y_offset = 200
    
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text((x, y_offset), line, fill='white', font=font_title)
        y_offset += 60
    
    # Add offer details
    details = offer_data.get("Offer_Details", "")
    if details:
        detail_lines = wrap_text(details, 50)
        y_offset += 40
        
        for line in detail_lines[:3]:  # Max 3 lines
            draw.text((40, y_offset), line, fill='#f0f0f0', font=font_details)
            y_offset += 30
    
    # Add validity period
    valid_from = offer_data.get("Valid_From", "")
    valid_till = offer_data.get("Valid_till", "")
    valid_text = f"Valid: {valid_from} - {valid_till}"
    draw.text((40, height - 100), valid_text, fill='#ffd700', font=font_valid)
    
    # Add "Naturals" logo text at bottom
    draw.text((40, height - 50), "NATURALS", fill='white', font=font_store)
    
    return img

def wrap_text(text, max_width):
    """
    Simple text wrapping for PIL
    """
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        test_line = ' '.join(current_line)
        
        # Simple width estimation (approximate)
        if len(test_line) > max_width:
            if len(current_line) == 1:
                lines.append(current_line)
                current_line = []
            else:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

def create_image_filename(offer_data, store_id):
    """
    Generate filename: YYYYMMDD_StoreID_offer_title.jpg
    """
    date_str = offer_data.get("Valid_From", "")
    if date_str:
        try:
            date = datetime.strptime(date_str, "%d-%b-%Y")
        except:
            date = datetime.now(IST)
    else:
        date = datetime.now(IST)
    
    title_slug = slugify(offer_data.get("Offer_Title", ""))[:30]
    
    return f"{date.strftime('%Y%m%d')}_{store_id}_{title_slug}.jpg"

def save_offer_image(offer_data, store_id, store_name):
    """
    Generate and save offer image
    """
    
    # Ensure output directory exists
    os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)
    
    # Generate image
    img = generate_offer_image(offer_data, store_name)
    
    # Create filename
    filename = create_image_filename(offer_data, store_id)
    filepath = os.path.join(IMAGE_OUTPUT_DIR, filename)
    
    # Save image
    img.save(filepath, 'JPEG', quality=85)
    
    print(f"Generated offer image: {filename}")
    return filename

if __name__ == "__main__":
    # Test example
    test_offer = {
        "Offer_Title": "Bridal Makeup Offer",
        "Offer_Details": "Flat ₹2000 off on Bridal Packages",
        "Valid_From": "20-Mar-2026",
        "Valid_till": "31-Mar-2026"
    }
    
    save_offer_image(test_offer, "N78", "JP Nagar")
    print("Test image generated successfully!")