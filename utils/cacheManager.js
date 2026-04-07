// ════════════════════════════════════════════
// utils/cacheManager.js
// Local cache management for SEO data and build optimization
// ════════════════════════════════════════════

const fs = require('fs');
const path = require('path');

class CacheManager {
  constructor(cacheDir = 'build/data/cache') {
    this.cacheDir = cacheDir;
    this.ensureCacheDir();
  }

  ensureCacheDir() {
    if (!fs.existsSync(this.cacheDir)) {
      fs.mkdirSync(this.cacheDir, { recursive: true });
      console.log(`📁 Created cache directory: ${this.cacheDir}`);
    }
  }

  getCachePath(key) {
    return path.join(this.cacheDir, `${key}.json`);
  }

  has(key) {
    const cachePath = this.getCachePath(key);
    return fs.existsSync(cachePath);
  }

  get(key) {
    if (!this.has(key)) {
      return null;
    }

    try {
      const cachePath = this.getCachePath(key);
      const data = fs.readFileSync(cachePath, 'utf8');
      return JSON.parse(data);
    } catch (error) {
      console.error(`❌ Error reading cache ${key}:`, error);
      return null;
    }
  }

  set(key, data, ttl = 5 * 60 * 1000) { // 5 minutes default TTL
    try {
      const cachePath = this.getCachePath(key);
      const cacheData = {
        data,
        timestamp: Date.now(),
        ttl
      };
      
      fs.writeFileSync(cachePath, JSON.stringify(cacheData, null, 2), 'utf8');
      console.log(`💾 Cached data: ${key} (${Object.keys(data).length} items)`);
    } catch (error) {
      console.error(`❌ Error writing cache ${key}:`, error);
    }
  }

  isValid(key) {
    if (!this.has(key)) {
      return false;
    }

    try {
      const cachePath = this.getCachePath(key);
      const data = fs.readFileSync(cachePath, 'utf8');
      const cacheData = JSON.parse(data);
      
      const now = Date.now();
      const isValid = cacheData.timestamp + cacheData.ttl > now;
      
      if (!isValid) {
        console.log(`⏰ Cache expired: ${key}`);
        return false;
      }
      
      return true;
    } catch (error) {
      console.error(`❌ Error validating cache ${key}:`, error);
      return false;
    }
  }

  clear(key) {
    const cachePath = this.getCachePath(key);
    try {
      fs.unlinkSync(cachePath);
      console.log(`🗑️ Cleared cache: ${key}`);
    } catch (error) {
      console.error(`❌ Error clearing cache ${key}:`, error);
    }
  }

  clearAll() {
    try {
      if (fs.existsSync(this.cacheDir)) {
        const files = fs.readdirSync(this.cacheDir);
        for (const file of files) {
          if (file.endsWith('.json')) {
            fs.unlinkSync(path.join(this.cacheDir, file));
          }
        }
        console.log('🗑️ Cleared all cache files');
      }
    } catch (error) {
      console.error('❌ Error clearing cache directory:', error);
    }
  }
}

module.exports = CacheManager;
