/**
 * PlantDoc i18n - Lightweight client-side translation manager
 * Supports English (en) and Kiswahili (sw)
 * Uses localStorage for persistence + server-side session as backup
 */

const PlantDocI18n = (function () {
  const STORAGE_KEY = 'plantdoc_lang';
  const DEFAULT_LANG = 'en';
  const SUPPORTED = ['en', 'sw'];

  let _translations = {};
  let _currentLang = DEFAULT_LANG;

  /** Flatten nested JSON keys: { nav: { home: "Home" } } → { "nav.home": "Home" } */
  function flatten(obj, prefix) {
    prefix = prefix || '';
    return Object.keys(obj).reduce(function (acc, key) {
      var fullKey = prefix ? prefix + '.' + key : key;
      if (typeof obj[key] === 'object' && obj[key] !== null && !Array.isArray(obj[key])) {
        Object.assign(acc, flatten(obj[key], fullKey));
      } else {
        acc[fullKey] = obj[key];
      }
      return acc;
    }, {});
  }

  /** Get a translation by dot-notation key, fallback to key itself */
  function t(key) {
    return _translations[key] || key;
  }

  /** Apply translations to all [data-i18n] elements in the DOM */
  function applyTranslations() {
    // Text content
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var key = el.getAttribute('data-i18n');
      var translation = t(key);
      if (translation !== key) {
        el.textContent = translation;
      }
    });

    // Placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-placeholder');
      var translation = t(key);
      if (translation !== key) {
        el.placeholder = translation;
      }
    });

    // Title attributes
    document.querySelectorAll('[data-i18n-title]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-title');
      var translation = t(key);
      if (translation !== key) {
        el.title = translation;
      }
    });

    // HTML content (for elements needing HTML, e.g. with icons preserved)
    document.querySelectorAll('[data-i18n-html]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-html');
      var translation = t(key);
      if (translation !== key) {
        // preserve inner HTML structure - only update text nodes
        el.childNodes.forEach(function (node) {
          if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
            node.textContent = ' ' + translation + ' ';
          }
        });
      }
    });

    // Update lang attribute on html element
    document.documentElement.lang = _currentLang === 'sw' ? 'sw' : 'en';

    // Update active state on switcher buttons
    document.querySelectorAll('[data-lang-btn]').forEach(function (btn) {
      var btnLang = btn.getAttribute('data-lang-btn');
      if (btnLang === _currentLang) {
        btn.classList.remove('btn-outline-light');
        btn.classList.add('btn-light');
      } else {
        btn.classList.remove('btn-light');
        btn.classList.add('btn-outline-light');
      }
    });
  }

  /** Load translation JSON file and apply */
  function loadAndApply(lang) {
    var url = '/static/i18n/' + lang + '.json?v=' + Date.now();
    return fetch(url)
      .then(function (res) {
        if (!res.ok) throw new Error('Failed to load ' + lang + '.json');
        return res.json();
      })
      .then(function (data) {
        _translations = flatten(data);
        _currentLang = lang;
        applyTranslations();
      })
      .catch(function (err) {
        console.warn('[i18n] Could not load', lang, '-', err.message);
        // Silently fall back - keep current translations
      });
  }

  /** Switch to a new language, persist it, and sync server session */
  function switchLang(lang) {
    if (!SUPPORTED.includes(lang)) return;
    localStorage.setItem(STORAGE_KEY, lang);
    loadAndApply(lang).then(function () {
      // Sync the server-side session in background (non-blocking)
      fetch('/set-lang/' + lang, { method: 'GET', credentials: 'same-origin' }).catch(function () {});
    });
  }

  /** Read saved language: localStorage → server hint → default */
  function detectLang() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored && SUPPORTED.includes(stored)) return stored;

    // Fall back to server-injected hint (set via data-server-lang on <html>)
    var serverLang = document.documentElement.getAttribute('data-server-lang');
    if (serverLang && SUPPORTED.includes(serverLang)) return serverLang;

    return DEFAULT_LANG;
  }

  /** Initialise on DOMContentLoaded */
  function init() {
    var lang = detectLang();
    // Always load to ensure translations are applied even if lang=en
    loadAndApply(lang);
  }

  // Public API
  return {
    init: init,
    switchLang: switchLang,
    t: t,
    getCurrentLang: function () { return _currentLang; }
  };
})();

document.addEventListener('DOMContentLoaded', PlantDocI18n.init);
