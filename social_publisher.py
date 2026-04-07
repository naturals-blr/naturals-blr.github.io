#!/usr/bin/env python3
"""
Social Media Publisher
Posts offers to Facebook and Instagram
Uses Facebook Graph API for cross-platform publishing
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path

# Import CSV logger
try:
    from csv_logger import log_social_post, log_error
    CSV_LOGGER_AVAILABLE = True
except ImportError:
    CSV_LOGGER_AVAILABLE = False
    print("⚠️  CSV logger not available")

class SocialPublisher:
    def __init__(self, access_token=None, page_id=None, instagram_account_id=None, dry_run=False, website_base_url=None):
        """
        Initialize Social Publisher
        
        Args:
            access_token: Facebook Page Access Token (from env or GitHub secrets)
            page_id: Facebook Page ID (optional, can be passed per-store)
            instagram_account_id: Instagram Business Account ID (optional, can be passed per-store)
            dry_run: If True, simulate posting without actually posting
            website_base_url: Base URL for hosted images (e.g., "https://naturals-blr.github.io")
        """
        self.access_token = access_token or os.getenv("FACEBOOK_ACCESS_TOKEN", "")
        self.default_page_id = page_id  # Optional default
        self.default_instagram_id = instagram_account_id  # Optional default
        self.dry_run = dry_run or os.getenv("DRY_RUN", "false").lower() == "true"
        self.website_base_url = website_base_url or os.getenv("WEBSITE_BASE_URL", "https://naturals-blr.github.io")
        self.base_url = "https://graph.facebook.com/v21.0"  # Updated to latest version
        
        # Track published posts to avoid duplicates
        self.published_log_file = "data/social_published.json"
        self.published_posts = self._load_published_log()
    
    def _load_published_log(self):
        """Load log of previously published posts"""
        if os.path.exists(self.published_log_file):
            try:
                with open(self.published_log_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_published_log(self):
        """Save log of published posts"""
        os.makedirs(os.path.dirname(self.published_log_file), exist_ok=True)
        with open(self.published_log_file, 'w') as f:
            json.dump(self.published_posts, f, indent=2)
    
    def _is_already_published(self, offer_id, platform):
        """Check if offer was already published to platform"""
        key = f"{offer_id}_{platform}"
        return key in self.published_posts
    
    def _mark_as_published(self, offer_id, platform, post_id=None):
        """Mark offer as published to platform"""
        key = f"{offer_id}_{platform}"
        self.published_posts[key] = {
            "published_at": datetime.now().isoformat(),
            "post_id": post_id,
            "offer_id": offer_id,
            "platform": platform
        }
        self._save_published_log()
    
    def publish_offer(self, offer_data, store_data, facebook_image_path=None, instagram_image_path=None):
        """
        Publish offer to Facebook and Instagram
        
        Args:
            offer_data: Dict with offer details (Offer_Title, Offer_Details, etc.)
            store_data: Dict with store details (store_display_name, facebook_page_id, instagram_business_account_id, etc.)
            facebook_image_path: Path to Facebook-sized image
            instagram_image_path: Path to Instagram-sized image
        
        Returns:
            Dict with results: {"facebook": bool, "instagram": bool}
        """
        results = {"facebook": False, "instagram": False}
        
        offer_id = offer_data.get("Image_Name", offer_data.get("Offer_Title", "unknown"))
        store_name = store_data.get("store_display_name", "Naturals Salon")
        
        # Get store-specific social media IDs
        facebook_page_id = store_data.get("facebook_page_id", self.default_page_id)
        instagram_account_id = store_data.get("instagram_business_account_id", self.default_instagram_id)
        
        # Check if already published
        if self._is_already_published(offer_id, "facebook"):
            print(f"⏭️  Already published to Facebook: {offer_id}")
        else:
            # Publish to Facebook (if page ID available)
            if facebook_page_id:
                results["facebook"] = self.publish_to_facebook(
                    offer_data, 
                    store_name,
                    facebook_page_id,
                    facebook_image_path
                )
            else:
                print(f"⚠️  No Facebook Page ID for {store_name}")
        
        if self._is_already_published(offer_id, "instagram"):
            print(f"⏭️  Already published to Instagram: {offer_id}")
        else:
            # Publish to Instagram (if account ID available)
            if instagram_account_id:
                results["instagram"] = self.publish_to_instagram(
                    offer_data, 
                    store_name,
                    instagram_account_id,
                    instagram_image_path
                )
            else:
                print(f"⚠️  No Instagram Account ID for {store_name}")
        
        return results
    
    def publish_to_facebook(self, offer_data, store_name, page_id, image_path=None):
        """
        Post to Facebook Page using Graph API v21.0 with pages_manage_posts permission
        Uses public image URL instead of file upload
        
        Args:
            offer_data: Offer details
            store_name: Store name
            page_id: Facebook Page ID (from store data)
            image_path: Path to image file (will be converted to public URL)
        """
        if not self.access_token:
            print("❌ Facebook access token not configured")
            return False
        
        if not page_id:
            print("❌ Facebook Page ID not provided")
            return False
        
        offer_id = offer_data.get("Image_Name", offer_data.get("image_name", offer_data.get("Offer_Title", "unknown")))
        title = offer_data.get("Offer_Title", offer_data.get("offer_title", "Special Offer"))
        
        # Build caption
        caption = self.build_facebook_caption(offer_data, store_name)
        
        # Convert local path to public URL
        image_url = self._get_public_image_url(image_path)
        
        if not image_url:
            print(f"⚠️  Could not generate public URL for image: {image_path}")
            return False
        
        if self.dry_run:
            print(f"🔵 [DRY RUN] Would post to Facebook: {title}")
            print(f"   Page ID: {page_id}")
            print(f"   Caption: {caption[:100]}...")
            print(f"   Image URL: {image_url}")
            self._mark_as_published(offer_id, "facebook", "dry_run_id")
            
            # Log dry run
            if CSV_LOGGER_AVAILABLE:
                log_social_post(
                    platform="facebook",
                    store_data={"Store_ID": page_id, "store_display_name": store_name, "facebook_page_id": page_id},
                    offer_data=offer_data,
                    status="success",
                    post_id="dry_run_id",
                    dry_run=True,
                    image_url=image_url
                )
            
            return True
        
        # Use Facebook Pages API endpoint with public URL
        url = f"{self.base_url}/{page_id}/photos"
        
        try:
            # Post with public image URL
            data = {
                'url': image_url,  # Use public URL instead of file upload
                'caption': caption,
                'access_token': self.access_token
            }
            
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                post_id = response.json().get('id', '')
                print(f"✅ Published to Facebook ({store_name}): {title}")
                self._mark_as_published(offer_id, "facebook", post_id)
                
                # Log success
                if CSV_LOGGER_AVAILABLE:
                    log_social_post(
                        platform="facebook",
                        store_data={"Store_ID": page_id, "store_display_name": store_name, "facebook_page_id": page_id},
                        offer_data=offer_data,
                        status="success",
                        post_id=post_id,
                        image_url=image_url
                    )
                
                return True
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', {}).get('message', response.text)
                error_code = error_data.get('error', {}).get('code', response.status_code)
                
                print(f"❌ Facebook API error: {response.status_code} - {response.text}")
                
                # Log failure
                if CSV_LOGGER_AVAILABLE:
                    log_social_post(
                        platform="facebook",
                        store_data={"Store_ID": page_id, "store_display_name": store_name, "facebook_page_id": page_id},
                        offer_data=offer_data,
                        status="failed",
                        error_code=str(error_code),
                        error_message=error_msg,
                        image_url=image_url
                    )
                    log_error(
                        module="social",
                        function_name="publish_to_facebook",
                        severity="high",
                        error_message=f"Facebook post failed: {error_msg}",
                        entity_type="post",
                        entity_id=offer_id,
                        error_code=str(error_code),
                        raw_error=response.text
                    )
                
                return False
                
        except Exception as e:
            print(f"❌ Facebook publish error: {e}")
            
            # Log exception
            if CSV_LOGGER_AVAILABLE:
                log_social_post(
                    platform="facebook",
                    store_data={"Store_ID": page_id, "store_display_name": store_name, "facebook_page_id": page_id},
                    offer_data=offer_data,
                    status="failed",
                    error_message=str(e),
                    image_url=image_url
                )
                log_error(
                    module="social",
                    function_name="publish_to_facebook",
                    severity="critical",
                    error_message=f"Facebook publish exception: {e}",
                    entity_type="post",
                    entity_id=offer_id,
                    raw_error=e
                )
            
            return False
                
        except Exception as e:
            print(f"❌ Facebook publish error: {e}")
            return False
    
    def publish_to_instagram(self, offer_data, store_name, instagram_account_id, image_path=None):
        """
        Post to Instagram Business Account using Graph API
        
        Instagram posting is a 2-step async process:
        1. Create media container (with publicly accessible image URL)
        2. Wait for Instagram to process the image (poll status)
        3. Publish the container
        
        Args:
            offer_data: Offer details
            store_name: Store name
            instagram_account_id: Instagram Business Account ID (from store data)
            image_path: Path to image file (will be converted to public URL)
        """
        if not self.access_token:
            print("❌ Instagram access token not configured")
            return False
        
        if not instagram_account_id:
            print("❌ Instagram Account ID not provided")
            return False
        
        offer_id = offer_data.get("Image_Name", offer_data.get("image_name", offer_data.get("Offer_Title", "unknown")))
        title = offer_data.get("Offer_Title", offer_data.get("offer_title", "Special Offer"))
        
        # Build caption
        caption = self.build_instagram_caption(offer_data, store_name)
        
        # Convert local path to public URL
        image_url = self._get_public_image_url(image_path)
        
        if not image_url:
            print(f"⚠️  Could not generate public URL for image: {image_path}")
            return False
        
        if self.dry_run:
            print(f"📸 [DRY RUN] Would post to Instagram: {title}")
            print(f"   Account ID: {instagram_account_id}")
            print(f"   Caption: {caption[:100]}...")
            print(f"   Image URL: {image_url}")
            self._mark_as_published(offer_id, "instagram", "dry_run_id")
            
            # Log dry run
            if CSV_LOGGER_AVAILABLE:
                log_social_post(
                    platform="instagram",
                    store_data={"Store_ID": instagram_account_id, "store_display_name": store_name, "instagram_business_account_id": instagram_account_id},
                    offer_data=offer_data,
                    status="success",
                    post_id="dry_run_id",
                    dry_run=True,
                    image_url=image_url
                )
            
            return True
        
        try:
            # Step 1: Create media container
            container_url = f"{self.base_url}/{instagram_account_id}/media"
            container_data = {
                'image_url': image_url,  # Must be a public HTTPS URL
                'caption': caption,
                'access_token': self.access_token
            }
            
            print(f"   Creating Instagram media container...")
            container_response = requests.post(container_url, data=container_data)
            
            if container_response.status_code != 200:
                print(f"❌ Instagram container creation failed: {container_response.text}")
                return False
            
            container_id = container_response.json().get('id')
            print(f"   ✅ Container created: {container_id}")
            
            # Step 2: Poll container status until ready
            import time
            max_attempts = 12  # 12 attempts * 5 seconds = 60 seconds max
            attempt = 0
            
            print(f"   Waiting for Instagram to process image...")
            while attempt < max_attempts:
                attempt += 1
                time.sleep(5)  # Wait 5 seconds between checks
                
                # Check container status
                status_url = f"{self.base_url}/{container_id}"
                status_params = {
                    'fields': 'status_code',
                    'access_token': self.access_token
                }
                
                status_response = requests.get(status_url, params=status_params)
                
                if status_response.status_code == 200:
                    status_code = status_response.json().get('status_code', '')
                    
                    if status_code == 'FINISHED':
                        print(f"   ✅ Image processed (attempt {attempt})")
                        break
                    elif status_code == 'ERROR':
                        print(f"❌ Instagram processing error")
                        return False
                    else:
                        print(f"   ⏳ Processing... (attempt {attempt}/{max_attempts})")
                else:
                    print(f"   ⚠️  Could not check status (attempt {attempt})")
            
            if attempt >= max_attempts:
                print(f"❌ Instagram processing timeout after {max_attempts * 5} seconds")
                return False
            
            # Step 3: Publish the container
            publish_url = f"{self.base_url}/{instagram_account_id}/media_publish"
            publish_data = {
                'creation_id': container_id,
                'access_token': self.access_token
            }
            
            print(f"   Publishing to Instagram...")
            publish_response = requests.post(publish_url, data=publish_data)
            
            if publish_response.status_code == 200:
                post_id = publish_response.json().get('id', '')
                print(f"✅ Published to Instagram ({store_name}): {title}")
                self._mark_as_published(offer_id, "instagram", post_id)
                
                # Log success
                if CSV_LOGGER_AVAILABLE:
                    log_social_post(
                        platform="instagram",
                        store_data={"Store_ID": instagram_account_id, "store_display_name": store_name, "instagram_business_account_id": instagram_account_id},
                        offer_data=offer_data,
                        status="success",
                        post_id=post_id,
                        image_url=image_url
                    )
                
                return True
            else:
                error_data = publish_response.json() if publish_response.text else {}
                error_msg = error_data.get('error', {}).get('message', publish_response.text)
                error_code = error_data.get('error', {}).get('code', publish_response.status_code)
                
                print(f"❌ Instagram publish failed: {publish_response.text}")
                
                # Log failure
                if CSV_LOGGER_AVAILABLE:
                    log_social_post(
                        platform="instagram",
                        store_data={"Store_ID": instagram_account_id, "store_display_name": store_name, "instagram_business_account_id": instagram_account_id},
                        offer_data=offer_data,
                        status="failed",
                        error_code=str(error_code),
                        error_message=error_msg,
                        image_url=image_url
                    )
                    log_error(
                        module="social",
                        function_name="publish_to_instagram",
                        severity="high",
                        error_message=f"Instagram publish failed: {error_msg}",
                        entity_type="post",
                        entity_id=offer_id,
                        error_code=str(error_code),
                        raw_error=publish_response.text
                    )
                
                return False
                
        except Exception as e:
            print(f"❌ Instagram publish error: {e}")
            
            # Log exception
            if CSV_LOGGER_AVAILABLE:
                log_social_post(
                    platform="instagram",
                    store_data={"Store_ID": instagram_account_id, "store_display_name": store_name, "instagram_business_account_id": instagram_account_id},
                    offer_data=offer_data,
                    status="failed",
                    error_message=str(e),
                    image_url=image_url
                )
                log_error(
                    module="social",
                    function_name="publish_to_instagram",
                    severity="critical",
                    error_message=f"Instagram publish exception: {e}",
                    entity_type="post",
                    entity_id=offer_id,
                    raw_error=e
                )
            
            return False
    
    def _get_public_image_url(self, local_path):
        """
        Convert local image path to public URL.
        Strips everything up to and including 'campaigns/' so only the
        relative web path remains, then prepends website_base_url.

        Examples:
          campaigns/offer/03_published/foo.jpg
            → https://naturals-blr.github.io/campaigns/offer/03_published/foo.jpg
          /home/runner/work/naturals-ops/naturals-ops/campaigns/birthdays/foo.jpg
            → https://naturals-blr.github.io/campaigns/birthdays/foo.jpg
        """
        if not local_path:
            return None

        # Normalise separators
        url_path = local_path.replace("\\", "/")

        # Find 'campaigns/' anywhere in the path and keep from there
        idx = url_path.find("campaigns/")
        if idx != -1:
            url_path = url_path[idx:]
        else:
            # Fallback: strip leading ./ or /
            url_path = url_path.lstrip("./").lstrip("/")

        return f"{self.website_base_url}/{url_path}"
    
    def build_facebook_caption(self, offer_data, store_name):
        """Build Facebook post caption — works for all campaign types."""
        # Support both legacy and new campaign field names
        title   = (offer_data.get("content_title") or offer_data.get("Offer_Title") or "Special Offer")
        details = (offer_data.get("content_body")  or offer_data.get("Offer_Details") or "")
        end_date = (offer_data.get("end_date") or offer_data.get("Valid_till") or "")
        hashtags = offer_data.get("hashtags", "")
        cta_text = offer_data.get("cta_text", "")

        phone          = offer_data.get("_store_call", "")
        whatsapp       = offer_data.get("_store_wa", "")
        appointment_url = offer_data.get("_store_appointment", "")

        caption = f"✨ {title} ✨\n\n"
        if details:
            caption += f"{details}\n\n"
        caption += f"📍 {store_name}\n"
        if end_date:
            caption += f"⏰ Valid till: {end_date}\n"
        if cta_text:
            caption += f"\n{cta_text}\n"
        if phone or whatsapp or appointment_url:
            caption += "\n📞 Book Your Appointment:\n"
            if phone:           caption += f"☎️ Call: {phone}\n"
            if whatsapp:        caption += f"💬 WhatsApp: {whatsapp}\n"
            if appointment_url: caption += f"🔗 Book Online: {appointment_url}\n"

        caption += f"\n{hashtags or '#NaturalsSalon #BangaloreBeauty #Bangalore'}\n"
        return caption
    
    def build_instagram_caption(self, offer_data, store_name):
        """Build Instagram post caption — works for all campaign types."""
        title    = (offer_data.get("content_title") or offer_data.get("Offer_Title") or "Special Offer")
        details  = (offer_data.get("content_body")  or offer_data.get("Offer_Details") or "")
        end_date = (offer_data.get("end_date") or offer_data.get("Valid_till") or "")
        hashtags = offer_data.get("hashtags", "")
        cta_text = offer_data.get("cta_text", "")

        caption = f"✨ {title} ✨\n\n"
        if details:
            caption += f"{details}\n\n"
        caption += f"📍 {store_name}\n"
        if end_date:
            caption += f"⏰ Valid till: {end_date}\n"
        if cta_text:
            caption += f"\n{cta_text}\n"
        caption += "\n📞 DM us to book your appointment!\n\n"
        caption += f"{hashtags or '#NaturalsSalon #BangaloreBeauty #SalonOffers #HairCare #SkinCare #Bangalore #SalonLife #GlowUp #SelfCare'}\n"
        return caption
    
    def get_page_posts(self, limit=10):
        """
        Get recent posts from Facebook Page
        """
        if not self.access_token or not self.page_id:
            return []
        
        url = f"{self.base_url}/{self.page_id}/posts"
        params = {
            "access_token": self.access_token,
            "limit": limit,
            "fields": "id,message,created_time,permalink_url"
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            print(f"Error fetching posts: {response.status_code}")
            return []


def main():
    """
    Test function for social publisher
    """
    print("Social Media Publisher - Test Mode")
    print("=" * 50)
    
    # Initialize publisher
    publisher = SocialPublisher(dry_run=True)
    
    # Test offer data
    test_offer = {
        "Offer_Title": "Bridal Makeup Special",
        "Offer_Details": "Flat ₹2000 off on Bridal Packages. Includes hair styling, makeup, and draping.",
        "Valid_From": "20-Mar-2026",
        "Valid_till": "31-Mar-2026",
        "Image_Name": "20260320_BridalSpecial"
    }
    
    test_store = {
        "store_display_name": "JP Nagar",
        "_store_call": "+91 87926 42299",
        "_store_wa": "+91 87926 42299",
        "_store_appointment": "https://naturals-blr.github.io/stores/jp-nagar.html"
    }
    
    # Test caption building
    print("\n📝 Facebook Caption:")
    print("-" * 50)
    print(publisher.build_facebook_caption(test_offer, test_store["store_display_name"]))
    
    print("\n📝 Instagram Caption:")
    print("-" * 50)
    print(publisher.build_instagram_caption(test_offer, test_store["store_display_name"]))
    
    # Test publishing (dry run)
    print("\n🚀 Testing Publish:")
    print("-" * 50)
    results = publisher.publish_offer(
        test_offer,
        test_store,
        facebook_image_path="campaigns/offer/facebook/20260320_BridalSpecial_facebook.jpg",
        instagram_image_path="campaigns/offer/instagram/20260320_BridalSpecial_instagram.jpg"
    )
    
    print(f"\nResults: {results}")
    print("\n✅ Social publisher test complete!")


if __name__ == "__main__":
    main()