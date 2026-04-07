# ════════════════════════════════════════════
# utils/cacheManager.py
# Local cache management for SEO data and build optimization
# ════════════════════════════════════════════

import json
import os
import time
from pathlib import Path

class CacheManager:
    def __init__(self, cache_dir='build/data'):
        """Use main data directory as single source of truth"""
        self.cache_dir = cache_dir
        self.ensure_cache_dir()
    
    def ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
            print(f"📁 Created data directory: {self.cache_dir}")
    
    def get_cache_path(self, key):
        """Get the full path for a cache key - add .cache.json for metadata"""
        return os.path.join(self.cache_dir, f"{key}.cache.json")
    
    def get_data_path(self, key):
        """Get the actual data file path"""
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def has(self, key):
        """Check if cache key exists"""
        return os.path.exists(self.get_cache_path(key))
    
    def has_data(self, key):
        """Check if data file exists"""
        return os.path.exists(self.get_data_path(key))
    
    def get(self, key):
        """Get cached data"""
        if not self.has(key):
            return None
        
        try:
            cache_path = self.get_cache_path(key)
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check if cache is still valid
            if time.time() < cache_data['timestamp'] + cache_data['ttl']:
                return cache_data['data']
            else:
                print(f"⏰ Cache expired: {key}")
                return None
        except Exception as e:
            print(f"❌ Error reading cache {key}: {e}")
            return None
    
    def set(self, key, data, ttl=5*60*1000):  # 5 minutes default TTL
        """Set cached data - save both data and metadata"""
        try:
            # Save the actual data file
            data_path = self.get_data_path(key)
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Save cache metadata
            cache_path = self.get_cache_path(key)
            cache_data = {
                'data': data,
                'timestamp': time.time(),
                'ttl': ttl
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Cached data: {key} ({len(data) if isinstance(data, (list, dict)) else 'single'} items")
        except Exception as e:
            print(f"❌ Error writing cache {key}: {e}")
    
    def is_valid(self, key):
        """Check if cache is valid (exists and not expired)"""
        if not self.has(key):
            return False
        
        try:
            cache_path = self.get_cache_path(key)
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            return time.time() < cache_data['timestamp'] + cache_data['ttl']
        except Exception as e:
            print(f"❌ Error validating cache {key}: {e}")
            return False
    
    def clear(self, key):
        """Clear specific cache key"""
        cache_path = self.get_cache_path(key)
        data_path = self.get_data_path(key)
        
        try:
            if os.path.exists(cache_path):
                os.remove(cache_path)
            if os.path.exists(data_path):
                os.remove(data_path)
            print(f"🗑️ Cleared cache: {key}")
        except Exception as e:
            print(f"❌ Error clearing cache {key}: {e}")
    
    def clear_all(self):
        """Clear all cache files"""
        try:
            if os.path.exists(self.cache_dir):
                for file in os.listdir(self.cache_dir):
                    if file.endswith('.cache.json') or file.endswith('.json'):
                        os.remove(os.path.join(self.cache_dir, file))
                print("🗑️ Cleared all cache files")
        except Exception as e:
            print(f"❌ Error clearing cache directory: {e}")
    
    def force_refresh(self, key):
        """Force refresh by clearing cache for specific key"""
        self.clear(key)
        print(f"🔄 Forced cache refresh for: {key}")
