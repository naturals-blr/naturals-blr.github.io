#!/usr/bin/env python3
"""
Content Delivery Engine
Generalized content management system for offers, greetings, updates, wishes, etc.
Maintains backward compatibility with existing offers functionality
"""

import os
import json
from datetime import datetime

# Field mapping: New generalized names -> Legacy offer names
FIELD_MAPPING = {
    # Content fields
    "content_title": "Offer_Title",
    "content_body": "Offer_Details",
    "start_date": "Valid_From",
    "end_date": "Valid_till",
    
    # Status fields
    "approval_status": "Offer_Approved",
    "social_enabled": "publish_social",
    "is_expired": "Offer_Expired",
    
    # Routing fields
    "target_all_stores": "Store_All",
    "target_store_n78": "Store_N78",
    "target_store_n45": "Store_N45",
    "target_store_n77": "Store_N77",
    "target_store_n36": "Store_N36",
    "target_store_n05": "Store_N05",
    "target_store_n43": "Store_N43",
    
    # Media fields
    "has_media": "Image_Available",
    "media_asset_name": "Image_Name",
    
    # New fields (no legacy mapping - these are new)
    # Campaign management
    "content_type": None,           # offer | greeting | update | wish | announcement
    "campaign_id": None,            # Unique campaign identifier
    "campaign_priority": None,      # Priority level (1-5, 1=highest)
    
    # Social media specific
    "caption_template": None,       # Template for social media captions
    "cta_text": None,              # Call-to-action text
    "hashtags": None,              # Comma-separated hashtags
    
    # Platform-specific flags
    "post_facebook": None,         # Post to Facebook (Yes/No)
    "post_instagram": None,        # Post to Instagram (Yes/No)
    "post_google": None,           # Post to Google Business (Yes/No)
    "post_website": None,          # Show on website (Yes/No)
    
    # Content tracking
    "content_hash": None           # Hash for deduplication
}

# Reverse mapping: Legacy names -> New names
REVERSE_FIELD_MAPPING = {v: k for k, v in FIELD_MAPPING.items()}


class ContentEngine:
    """
    Generalized content delivery engine
    Supports both legacy (Offer_*) and new (content_*) field names
    """
    
    def __init__(self):
        """Initialize content engine"""
        self.field_mapping = FIELD_MAPPING
        self.reverse_mapping = REVERSE_FIELD_MAPPING
    
    def get_field(self, content_item, field_name, default=""):
        """
        Get field value with support for both naming conventions
        
        Args:
            content_item: Dict with content data
            field_name: Field name (can be legacy or new format)
            default: Default value if field not found
        
        Returns:
            Field value (case-insensitive)
        
        Examples:
            get_field(item, "content_title")  # Returns Offer_Title value
            get_field(item, "Offer_Title")    # Also works
            get_field(item, "CONTENT_TITLE")  # Case-insensitive
        """
        if not content_item:
            return default
        
        # Normalize field name to lowercase for case-insensitive matching
        field_lower = field_name.lower()
        
        # Try direct match (case-insensitive)
        for key, value in content_item.items():
            if key.lower() == field_lower:
                return value if value is not None else default
        
        # Try new -> legacy mapping (case-insensitive)
        for new_name, legacy_name in self.field_mapping.items():
            if new_name.lower() == field_lower:
                # Found mapping
                if legacy_name is None:
                    # No legacy mapping (new field only)
                    return default
                # Look for legacy field
                for key, value in content_item.items():
                    if key.lower() == legacy_name.lower():
                        return value if value is not None else default
        
        # Try legacy -> new mapping (case-insensitive)
        for new_name, legacy_name in self.field_mapping.items():
            if legacy_name and legacy_name.lower() == field_lower:
                # Found mapping, now look for new field
                for key, value in content_item.items():
                    if key.lower() == new_name.lower():
                        return value if value is not None else default
        
        return default
    
    def normalize_content(self, content_item):
        """
        Normalize content item to include both legacy and new field names
        This ensures backward compatibility
        
        Args:
            content_item: Dict with content data
        
        Returns:
            Dict with both naming conventions
        """
        normalized = dict(content_item)
        
        # Add new field names based on legacy values
        for new_name, legacy_name in self.field_mapping.items():
            if legacy_name in content_item and new_name not in content_item:
                normalized[new_name] = content_item[legacy_name]
        
        # Add legacy field names based on new values
        for new_name, legacy_name in self.field_mapping.items():
            if new_name in content_item and legacy_name not in content_item:
                normalized[legacy_name] = content_item[new_name]
        
        return normalized
    
    def is_approved(self, content_item):
        """
        Check if content is approved
        Supports: approval_status, Offer_Approved
        """
        value = self.get_field(content_item, "approval_status")
        return self._is_yes(value)
    
    def is_social_enabled(self, content_item):
        """
        Check if social media publishing is enabled
        Supports: social_enabled, publish_social
        """
        value = self.get_field(content_item, "social_enabled")
        return self._is_yes(value)
    
    def is_expired(self, content_item):
        """
        Check if content is expired
        Supports: is_expired, Offer_Expired
        """
        value = self.get_field(content_item, "is_expired")
        return self._is_yes(value)
    
    def has_media(self, content_item):
        """
        Check if content has media attached
        Supports: has_media, Image_Available
        """
        value = self.get_field(content_item, "has_media")
        return self._is_yes(value)
    
    def targets_all_stores(self, content_item):
        """
        Check if content targets all stores
        Supports: target_all_stores, Store_All
        """
        value = self.get_field(content_item, "target_all_stores")
        return self._is_yes(value)
    
    def targets_store(self, content_item, store_id):
        """
        Check if content targets specific store.
        Fully case-insensitive — store_id may arrive as any of:
          "Store_N78", "store_n78", "STORE_N78", "N78", "n78"

        Args:
            content_item: Content data
            store_id: Store ID in any case/format

        Returns:
            bool: True if content targets this store
        """
        # Check if targets all stores first
        if self.targets_all_stores(content_item):
            return True

        # Normalise to uppercase short form, e.g. "N78"
        sid = store_id.strip()
        sid_upper = sid.upper()
        if sid_upper.startswith("STORE_"):
            store_short = sid_upper[len("STORE_"):]   # "N78"
        else:
            store_short = sid_upper                    # already "N78"

        store_short_lower = store_short.lower()        # "n78"

        # Try new sheet field: target_store_n78
        value = self.get_field(content_item, f"target_store_{store_short_lower}")
        if self._is_yes(value):
            return True

        # Try legacy field: Store_N78
        value = self.get_field(content_item, f"Store_{store_short}")
        if self._is_yes(value):
            return True

        return False
    
    def is_valid_date_range(self, content_item):
        """
        Check if content is within valid date range
        Supports: start_date/end_date, Valid_From/Valid_till
        
        Returns:
            bool: True if current date is within range
        """
        start_date_str = self.get_field(content_item, "start_date")
        end_date_str = self.get_field(content_item, "end_date")
        
        if not end_date_str:
            return True  # No end date means always valid
        
        try:
            # Parse end date (format: DD-MMM-YYYY or DD-Mon-YYYY)
            end_date = self._parse_date(end_date_str)
            if not end_date:
                return True
            
            # Check if expired
            today = datetime.now().date()
            if today > end_date:
                return False
            
            # Check start date if provided
            if start_date_str:
                start_date = self._parse_date(start_date_str)
                if start_date and today < start_date:
                    return False
            
            return True
            
        except Exception as e:
            print(f"⚠️  Error parsing dates: {e}")
            return True  # Default to valid if parsing fails
    
    def is_content_valid(self, content_item):
        """
        Check if content is valid for publishing
        
        Criteria:
        - Must be approved
        - Must not be expired
        - Must be within valid date range
        
        Returns:
            bool: True if content is valid
        """
        # Check approval
        if not self.is_approved(content_item):
            return False
        
        # Check expired flag
        if self.is_expired(content_item):
            return False
        
        # Check date range
        if not self.is_valid_date_range(content_item):
            return False
        
        return True
    
    def get_content_for_store(self, content_items, store_id):
        """
        Get all valid content items for a specific store
        
        Args:
            content_items: List of content items
            store_id: Store ID (e.g., "Store_N78" or "N78")
        
        Returns:
            List of content items targeting this store
        """
        result = []
        
        for item in content_items:
            # Check if valid
            if not self.is_content_valid(item):
                continue
            
            # Check if targets this store
            if self.targets_store(item, store_id):
                result.append(self.normalize_content(item))
        
        return result
    
    def get_social_content(self, content_items, store_id=None):
        """
        Get content items that should be published to social media
        
        Args:
            content_items: List of content items
            store_id: Optional store ID to filter by
        
        Returns:
            List of content items for social media
        """
        result = []
        
        for item in content_items:
            # Check if valid
            if not self.is_content_valid(item):
                continue
            
            # Check if social enabled
            if not self.is_social_enabled(item):
                continue
            
            # Check store targeting if specified
            if store_id and not self.targets_store(item, store_id):
                continue
            
            result.append(self.normalize_content(item))
        
        return result
    
    def get_content_with_media(self, content_items):
        """
        Get content items that have media attached
        
        Args:
            content_items: List of content items
        
        Returns:
            List of content items with media
        """
        result = []
        
        for item in content_items:
            if self.has_media(item):
                result.append(self.normalize_content(item))
        
        return result
    
    def get_content_type(self, content_item):
        """
        Get content type
        Returns: offer | festival | greeting | update | announcement | testimonial
        Defaults to "offer" if empty
        """
        content_type = self.get_field(content_item, "content_type")
        if not content_type:
            return "offer"  # Default to offer
        return content_type.lower()
    
    def get_campaign_id(self, content_item):
        """Get campaign ID"""
        return self.get_field(content_item, "campaign_id")
    
    def get_campaign_priority(self, content_item):
        """
        Get campaign priority
        Returns: "high" | "normal" | "low"
        Defaults to "normal" if empty
        """
        priority = self.get_field(content_item, "campaign_priority")
        if not priority:
            return "normal"
        
        priority_lower = str(priority).strip().lower()
        
        # Map old integer values to new string values for backward compatibility
        if priority_lower in {"1", "high"}:
            return "high"
        elif priority_lower in {"2", "3", "normal"}:
            return "normal"
        elif priority_lower in {"4", "5", "low"}:
            return "low"
        else:
            return "normal"  # Default
    
    def should_post_to_facebook(self, content_item):
        """
        Check if content should be posted to Facebook
        Falls back to social_enabled if post_facebook not specified
        """
        # Check specific Facebook flag first
        facebook_flag = self.get_field(content_item, "post_facebook")
        if facebook_flag:
            return self._is_yes(facebook_flag)
        
        # Fall back to general social_enabled flag
        return self.is_social_enabled(content_item)
    
    def should_post_to_instagram(self, content_item):
        """
        Check if content should be posted to Instagram
        Falls back to social_enabled if post_instagram not specified
        """
        # Check specific Instagram flag first
        instagram_flag = self.get_field(content_item, "post_instagram")
        if instagram_flag:
            return self._is_yes(instagram_flag)
        
        # Fall back to general social_enabled flag
        return self.is_social_enabled(content_item)
    
    def should_post_to_google(self, content_item):
        """
        Check if content should be posted to Google Business
        """
        google_flag = self.get_field(content_item, "post_google")
        return self._is_yes(google_flag)
    
    def should_show_on_website(self, content_item):
        """
        Check if content should be shown on website
        Always returns True to show all campaigns on website
        """
        return True
    
    def get_caption_template(self, content_item):
        """Get caption template for social media"""
        return self.get_field(content_item, "caption_template")
    
    def get_cta_text(self, content_item):
        """Get call-to-action text"""
        return self.get_field(content_item, "cta_text")
    
    def get_hashtags(self, content_item):
        """
        Get hashtags as list
        Returns: List of hashtags (without # prefix)
        """
        hashtags_str = self.get_field(content_item, "hashtags")
        if not hashtags_str:
            return []
        
        # Split by comma and clean up
        hashtags = [tag.strip().lstrip('#') for tag in hashtags_str.split(',')]
        return [tag for tag in hashtags if tag]
    
    def get_content_hash(self, content_item):
        """Get content hash for deduplication"""
        return self.get_field(content_item, "content_hash")
    
    def generate_content_hash(self, content_item):
        """
        Generate content hash from content_title + content_body + media_asset_name
        Used for deduplication
        
        Returns:
            MD5 hash (first 16 characters)
        """
        import hashlib
        
        title = self.get_field(content_item, "content_title")
        body = self.get_field(content_item, "content_body")
        media = self.get_field(content_item, "media_asset_name")
        
        # Combine fields
        combined = f"{title}|{body}|{media}"
        
        # Generate hash
        hash_obj = hashlib.md5(combined.encode('utf-8'))
        return hash_obj.hexdigest()[:16]
    
    def render_caption(self, content_item, store_data=None):
        """
        Render caption with placeholder substitution
        
        Placeholders:
        - {{STORE_NAME}} - Store display name
        - {{AREA}} - Store area
        - {{CITY}} - Store city
        
        Args:
            content_item: Content data
            store_data: Store data (optional)
        
        Returns:
            Rendered caption string
        """
        # Get caption template
        template = self.get_caption_template(content_item)
        
        # If no template, use content_body as fallback
        if not template:
            template = self.get_field(content_item, "content_body")
        
        if not template:
            return ""
        
        caption = template
        
        # Replace placeholders if store data provided
        if store_data:
            store_name = store_data.get("store_display_name", "")
            area = store_data.get("store_area", store_data.get("area", ""))
            city = store_data.get("Address_City", store_data.get("address_city", ""))
            
            caption = caption.replace("{{STORE_NAME}}", store_name)
            caption = caption.replace("{{AREA}}", area)
            caption = caption.replace("{{CITY}}", city)
        
        # Add CTA text if present
        cta = self.get_cta_text(content_item)
        if cta:
            caption += f"\n\n{cta}"
        
        # Add hashtags if present
        hashtags = self.get_hashtags(content_item)
        if hashtags:
            hashtag_str = " ".join([f"#{tag}" for tag in hashtags])
            caption += f"\n\n{hashtag_str}"
        
        return caption
    
    def get_content_by_type(self, content_items, content_type):
        """
        Get content items by type
        
        Args:
            content_items: List of content items
            content_type: "offer", "greeting", "update", "wish", "announcement"
        
        Returns:
            List of content items of specified type
        """
        result = []
        
        for item in content_items:
            if not self.is_content_valid(item):
                continue
            
            item_type = self.get_content_type(item)
            if item_type and item_type.lower() == content_type.lower():
                result.append(self.normalize_content(item))
        
        return result
    
    def get_content_by_campaign(self, content_items, campaign_id):
        """
        Get content items by campaign ID
        
        Args:
            content_items: List of content items
            campaign_id: Campaign identifier
        
        Returns:
            List of content items in specified campaign
        """
        result = []
        
        for item in content_items:
            if not self.is_content_valid(item):
                continue
            
            item_campaign = self.get_campaign_id(item)
            if item_campaign and item_campaign.lower() == campaign_id.lower():
                result.append(self.normalize_content(item))
        
        return result
    
    def sort_by_priority(self, content_items):
        """
        Sort content items by campaign priority (high > normal > low)
        Items without priority are treated as "normal"
        
        Args:
            content_items: List of content items
        
        Returns:
            Sorted list of content items
        """
        priority_order = {"high": 1, "normal": 2, "low": 3}
        
        def get_priority_value(item):
            priority = self.get_campaign_priority(item)
            return priority_order.get(priority, 2)  # Default to normal
        
        return sorted(content_items, key=get_priority_value)
    
    def get_facebook_content(self, content_items, store_id=None):
        """
        Get content items for Facebook posting
        
        Args:
            content_items: List of content items
            store_id: Optional store ID to filter by
        
        Returns:
            List of content items for Facebook
        """
        result = []
        
        for item in content_items:
            if not self.is_content_valid(item):
                continue
            
            # Enforce has_media requirement for social posting
            if not self.has_media(item):
                continue
            
            if not self.should_post_to_facebook(item):
                continue
            
            if store_id and not self.targets_store(item, store_id):
                continue
            
            result.append(self.normalize_content(item))
        
        return result
    
    def get_instagram_content(self, content_items, store_id=None):
        """
        Get content items for Instagram posting
        
        Args:
            content_items: List of content items
            store_id: Optional store ID to filter by
        
        Returns:
            List of content items for Instagram
        """
        result = []
        
        for item in content_items:
            if not self.is_content_valid(item):
                continue
            
            # Enforce has_media requirement for social posting
            if not self.has_media(item):
                continue
            
            if not self.should_post_to_instagram(item):
                continue
            
            if store_id and not self.targets_store(item, store_id):
                continue
            
            result.append(self.normalize_content(item))
        
        return result
    
    def get_website_content(self, content_items, store_id=None):
        """
        Get content items for website display
        
        Args:
            content_items: List of content items
            store_id: Optional store ID to filter by
        
        Returns:
            List of content items for website
        """
        result = []
        
        for item in content_items:
            if not self.is_content_valid(item):
                continue
            
            if not self.should_show_on_website(item):
                continue
            
            if store_id and not self.targets_store(item, store_id):
                continue
            
            result.append(self.normalize_content(item))
        
        return result
    
    def _is_yes(self, value):
        """Check if value represents 'yes' (case-insensitive)"""
        if value is None:
            return False
        
        value_str = str(value).strip().lower()
        return value_str in {"yes", "y", "true", "t", "1"}
    
    def _parse_date(self, date_str):
        """
        Parse date string in various formats
        Supports: DD-MMM-YYYY, DD-Mon-YYYY, YYYY-MM-DD
        
        Returns:
            datetime.date object or None
        """
        if not date_str:
            return None
        
        date_str = str(date_str).strip()
        
        # Try different formats
        formats = [
            "%d-%b-%Y",    # 26-Feb-2026
            "%d-%B-%Y",    # 26-February-2026
            "%Y-%m-%d",    # 2026-02-26
            "%d/%m/%Y",    # 26/02/2026
            "%m/%d/%Y"     # 02/26/2026
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None


# Global content engine instance
content_engine = ContentEngine()


# Convenience functions for backward compatibility
def get_field(content_item, field_name, default=""):
    """Get field value (supports both naming conventions)"""
    return content_engine.get_field(content_item, field_name, default)


def normalize_content(content_item):
    """Normalize content to include both naming conventions"""
    return content_engine.normalize_content(content_item)


def is_content_valid(content_item):
    """Check if content is valid for publishing"""
    return content_engine.is_content_valid(content_item)


def get_content_for_store(content_items, store_id):
    """Get valid content for specific store"""
    return content_engine.get_content_for_store(content_items, store_id)


def get_social_content(content_items, store_id=None):
    """Get content for social media"""
    return content_engine.get_social_content(content_items, store_id)


def get_facebook_content(content_items, store_id=None):
    """Get content for Facebook"""
    return content_engine.get_facebook_content(content_items, store_id)


def get_instagram_content(content_items, store_id=None):
    """Get content for Instagram"""
    return content_engine.get_instagram_content(content_items, store_id)


def get_website_content(content_items, store_id=None):
    """Get content for website"""
    return content_engine.get_website_content(content_items, store_id)


def get_content_by_type(content_items, content_type):
    """Get content by type (offer, greeting, update, wish, announcement)"""
    return content_engine.get_content_by_type(content_items, content_type)


def sort_by_priority(content_items):
    """Sort content by campaign priority"""
    return content_engine.sort_by_priority(content_items)


def generate_content_hash(content_item):
    """Generate content hash for deduplication"""
    return content_engine.generate_content_hash(content_item)


def render_caption(content_item, store_data=None):
    """Render caption with placeholder substitution"""
    return content_engine.render_caption(content_item, store_data)
