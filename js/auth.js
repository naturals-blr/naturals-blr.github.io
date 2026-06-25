(function(){
var AUTH_STORAGE_KEY = 'naturals_admin_token';
var currentToken = null;
var currentUser = null;

function isProduction() {
  return window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
}

function isAdminPath() {
  return window.location.pathname.startsWith('/admin/');
}

function getStoredToken() {
  try { return localStorage.getItem(AUTH_STORAGE_KEY); } catch(e) { return null; }
}

function storeToken(t) {
  try { localStorage.setItem(AUTH_STORAGE_KEY, t); } catch(e) {}
}

function clearToken() {
  try { localStorage.removeItem(AUTH_STORAGE_KEY); } catch(e) {}
  currentToken = null;
  currentUser = null;
}

function decodeToken(t) {
  try {
    var parts = t.split('.');
    return JSON.parse(atob(parts[1].replace(/-/g,'+').replace(/_/g,'/')));
  } catch(e) { return null; }
}

function isTokenValid(t) {
  var p = decodeToken(t);
  if (!p) return false;
  if (p.exp && Date.now() >= p.exp * 1000) return false;
  var allowed = window.ADMIN_ALLOWED_EMAILS || [];
  if (allowed.length > 0 && !allowed.includes((p.email || '').toLowerCase())) return false;
  return true;
}

function restoreSession() {
  var stored = getStoredToken();
  if (stored && isTokenValid(stored)) {
    currentToken = stored;
    currentUser = decodeToken(stored);
    return true;
  }
  return false;
}

function loadGSIScript(callback) {
  if (window.google && window.google.accounts) { if (callback) callback(); return; }
  var s = document.createElement('script');
  s.src = 'https://accounts.google.com/gsi/client';
  s.async = true;
  s.defer = true;
  s.onload = callback;
  document.head.appendChild(s);
}

function showAuthScreen(containerId, onAuth) {
  var c = document.getElementById(containerId);
  if (!c) return;
  c.style.position = 'fixed';
  c.style.top = '0';
  c.style.left = '0';
  c.style.width = '100%';
  c.style.height = '100%';
  c.style.zIndex = '9999';
  c.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f3f4f6"><div style="background:#fff;border-radius:1rem;padding:3rem 2.5rem;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.08);max-width:400px;width:100%"><div style="font-size:2.5rem;margin-bottom:.5rem">&#x1F33F;</div><h1 style="font-size:1.5rem;font-weight:700;color:#166534;margin-bottom:.25rem">Naturals Admin</h1><p style="font-size:.875rem;color:#6b7280;margin-bottom:.25rem">Sign in with your Google account</p><p style="font-size:.75rem;color:#9ca3af;margin-bottom:1.5rem" id="auth-status">Loading sign-in...</p><div id="g_id_onload" data-client_id="816755094343-1ibdm0ecuhg90b50090rjoohkrlr9pd5.apps.googleusercontent.com" data-context="signin" data-callback="__naturalsAuthCallback" data-auto_select="false"></div><div class="g_id_signin" data-type="standard" data-shape="rectangular" data-theme="outline" data-text="signin_with" data-size="large"></div><p style="font-size:.75rem;color:#dc2626;margin-top:.75rem;min-height:1.25rem" id="auth-error-msg"></p></div></div>';
  loadGSIScript(function() {
    var statusEl = document.getElementById('auth-status');
    if (statusEl) statusEl.textContent = 'Sign in with your Google account';
  });

  window.__naturalsAuthCallback = function(response) {
    var token = response.credential;
    var payload = decodeToken(token);
    if (!payload || !payload.email) {
      var errEl = document.getElementById('auth-error-msg');
      if (errEl) errEl.textContent = 'Failed to parse credentials';
      return;
    }
    var allowed = window.ADMIN_ALLOWED_EMAILS || [];
    var email = payload.email.toLowerCase();
    if (allowed.length > 0 && !allowed.includes(email)) {
      var errEl2 = document.getElementById('auth-error-msg');
      if (errEl2) errEl2.textContent = 'Access denied: ' + email + ' is not authorized.';
      return;
    }
    currentToken = token;
    currentUser = payload;
    storeToken(token);
    c.style.display = 'none';
    if (onAuth) onAuth(payload);
  };
}

window.Auth = {
  getToken: function() { return currentToken; },
  getUser: function() { return currentUser; },
  isAuthenticated: function() { return !!currentToken; },

  protect: function(containerId, onAuth) {
    // Only enforce auth in production on /admin/* pages
    if (!isProduction() || !isAdminPath()) {
      if (onAuth) onAuth(null);
      return;
    }
    if (restoreSession()) {
      if (onAuth) onAuth(currentUser);
      return;
    }
    showAuthScreen(containerId, onAuth);
  },

  signOut: function() {
    clearToken();
    window.location.reload();
  }
};
})();
