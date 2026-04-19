#!/usr/bin/env bash
# Build the CREATOR-mode PWA bundle.
#
# Output:
#   ~/KingdomAI-Private/pwa/                       static assets (manifest, sw, html, icon)
#   ~/KingdomAI-Private/creator_bootstrap.enc      AES-GCM-encrypted creator config
#
# The iOS install flow works like this:
#   1. Creator's iPhone scans the Kaig QR.
#   2. Safari opens /install?t=<token>.
#   3. User taps Share -> Add to Home Screen.
#   4. First launch, the PWA fetches /creator_bootstrap.enc (same short-lived
#      server, token still valid) and unlocks it with the creator's passphrase.
#   5. From then on the PWA runs in creator mode, bound to Face ID via
#      WebAuthn.
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${OUT_DIR:-$HOME/KingdomAI-Private}"
PWA_OUT="$OUT_DIR/pwa"
mkdir -p "$PWA_OUT"

# --- 1. Copy PWA shell assets ---
cp "$ROOT/kingdom-landing/public/icon.png" "$PWA_OUT/icon.png"

cat > "$PWA_OUT/manifest.json" <<'JSON'
{
  "id": "/creator",
  "name": "Kingdom AI (Creator)",
  "short_name": "Kingdom AI",
  "start_url": "/pwa.html?mode=creator",
  "scope": "/",
  "display": "standalone",
  "background_color": "#0A0E17",
  "theme_color": "#FFD700",
  "icons": [
    {"src": "/icon.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
    {"src": "/icon.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
  ]
}
JSON

cat > "$PWA_OUT/sw.js" <<'JS'
const CACHE = 'kingdom-creator-v1';
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(['/pwa.html', '/manifest.json', '/icon.png'])));
  self.skipWaiting();
});
self.addEventListener('activate', e => { self.clients.claim(); });
self.addEventListener('fetch', e => {
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
JS

cat > "$PWA_OUT/pwa.html" <<'HTML'
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kingdom AI (Creator)</title>
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Kingdom AI">
<style>body{font-family:-apple-system,sans-serif;background:#0A0E17;color:#FFD700;padding:32px}</style>
</head>
<body>
<h1>&#128081; Kingdom AI</h1>
<p id="status">Bootstrapping creator mode...</p>
<script>
// On first launch this pulls the encrypted creator bootstrap from the
// desktop install server (same short-lived Wi-Fi host that served this page).
// Subsequent launches use the already-bootstrapped local state.
(async () => {
  const already = localStorage.getItem('kingdom_creator_bootstrapped');
  const status = document.getElementById('status');
  if (already) {
    status.textContent = "Creator mode active. Unlock with Face ID.";
    // hook Face ID via WebAuthn here (navigator.credentials.get...)
    return;
  }
  try {
    const qs = new URLSearchParams(location.search);
    const token = qs.get('t') || localStorage.getItem('kingdom_install_token');
    if (token) { localStorage.setItem('kingdom_install_token', token); }
    const resp = await fetch('/creator_bootstrap.enc' + (token ? ('?t=' + token) : ''), {cache: 'no-store'});
    if (!resp.ok) throw new Error('bootstrap failed: ' + resp.status);
    const enc = await resp.arrayBuffer();
    localStorage.setItem('kingdom_creator_bootstrapped', '1');
    localStorage.setItem('kingdom_creator_enc', btoa(String.fromCharCode.apply(null, new Uint8Array(enc))));
    status.textContent = "Creator mode installed. Next step: set your passphrase and register Face ID.";
  } catch (e) {
    status.textContent = "Bootstrap error: " + e.message + ". Tap the Kaig QR again on your desktop.";
  }
})();
</script>
</body>
</html>
HTML

# --- 2. Write encrypted creator bootstrap bundle ---
# Uses the Python recovery_vault helpers to encrypt the creator config with a
# short-lived passphrase (shown to the creator on the desktop once).
python3 "$ROOT/scripts/_internal_write_creator_bootstrap.py" \
  --out "$OUT_DIR/creator_bootstrap.enc" \
  --config "$ROOT/config/.secrets.env"

echo ""
echo "Creator PWA assets: $PWA_OUT/"
echo "Creator bootstrap:  $OUT_DIR/creator_bootstrap.enc"
echo "Neither path is ever published or backed up to consumer bundles."
