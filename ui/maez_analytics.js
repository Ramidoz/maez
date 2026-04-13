(function() {
  if (window.__maezAnalyticsLoaded) return;
  window.__maezAnalyticsLoaded = true;

  const API_PATH = '/api/analytics';

  function createId(prefix) {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return prefix + '-' + window.crypto.randomUUID().slice(0, 12);
    }
    return prefix + '-' + Math.random().toString(16).slice(2, 14);
  }

  function readOrCreate(storage, key, prefix) {
    try {
      const current = storage.getItem(key);
      if (current) return current;
      const next = createId(prefix);
      storage.setItem(key, next);
      return next;
    } catch (err) {
      return createId(prefix);
    }
  }

  function cleanText(value, limit) {
    return String(value || '').trim().replace(/\s+/g, ' ').slice(0, limit);
  }

  function normalizePath(value) {
    const raw = cleanText(value || window.location.pathname || '/', 180);
    if (!raw) return '/';
    if (raw.startsWith('/')) return raw.split('?')[0].split('#')[0] || '/';
    try {
      const parsed = new URL(raw, window.location.origin);
      return parsed.pathname || '/';
    } catch (err) {
      return '/';
    }
  }

  function normalizeTarget(value) {
    const raw = cleanText(value, 200);
    if (!raw) return '';
    if (raw.startsWith('/')) return normalizePath(raw);
    try {
      const parsed = new URL(raw, window.location.origin);
      const host = parsed.host.replace(/^www\./, '');
      return (parsed.protocol + '//' + host + (parsed.pathname || '/')).slice(0, 200);
    } catch (err) {
      return normalizePath(raw);
    }
  }

  const anonId = readOrCreate(window.localStorage, 'maez_anon_id', 'anon');
  const sessionId = readOrCreate(window.sessionStorage, 'maez_session_id', 'sess');

  function send(event, extra) {
    const payload = JSON.stringify({
      event: event,
      path: normalizePath(window.location.pathname),
      anon_id: anonId,
      session_id: sessionId,
      label: cleanText(extra && extra.label, 80),
      target: normalizeTarget(extra && extra.target),
    });

    try {
      if (navigator.sendBeacon) {
        const blob = new Blob([payload], { type: 'application/json' });
        navigator.sendBeacon(API_PATH, blob);
        return;
      }
    } catch (err) {}

    try {
      fetch(API_PATH, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true,
        credentials: 'same-origin',
      }).catch(function() {});
    } catch (err) {}
  }

  function trackClick(element) {
    if (!element) return;
    const label = element.getAttribute('data-analytics-label') || element.textContent || 'cta';
    const target = element.getAttribute('href') || element.getAttribute('data-analytics-target') || '';
    send('cta_click', { label: label, target: target });
  }

  window.maezAnalytics = {
    track: function(event, extra) {
      if (event !== 'pageview' && event !== 'cta_click') return;
      send(event, extra || {});
    },
    trackClick: trackClick,
  };

  if (document.body && document.body.getAttribute('data-analytics-pageview') !== 'off') {
    send('pageview', {});
  }

  document.addEventListener('click', function(event) {
    const tracked = event.target && event.target.closest
      ? event.target.closest('[data-analytics-label]')
      : null;
    if (!tracked) return;
    trackClick(tracked);
  }, true);
})();
