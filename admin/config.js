/**
 * Naturals Admin Panel — Configuration
 *
 * ⚠️  NEVER store secrets/tokens here. This file is in the source repo.
 *      The DISPATCH_TOKEN placeholder is replaced at deploy time by
 *      .github/workflows/deploy_admin.yml using GitHub Secrets.
 *
 * See docs/OPS_PLAYBOOK_FB_TOKENS.md and Naturals_Admin_Panel_Spec_v1.docx
 */
const ADMIN_CONFIG = {
  // Values below are injected at deploy time from GitHub Secrets
  GOOGLE_CLIENT_ID: '816755094343-1ibdm0ecuhg90b50090rjoohkrlr9pd5.apps.googleusercontent.com',
  IMAGEKIT_PUBLIC_KEY: 'public_FS+yTbkgglmRSrKu9hBg4Lm04/8=',
  IMAGEKIT_URL_ENDPOINT: 'https://ik.imagekit.io/naturals',

  // GitHub — repo where the verification workflow lives
  GITHUB_OWNER: 'naturals-blr',
  GITHUB_REPO: 'naturals-ops',

  // Verification workflow — called from browser with Google ID token
  // The admin JS uses the DISPATCH_TOKEN placeholder which gets replaced
  // at deploy time by deploy_admin.yml (never committed to source)
  VERIFY_WORKFLOW: 'verify_and_dispatch.yml',
  DISPATCH_TOKEN: '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',

  // Allowed email domain for Google OAuth sign-in
  // Set to empty string to allow any email (real auth is server-side in verify_and_dispatch.yml)
  ALLOWED_DOMAIN: '',

  // Authorised emails (any email can trigger auth; real access control is server-side)
  AUTHORIZED_EMAILS: [],

  // Platform character limits — injected at deploy time from aris_global_settings
  // Defaults used as fallback if settings not yet loaded
  PLATFORM_LIMITS: { facebook: 63206, instagram: 2200, google: 1500 },

  // Production base URL for building offer links (injected at deploy time)
  PRODUCTION_BASE_URL: 'https://naturalsprime.in',
};
