/**
 * Naturals Admin Panel — Configuration
 *
 * ⚠️  NO tokens or secrets here. Data (stores, campaigns, settings) is
 *      injected at build time by build/build.py into admin/config.js
 *      in the output directory. See the window.*_CACHE globals below.
 *
 * See docs/OPS_PLAYBOOK_FB_TOKENS.md and Naturals_Admin_Panel_Spec_v1.docx
 */
const ADMIN_CONFIG = {
  // Google OAuth — public client ID
  GOOGLE_CLIENT_ID: '816755094343-1ibdm0ecuhg90b50090rjoohkrlr9pd5.apps.googleusercontent.com',

  // Production base URL for building offer links (injected at deploy time)
  PRODUCTION_BASE_URL: 'https://naturalsprime.in',

  // Google Apps Script Web App URL for the relay (Option A - Primary)
  GAS_WEBHOOK_URL: '',

  // Platform character limits — defaults (overridden by injected ARIS_PLATFORM_LIMITS)
  PLATFORM_LIMITS: { facebook: 63206, instagram: 2200, google: 1500 },
};

// ── Build-time data injection ──────────────────────────────────────────
// These are injected at build time by build/build.py to eliminate
// authenticated GitHub API calls from the browser.
window.SALON_STORES_CACHE = [{"id": "N78", "name": "JP Nagar 5th Phase", "slug": "jpnagar5thphase"}, {"id": "N45", "name": "Nagavara", "slug": "nagavara"}, {"id": "N36", "name": "Ayyappa Nagar", "slug": "ayyappanagar"}, {"id": "N05", "name": "Frazer Town", "slug": "frazertown"}, {"id": "N43", "name": "Hennur", "slug": "hennur"}];
window.STORE_EMAIL_MAP = {};
window.STORE_OWNER_SET = ["iris.digihelp+sandesh@gmail.com", "iris.digihelp@gmail.com", "sandesh.aristycoon@gmail.com", "sophiaaxon@gmail.com"];
window.CAMPAIGN_TYPES_CACHE = ["announcement", "offer"];
window.ARIS_PLATFORM_LIMITS = {"facebook": 63206, "instagram": 2200, "google": 1500};
window.REVIEW_SUMMARY = {"total": 2146, "replied": 10, "avgStars": 5, "perStore": [{"store": "Ayyappa Nagar", "id": "N36", "total": 383, "replied": 2, "avgStars": 5.0}, {"store": "Frazer Town", "id": "N05", "total": 418, "replied": 2, "avgStars": 5.0}, {"store": "Hennur", "id": "N43", "total": 448, "replied": 2, "avgStars": 5.0}, {"store": "JP Nagar 5th Phase", "id": "N78", "total": 396, "replied": 2, "avgStars": 5.0}, {"store": "Nagavara", "id": "N45", "total": 465, "replied": 2, "avgStars": 5.0}, {"store": "Store 11456061934238062921", "id": "", "total": 10, "replied": 0, "avgStars": 5.0}, {"store": "Store 5858391068390788403", "id": "", "total": 26, "replied": 0, "avgStars": 5.0}]};
