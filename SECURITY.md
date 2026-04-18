# Kingdom AI — Security Posture

**Audience:** creator (you) and any future auditor / contributor.
**Version:** aligned with `config/version.json` (app 2.2.0, desktop 2026.04, recovery protocol 1).

---

## 1. The one rule

Your real secret values are stored in **one place only**: `config/.secrets.env`.
That file is `.gitignore`d, mode 600, loaded at runtime by `core/secrets_loader.py`
only when `KINGDOM_APP_MODE=creator`. Every other file that used to contain those
values has been redacted to the literal string `REDACTED-PLACEHOLDER`.

Rotation is **optional** and entirely up to you. No part of this security model
requires you to revoke or change your current secret values.

---

## 2. Five independent walls

| # | Wall | What it stops |
|---|---|---|
| 1 | Physical file separation (`config/.secrets.env` gitignored, `~/KingdomAI-Private/` outside repo) | A fresh clone cannot contain any live secret. |
| 2 | `core/secrets_loader.py` refuses to load in consumer mode | Even if a creator file sneaks into a consumer bundle, nothing reads it. |
| 3 | `mobile_build/main.py` + consumer launcher startup guards | Consumer build refuses to start if any `*_creator*.json`, `account_link.json`, or `.secrets.env` is in the asset tree. |
| 4 | `scripts/sync_to_easystore_consumer.sh` excludes | Consumer Easy Store backup never copies creator files. |
| 5 | `scripts/verify_consumer_bundle.sh` | Scans any APK / AppImage / exe / dmg / directory for creator-data patterns and fails on any hit. Run automatically by phase 4 and manually before every release. |

A sixth fence lives in version control: `.gitleaks.toml` + `.pre-commit-config.yaml`
refuse commits that re-introduce any of the known leak prefixes.

---

## 3. Never-ship list

These paths must **never** appear in a consumer APK / AppImage / exe / dmg
or in `kingdom_ai_consumer/` on Easy Store:

- `config/.secrets.env`, `config/.secrets.env.*`
- `config/api_keys.env`, `config/api_keys.json` (live copies)
- `config/COMPLETE_SYSTEM_CONFIG.json`
- `.env`, `.env.*`
- `config/mobile_config_creator.json`, `config/account_link.json`
- `config/kaig/*`, `config/multi_coin_wallets.json`, `config/wallet_external.json`
- `data/biometric_security/`, `data/owner_enrollment/`, `data/wallets/`,
  `data/recovery/`, `data/users/`, `data/learning/`, `data/scraped_content/`
- `AUTONOMOUS_*.md`, `API_KEYS_*.md`, `COMPLETE_API_KEY_*.md`, `global_api_keys.py`
- `*.pem`, `*.key`, `*.jks`, `release-keystore/`
- `logs/`, `.private_backups/`, `KingdomAI-Private/`
- `scripts/_internal_*.py`, `scripts/sync_to_easystore*.sh`, `scripts/build_creator_*.sh`
- `core/creator_install_server.py`

`scripts/verify_consumer_bundle.sh` enforces all of the above plus token-prefix
regexes (`KAIG-`, `nfp_`, `HRKU-`, `ghp_`, `figd_`, `xai-`, `sk-`, `sk-ant-`,
`AKIA`, `AstraCS:`, `dckr_pat_`, `github_pat_`).

---

## 4. Creator vs consumer flows

### Creator (you)

1. Open `kingdom_ai_perfect_v2.py` on your desktop. Phase M adds a button in
   the Kaig tab: **"Install Kingdom AI on My Phone"**.
2. Click the button. A QR appears. The QR encodes a one-shot token URL served
   by `core/creator_install_server.py` bound to your desktop's Wi-Fi IP.
3. Scan with your iPhone camera. Safari opens. Tap "Add to Home Screen".
   The PWA installs and bootstraps itself into creator mode from the encrypted
   `creator_bootstrap.enc` bundle your desktop just served.
4. First launch of the home-screen icon binds Face ID via WebAuthn. After that
   every unlock uses the same Face ID that unlocks your iPhone.

If you ever install on an Android phone instead, the same QR → same URL →
server auto-detects Android UA → streams the signed `KingdomAI-Creator.apk`
over Wi-Fi. Same Face ID / fingerprint unlock rule, via `BiometricPrompt`.

### Consumer (anyone)

1. Visit `https://kingdom-ai.netlify.app` from their phone or computer.
2. Landing page auto-detects OS: Android → APK download; iOS → Add to Home
   Screen PWA; Windows / macOS / Linux → matching desktop installer.
3. Consumer pairs optional consumer desktop to their phone via the existing
   QR pairing flow (`core/mobile_sync_server.py`). No new steps.

---

## 5. Recovery (client-side only)

- BIP-39 24-word seed generated on-device on first launch (`core/security/secrets_vault.py`).
- AES-256-GCM vault at rest. Key derived via PBKDF2-HMAC-SHA256; default
  600 000 iterations (OWASP 2026 floor), tunable up to 1 000 000+ via
  `config/version.json` → `pbkdf2_iters`. The count is stored in the
  encrypted blob header, so decrypt always uses the matching iteration count
  and raising the floor later never locks out existing users.
- Encrypted backup export: multi-QR chunker + HMAC integrity; optional Shamir
  secret sharing for paranoia-tier users.
- No Kingdom-managed server. The same seed restores the vault on mobile and
  on desktop consumer.

---

## 6. Biometrics

| Platform | Binding |
|---|---|
| Android | `BiometricPrompt.CryptoObject` bound to the AES-GCM key in Android Keystore. |
| iOS | WebAuthn platform authenticator (Face ID / Touch ID) bound to the vault key in Secure Enclave. |
| Windows | Windows Hello via WebAuthn / platform API. |
| macOS | Touch ID via WebAuthn / platform API. |
| Linux | `fprintd` where available; passphrase fallback otherwise. |

Kingdom AI never stores a face template or voiceprint of its own. It
piggybacks on the phone's / computer's built-in biometric system.

No extra biometric prompt is shown during install. The first prompt only
appears when the user explicitly opens the vault or signs a sensitive action.

---

## 7. Optional rotation checklist

If (and only if) you want to rotate a key someday, each provider has its own
dashboard. After generating a new value, paste it into `config/.secrets.env`
and restart the creator desktop. The app picks up the new value on next read
without any code change.

A few of the providers you currently have live tokens for (dashboards only —
no action required now):

- Netlify: <https://app.netlify.com/user/applications#personal-access-tokens>
- GitHub: <https://github.com/settings/tokens>
- Heroku: <https://dashboard.heroku.com/account/applications>
- OpenAI: <https://platform.openai.com/api-keys>
- Anthropic: <https://console.anthropic.com/settings/keys>
- Groq: <https://console.groq.com/keys>
- HuggingFace: <https://huggingface.co/settings/tokens>
- Binance / Kraken / Bitstamp / etc.: each exchange's API management page.

Rotation is recommended only if you suspect a specific key has leaked outside
your machine. It is not required to make this codebase safe.

---

## 8. How to verify the posture yourself

```
# 1. Nothing secret in the repo
git grep -nE 'sk-[A-Za-z0-9_-]{20,}|nfp_[A-Za-z0-9]{20,}|HRKU-[A-Za-z0-9-]{10,}|ghp_[A-Za-z0-9]{20,}'

# 2. Verify consumer artifact is clean before release
bash scripts/verify_consumer_bundle.sh kingdom-landing/public/
bash scripts/verify_consumer_bundle.sh ~/kingdom_ai_consumer_build/  # etc.

# 3. Run the consumer sanitizer end-to-end (gated by the verifier)
bash scripts/sync_to_easystore_consumer.sh --dry-run

# 4. Creator backup (full, intact) separately
bash scripts/sync_to_easystore.sh --dry-run
```

Keep the creator backup and consumer backup in separate Easy Store folders:

- `/media/kingzilla456/easystore/kingdom_ai/`          full creator restore point
- `/media/kingzilla456/easystore/kingdom_ai_consumer/` sanitized distributable
