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
  GAS_WEBHOOK_URL: 'https://script.google.com/macros/s/AKfycbwqtspGIuXR5uTs1roJlYRjysm1i4421f41ygDch7WGWatVCp1lXl0a7FrAOMCxl_cfDA/exec',

  // Platform character limits — defaults (overridden by injected ARIS_PLATFORM_LIMITS)
  PLATFORM_LIMITS: { facebook: 63206, instagram: 2200, google: 1500 },
};

// ── Build-time data injection ──────────────────────────────────────────
// These are injected at build time by build/build.py to eliminate
// authenticated GitHub API calls from the browser.
window.SALON_STORES_CACHE = [{"id": "N78", "name": "JP Nagar 5th Phase", "slug": "jpnagar5thphase"}, {"id": "N45", "name": "Nagavara", "slug": "nagavara"}, {"id": "N36", "name": "Ayyappa Nagar", "slug": "ayyappanagar"}, {"id": "N05", "name": "Frazer Town", "slug": "frazertown"}, {"id": "N43", "name": "Hennur", "slug": "hennur"}];
window.STORE_EMAIL_MAP = {"jpnagar2.naturals@gmail.com": "N78", "naturalsnagavara@gmail.com": "N45", "naturalsdevasandra@gmail.com": "N36", "frazertown.naturals@gmail.com": "N05", "naturalshennur@gmail.com": "N43"};
window.STORE_OWNER_SET = ["iris.digihelp+sandesh@gmail.com", "iris.digihelp@gmail.com", "sandesh.aristycoon@gmail.com", "sophiaaxon@gmail.com"];
window.ADMIN_CAMPAIGN_ACCESS = ["sophiaaxon@gmail.com", "iris.digihelp@gmail.com", "sandesh.aristycoon@gmail.com", "iris.digihelp+sandesh@gmail.com"];
window.ADMIN_ALLOWED_EMAILS = ["frazertown.naturals@gmail.com", "iris.digihelp+sandesh@gmail.com", "iris.digihelp@gmail.com", "jpnagar2.naturals@gmail.com", "naturalsdevasandra@gmail.com", "naturalshennur@gmail.com", "naturalsnagavara@gmail.com", "sandesh.aristycoon@gmail.com", "sophiaaxon@gmail.com"];
window.CAMPAIGN_TYPES_CACHE = ["announcement", "offer"];
window.ARIS_PLATFORM_LIMITS = {"facebook": 63206, "instagram": 2200, "google": 1500};
window.REVIEW_SUMMARY = {"total": 168, "replied": 165, "avgStars": 4.7, "perStore": [{"store": "Ayyappa Nagar", "id": "N36", "total": 45, "replied": 45, "avgStars": 4.9}, {"store": "Frazer Town", "id": "N05", "total": 40, "replied": 40, "avgStars": 4.6}, {"store": "Hennur", "id": "N43", "total": 36, "replied": 36, "avgStars": 4.9}, {"store": "JP Nagar 5th Phase", "id": "N78", "total": 3, "replied": 2, "avgStars": 1.0}, {"store": "Nagavara", "id": "N45", "total": 44, "replied": 42, "avgStars": 4.8}]};
