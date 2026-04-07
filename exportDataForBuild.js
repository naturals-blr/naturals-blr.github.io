#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');
const { loadConfig, getMasterLoader } = require('../config/masterLoader');

// ── CONFIGURATION ──────────────────────────────────────────────
const OUTPUT_DIR = path.join(__dirname, 'data');
const CONFIG_DIR = path.join(__dirname, '..', 'config');

const OUTPUT_FILES = {
  stores: path.join(OUTPUT_DIR, 'stores.json'),
  services: path.join(OUTPUT_DIR, 'services.json'),
  campaigns: path.join(OUTPUT_DIR, 'campaigns.json'),
  stylists: path.join(OUTPUT_DIR, 'stylists.json'),
  reviews: path.join(OUTPUT_DIR, 'reviews.json'),
  careers: path.join(OUTPUT_DIR, 'careers.json'),
  brand: path.join(OUTPUT_DIR, 'aris_global_settings.json'),
  review_response_templates: path.join(OUTPUT_DIR, 'review_response_templates.json'),
  trainings: path.join(OUTPUT_DIR, 'trainings.json'),
  page_seo_config: path.join(OUTPUT_DIR, 'page_seo_config.json')
};

const CONFIG_FILES = {
  stores: path.join(CONFIG_DIR, 'stores.yml'),
  services: path.join(CONFIG_DIR, 'services.yml'),
  campaigns: path.join(CONFIG_DIR, 'campaigns.yml'),
  stylists: path.join(CONFIG_DIR, 'stylists.yml'),
  reviews: path.join(CONFIG_DIR, 'reviews.yml'),
  careers: path.join(CONFIG_DIR, 'careers.yml'),
  brand: path.join(CONFIG_DIR, 'aris_global_settings.yml'),
  review_response_templates: path.join(CONFIG_DIR, 'review_response_templates.yml'),
  trainings: path.join(CONFIG_DIR, 'trainings.yml')
};

const MAX_RETRIES = 3;
const RETRY_DELAY = 2000;

// ── HELPERS ────────────────────────────────────────────────────

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function withRetry(fn, label) {
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await fn();
    } catch (err) {
      console.warn(`⚠️ ${label} failed (attempt ${attempt}/${MAX_RETRIES})`);

      if (attempt === MAX_RETRIES) throw err;

      await sleep(RETRY_DELAY * attempt);
    }
  }
}

function ensureOutputDir() {
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }
}

function writeJson(filepath, data) {
  fs.writeFileSync(filepath, JSON.stringify(data, null, 2), 'utf-8');
  const sizeKb = (fs.statSync(filepath).size / 1024).toFixed(1);
  console.log(`  ✅ Written: ${path.basename(filepath)} (${sizeKb} KB)`);
}

function writeYaml(filepath, data) {
  fs.writeFileSync(filepath, yaml.dump(data, { indent: 2, lineWidth: 120 }), 'utf-8');
  const sizeKb = (fs.statSync(filepath).size / 1024).toFixed(1);
  console.log(`  ✅ Updated: ${path.basename(filepath)} (${sizeKb} KB)`);
}

// ── TRANSFORMERS ───────────────────────────────────────────────

function transformStoreForBuild(store) {
  const shortIdFromStoreId = store.id ? store.id.replace(/^Store_/i, '') : '';

  const transformed = {
    Store_ID: store.id,
    brand_store_name: store.name || 'Unknown Store',
    store_id_short: store.short_name || shortIdFromStoreId,
    store_display_name: store.display_name || store.short_name || shortIdFromStoreId,
    store_area: store?.area || '',
    Active_Status: store?.active ? 'Yes' : 'No',

    Address_Full: store?.address?.line1 || '',
    Address_Line_2: store?.address?.line2 || '',
    Address_City: store?.address?.city || '',
    Address_State: store?.address?.state || '',
    Pincode: store?.address?.pincode || '',
    Google_Maps_URL: store?.address?.google_maps_url || '',

    Google_Location_ID: store?.google?.location_id || '',
    google_review_link: store?.google?.review_link || '',
    Google_Place_ID: store?.google?.place_id || '',

    phone_mobile: store?.contact?.phone || '',
    Phone_Raw: store?.contact?.phone || '',
    phone_whatsapp: store?.contact?.whatsapp || '',
    phone_landline: store?.contact?.landline || '',
    Email: store?.contact?.email || '',

    Appointment_URL: store?.booking?.appointment_url || '',
    Booking_Platform: store?.booking?.booking_platform || '',

    Instagram_ID: store?.social?.instagram || '',
    Instagram_URL: store?.social?.instagram_url || '',
    Facebook_ID: store?.social?.facebook || '',
    Facebook_URL: store?.social?.facebook_url || '',
    facebook_page_id: store?.social?.facebook_page_id || '',
    instagram_business_account_id: store?.social?.instagram_business_account_id || '',

    Manager_Name: store?.team?.manager_name || '',
    Manager_WhatsApp: store?.team?.manager_whatsapp || ''
  };

  if (store.raw_data) {
    Object.keys(store.raw_data).forEach(key => {
      if (!(key in transformed)) {
        transformed[key] = store.raw_data[key];
      }
    });
  }

  transformed.Store_Page_URL = `stores/${transformed.store_id_short.toLowerCase()}.html`;

  return transformed;
}

// ── SAFE LOADER ────────────────────────────────────────────────

async function safeLoad(loader, key) {
  try {
    const forceRefresh = process.env.FORCE_REFRESH === 'true';
    const data = await withRetry(
      () => loader.getWebsiteData(key, { forceRefresh: forceRefresh, validateData: false }),
      key
    );

    console.log(`   ✅ Loaded ${data.length} ${key}`);
    return data;

  } catch (err) {
    console.error(`   ❌ Failed to load ${key}, using empty fallback`);
    return [];
  }
}

async function safeLoadTemplates(loader) {
  try {
    const forceRefresh = process.env.FORCE_REFRESH === 'true';
    const templates = await withRetry(
      () => loader.loadReviewTemplates({ forceRefresh: forceRefresh, validateData: false }),
      'review_response_templates'
    );

    const templateCount = Object.keys(templates).length;
    const totalTemplates = Object.values(templates).reduce((sum, arr) => sum + arr.length, 0);
    console.log(`   ✅ Loaded ${templateCount} template categories (${totalTemplates} total templates)`);
    return templates;

  } catch (err) {
    console.error(`   ❌ Failed to load review_response_templates, using empty fallback`);
    return {};
  }
}

// ── MAIN ───────────────────────────────────────────────────────

async function exportDataForBuild() {
  let cachedTrainings = null; // Declare at function scope
  
  console.log('\n═══════════════════════════════════════════════════════════');
  console.log('  EXPORT DATA FOR PYTHON BUILD (Optimized)');
  console.log('═══════════════════════════════════════════════════════════\n');

  try {
    const loader = getMasterLoader();
    ensureOutputDir();

    // ── STORES + BRAND ─────────────────────────────────────────
    console.log('📋 Loading core config...');
    
    const forceRefresh = process.env.FORCE_REFRESH === 'true';
    if (forceRefresh) {
      console.log('🔄 FORCE_REFRESH=true - fetching fresh data from Google Sheets');
    } else {
      console.log('💾 Using cached data - skipping Google Sheets fetch');
    }

    const { stores, brand } = await withRetry(
      () => loader.loadConfig({
        forceRefresh: forceRefresh,
        fallbackToYaml: true,
        validateData: true
      }),
      'loadConfig'
    );

    console.log(`   ✅ Loaded ${stores.length} stores`);
    if (brand) {
      console.log(`   ✅ Loaded brand settings`);
    } else {
      console.warn(`   ⚠️  Brand settings not loaded`);
    }

    const storesForBuild = stores.map(transformStoreForBuild);

    writeJson(OUTPUT_FILES.stores, storesForBuild);

    // ── PARALLEL LOAD ──────────────────────────────────────────
    console.log('\n📋 Loading website data (parallel)...');

    const [
      services,
      campaigns,
      stylists,
      reviews,
      careers,
      trainings,
      templates,
      page_seo_config
    ] = await Promise.all([
      safeLoad(loader, 'services'),
      safeLoad(loader, 'campaigns'),
      safeLoad(loader, 'stylists'),
      safeLoad(loader, 'reviews'),
      safeLoad(loader, 'careers'),
      safeLoad(loader, 'trainings'),
      safeLoadTemplates(loader),
      safeLoad(loader, 'page_seo_config')
    ]);

    // ── WRITE FILES ────────────────────────────────────────────
    writeJson(OUTPUT_FILES.services, services);
    writeJson(OUTPUT_FILES.campaigns, campaigns);
    writeJson(OUTPUT_FILES.stylists, stylists);
    writeJson(OUTPUT_FILES.reviews, reviews);
    writeJson(OUTPUT_FILES.careers, careers);
    writeJson(OUTPUT_FILES.trainings, trainings);
    writeJson(OUTPUT_FILES.review_response_templates, templates);
    writeJson(OUTPUT_FILES.page_seo_config, page_seo_config);

    // ── WRITE CONFIG YAML FILES ─────────────────────────────
    console.log('\n📝 Updating config YAML files...');
    
    // Transform and write stores.yml
    const storesYaml = {
      stores: storesForBuild.map(store => ({
        id: store.Store_ID,
        name: store.brand_store_name,
        short_name: store.store_id_short,
        display_name: store.store_display_name,
        area: store.local_neighborhood || '',
        active: store.Active_Status === 'Yes',
        address: {
          line1: store.Address_Line_1 || '',
          line2: store.Address_Line_2 || '',
          city: store.Address_City || '',
          state: store.Address_State || '',
          pincode: store.Pincode || '',
          google_maps_url: store.google_maps_url || '',
          google: {
            location_id: store.google_location_id || '',
            review_link: store.google_review_link || '',
            place_id: store.Google_Place_ID || ''
          }
        },
        booking: {
          appointment_url: store.Appointment_URL || '',
          booking_platform: store.Booking_Platform || ''
        },
        contact: {
          phone: store.phone_mobile || '',
          whatsapp: store.phone_whatsapp || '',
          landline: store.phone_landline || '',
          email: store.email || '',
          escalation_email: store.escalation_email || ''
        },
        social: {
          instagram: store.Instagram_ID || '',
          instagram_url: store.Instagram_URL || '',
          facebook: store.Facebook_ID || '',
          facebook_url: store.Facebook_URL || '',
          facebook_page_id: store.facebook_page_id || '',
          instagram_business_account_id: store.instagram_business_account_id || ''
        },
        team: {
          manager_name: store.store_manager_name || '',
          manager_whatsapp: store.escalation_whatsapp || '',
          escalation_contact: store.escalation_contact || '',
          escalation_whatsapp: store.escalation_whatsapp || ''
        }
      }))
    };
    writeYaml(CONFIG_FILES.stores, storesYaml);

    // Write other YAML files
    writeYaml(CONFIG_FILES.services, { services: services });
    writeYaml(CONFIG_FILES.campaigns, { campaigns: campaigns });
    writeYaml(CONFIG_FILES.stylists, { stylists: stylists });
    writeYaml(CONFIG_FILES.reviews, { reviews: reviews });
    writeYaml(CONFIG_FILES.careers, { careers: careers });
    writeYaml(CONFIG_FILES.review_response_templates, { review_response_templates: templates });
    writeYaml(CONFIG_FILES.trainings, { trainings: cachedTrainings || [] });
    
    // Write aris_global_settings with proper nested structure
    if (brand) {
      writeYaml(CONFIG_FILES.brand, brand);
      console.log(`  ✅ Updated: ${path.basename(CONFIG_FILES.brand)} (${(fs.statSync(CONFIG_FILES.brand).size / 1024).toFixed(1)} KB)`);
    } else {
      console.warn('   ⚠️  aris_global_settings not loaded - skipping YAML update');
    }

    // ── VERIFY TRAININGS ────────────────────────────────────────
    console.log('\n📋 Checking static data files...');
    
    // Load trainings through cache system
    try {
      const cacheManager = loader.cacheManager;
      cachedTrainings = await cacheManager.get('trainings');
      
      if (cachedTrainings) {
        writeJson(OUTPUT_FILES.trainings, cachedTrainings);
        console.log('   ✅ trainings.json loaded from cache and written to build/data/');
      } else {
        // Fallback to direct file read
        if (fs.existsSync(OUTPUT_FILES.trainings)) {
          console.log('   ✅ trainings.json exists in build/data/ (direct access)');
        } else {
          console.warn('   ⚠️  trainings.json not found in build/data/ - maintain it manually');
        }
      }
    } catch (err) {
      console.warn('   ⚠️  Trainings cache failed, checking file directly:', err.message);
      if (fs.existsSync(OUTPUT_FILES.trainings)) {
        console.log('   ✅ trainings.json exists in build/data/ (fallback)');
      } else {
        console.warn('   ⚠️  trainings.json not found in build/data/ - maintain it manually');
      }
    }

    // ── SUMMARY ────────────────────────────────────────────────
    console.log('\n═══════════════════════════════════════════════════════════');
    console.log('✅ DATA EXPORT COMPLETE');
    console.log('═══════════════════════════════════════════════════════════\n');

    // ── CACHE INFO ─────────────────────────────────────────────
    const cacheStatus = loader.getCacheStatus();
    console.log('📊 Cache Status:');
    console.log(`   Memory cache: ${cacheStatus.memory?.count || 0}`);
    console.log(`   File cache: ${cacheStatus.file?.count || 0}`);
    console.log(`   Hit rate: ${cacheStatus.stats?.hitRate || '0%'}`);
    console.log('');

  } catch (err) {
    console.error('\n❌ EXPORT FAILED:', err.message);
    process.exit(1);
  }
}

// ── RUN ────────────────────────────────────────────────────────

if (require.main === module) {
  exportDataForBuild();
}

module.exports = { exportDataForBuild };