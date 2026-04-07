#!/usr/bin/env python3
"""
CSV Logger Utility
Standardized CSV-based logging for Naturals Ops Automation
All logs are append-only and stored in /logs directory
"""

import os
import csv
import hashlib
import traceback
from datetime import datetime
from pathlib import Path

# Base logs directory
LOGS_DIR = "logs"

# CSV file paths
SOCIAL_POSTS_LOG = os.path.join(LOGS_DIR, "social_posts.csv")
ERRORS_LOG = os.path.join(LOGS_DIR, "errors.csv")
WEBSITE_BUILD_LOG = os.path.join(LOGS_DIR, "website_builds.csv")
REVIEWS_LOG = os.path.join(LOGS_DIR, "reviews.csv")

# CSV Schemas (frozen - do not modify column order)
SOCIAL_POSTS_SCHEMA = [
    "timestamp",
    "platform",
    "store_id",
    "store_display_name",
    "offer_id",
    "offer_title",
    "valid_from",
    "valid_till",
    "post_type",
    "caption_hash",
    "image_url",
    "facebook_page_id",
    "instagram_business_account_id",
    "post_id",
    "status",
    "error_code",
    "error_message",
    "retry_count",
    "dry_run"
]

ERRORS_SCHEMA = [
    "timestamp",
    "module",
    "function_name",
    "store_id",
    "entity_type",
    "entity_id",
    "severity",
    "error_code",
    "error_message",
    "raw_error",
    "stack_trace",
    "action_taken",
    "resolved"
]

WEBSITE_BUILD_SCHEMA = [
    "timestamp",
    "build_id",
    "trigger",
    "status",
    "duration_seconds",
    "pages_generated",
    "offers_processed",
    "stores_processed",
    "error_count",
    "warning_count",
    "git_commit",
    "deployed"
]

REVIEWS_SCHEMA = [
    "review_id",
    "store_id",
    "store_display_name",
    "platform",
    "rating",
    "reviewer_name",
    "review_text",
    "review_language",
    "review_date",
    "reply_text",
    "reply_status",
    "reply_date",
    "reply_mode",
    "escalated",
    "escalation_reason",
    "processed",
    "last_updated"
]


class CSVLogger:
    """CSV Logger with automatic file creation and header management"""
    
    def __init__(self):
        """Initialize CSV Logger and ensure logs directory exists"""
        os.makedirs(LOGS_DIR, exist_ok=True)
    
    def _ensure_file_exists(self, filepath, headers):
        """
        Ensure CSV file exists with proper headers
        Creates file if missing, validates headers if exists
        """
        try:
            if not os.path.exists(filepath):
                # Create new file with headers
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                return True
            else:
                # Validate existing headers
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    try:
                        existing_headers = next(reader)
                        if existing_headers != headers:
                            # Log warning but don't fail
                            print(f"⚠️  Warning: Headers mismatch in {filepath}")
                            print(f"   Expected: {headers}")
                            print(f"   Found: {existing_headers}")
                    except StopIteration:
                        # Empty file, write headers
                        with open(filepath, 'w', newline='', encoding='utf-8') as fw:
                            writer = csv.writer(fw)
                            writer.writerow(headers)
                return True
        except Exception as e:
            print(f"❌ Error ensuring file exists: {filepath} - {e}")
            return False
    
    def _sanitize_value(self, value):
        """
        Sanitize value for CSV storage
        - Truncate long strings
        - Escape newlines and commas
        - Remove sensitive data
        """
        if value is None:
            return ""
        
        # Convert to string
        value = str(value)
        
        # Remove access tokens (anything that looks like a token)
        if len(value) > 100 and ("EAAS" in value or "Bearer" in value):
            return "[REDACTED_TOKEN]"
        
        # Truncate very long strings
        if len(value) > 1000:
            value = value[:997] + "..."
        
        # Escape newlines and tabs
        value = value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        
        # Remove multiple spaces
        value = ' '.join(value.split())
        
        return value
    
    def _append_row(self, filepath, headers, row_dict):
        """
        Append a row to CSV file
        
        Args:
            filepath: Path to CSV file
            headers: List of column names
            row_dict: Dictionary with row data
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure file exists
            if not self._ensure_file_exists(filepath, headers):
                return False
            
            # Build row in correct order
            row = []
            for header in headers:
                value = row_dict.get(header, "")
                row.append(self._sanitize_value(value))
            
            # Append row
            with open(filepath, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(row)
            
            return True
            
        except Exception as e:
            print(f"❌ Error appending row to {filepath}: {e}")
            # Try to log this error to errors.csv (if not already logging an error)
            if filepath != ERRORS_LOG:
                self.log_error(
                    module="csv_logger",
                    function_name="_append_row",
                    severity="high",
                    error_message=f"Failed to append row to {filepath}: {e}"
                )
            return False
    
    def _hash_text(self, text):
        """Generate hash of text for deduplication"""
        if not text:
            return ""
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
    
    def log_social_post(self, platform, store_data, offer_data, status, 
                       post_id=None, error_code=None, error_message=None,
                       retry_count=0, dry_run=False, image_url=None, skip_reason=None):
        """
        Log social media post attempt
        
        Args:
            platform: "facebook" or "instagram"
            store_data: Dict with store information
            offer_data: Dict with offer information
            status: "success", "failed", or "skipped"
            post_id: Graph API post ID (if successful)
            error_code: Error code (if failed)
            error_message: Error message (if failed)
            retry_count: Number of retries
            dry_run: Whether this was a dry run
            image_url: Public URL of the image
            skip_reason: Reason for skipping (if status="skipped")
        """
        # If skipped, use skip_reason as error_message
        if status == "skipped" and skip_reason:
            error_message = skip_reason
        
        row = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform,
            "store_id": store_data.get("Store_ID", store_data.get("store_id", "")),
            "store_display_name": store_data.get("store_display_name", ""),
            "offer_id": offer_data.get("Image_Name", offer_data.get("image_name", "")),
            "offer_title": offer_data.get("Offer_Title", offer_data.get("offer_title", offer_data.get("content_title", ""))),
            "valid_from": offer_data.get("Valid_From", offer_data.get("valid_from", offer_data.get("start_date", ""))),
            "valid_till": offer_data.get("Valid_till", offer_data.get("valid_till", offer_data.get("end_date", ""))),
            "post_type": "photo",
            "caption_hash": self._hash_text(offer_data.get("Offer_Title", offer_data.get("offer_title", offer_data.get("content_title", "")))),
            "image_url": image_url or "",
            "facebook_page_id": store_data.get("facebook_page_id", ""),
            "instagram_business_account_id": store_data.get("instagram_business_account_id", ""),
            "post_id": post_id or "",
            "status": status,
            "error_code": error_code or "",
            "error_message": error_message or "",
            "retry_count": retry_count,
            "dry_run": "true" if dry_run else "false"
        }
        
        return self._append_row(SOCIAL_POSTS_LOG, SOCIAL_POSTS_SCHEMA, row)
    
    def log_error(self, module, function_name, severity, error_message,
                 store_id=None, entity_type=None, entity_id=None,
                 error_code=None, raw_error=None, action_taken=None):
        """
        Log error to central error registry
        
        Args:
            module: "social", "reviews", "website", "scheduler", etc.
            function_name: Name of function where error occurred
            severity: "low", "medium", "high", "critical"
            error_message: Human-readable error message
            store_id: Store ID (if applicable)
            entity_type: "post", "review", "page", "website", "api"
            entity_id: ID of entity that failed
            error_code: Error code (if available)
            raw_error: Raw error object/message
            action_taken: What action was taken (retry, skip, alert, etc.)
        """
        # Get stack trace
        stack = traceback.format_exc() if raw_error else ""
        
        row = {
            "timestamp": datetime.now().isoformat(),
            "module": module,
            "function_name": function_name,
            "store_id": store_id or "",
            "entity_type": entity_type or "",
            "entity_id": entity_id or "",
            "severity": severity,
            "error_code": error_code or "",
            "error_message": error_message,
            "raw_error": str(raw_error) if raw_error else "",
            "stack_trace": stack,
            "action_taken": action_taken or "",
            "resolved": "false"
        }
        
        return self._append_row(ERRORS_LOG, ERRORS_SCHEMA, row)
    
    def log_website_build(self, build_id, trigger, status, duration_seconds=0,
                         pages_generated=0, offers_processed=0, stores_processed=0,
                         error_count=0, warning_count=0, git_commit=None, deployed=False):
        """
        Log website build attempt
        
        Args:
            build_id: Unique build identifier
            trigger: "manual", "scheduled", "github_action", "api"
            status: "success", "failed", "partial"
            duration_seconds: Build duration
            pages_generated: Number of pages generated
            offers_processed: Number of offers processed
            stores_processed: Number of stores processed
            error_count: Number of errors
            warning_count: Number of warnings
            git_commit: Git commit hash
            deployed: Whether build was deployed
        """
        row = {
            "timestamp": datetime.now().isoformat(),
            "build_id": build_id,
            "trigger": trigger,
            "status": status,
            "duration_seconds": duration_seconds,
            "pages_generated": pages_generated,
            "offers_processed": offers_processed,
            "stores_processed": stores_processed,
            "error_count": error_count,
            "warning_count": warning_count,
            "git_commit": git_commit or "",
            "deployed": "true" if deployed else "false"
        }
        
        return self._append_row(WEBSITE_BUILD_LOG, WEBSITE_BUILD_SCHEMA, row)
    
    def log_review(self, review_id, store_id, store_display_name, platform, rating,
                  reviewer_name, review_text, review_date, reply_text=None,
                  reply_status="pending", reply_date=None, reply_mode=None,
                  escalated=False, escalation_reason=None, processed=False):
        """
        Log review (new or updated)
        
        Args:
            review_id: Unique review identifier
            store_id: Store ID
            store_display_name: Store display name
            platform: "google", "facebook", etc.
            rating: Rating (1-5)
            reviewer_name: Reviewer first name only
            review_text: Review text
            review_date: Date of review
            reply_text: Reply text (if replied)
            reply_status: "pending", "replied", "skipped"
            reply_date: Date of reply
            reply_mode: "auto", "manual", "template"
            escalated: Whether review was escalated
            escalation_reason: Reason for escalation
            processed: Whether review has been processed
        """
        row = {
            "review_id": review_id,
            "store_id": store_id,
            "store_display_name": store_display_name,
            "platform": platform,
            "rating": rating,
            "reviewer_name": reviewer_name,
            "review_text": review_text,
            "review_language": "",  # TODO: Add language detection
            "review_date": review_date,
            "reply_text": reply_text or "",
            "reply_status": reply_status,
            "reply_date": reply_date or "",
            "reply_mode": reply_mode or "",
            "escalated": "true" if escalated else "false",
            "escalation_reason": escalation_reason or "",
            "processed": "true" if processed else "false",
            "last_updated": datetime.now().isoformat()
        }
        
        return self._append_row(REVIEWS_LOG, REVIEWS_SCHEMA, row)


# Global logger instance
logger = CSVLogger()


# Convenience functions
def log_social_post(*args, **kwargs):
    """Log social media post"""
    return logger.log_social_post(*args, **kwargs)


def log_error(*args, **kwargs):
    """Log error"""
    return logger.log_error(*args, **kwargs)


def log_website_build(*args, **kwargs):
    """Log website build"""
    return logger.log_website_build(*args, **kwargs)


def log_review(*args, **kwargs):
    """Log review"""
    return logger.log_review(*args, **kwargs)
