# Kingdom AI — Consumer Edition

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Release](https://img.shields.io/badge/release-v2.2.0-brightgreen)](https://github.com/LegendsUp1/KingdomAi/releases)
[![Platform](https://img.shields.io/badge/platform-Android%20%7C%20iOS%20%7C%20Desktop-lightgrey)](#install)

Kingdom AI is a privacy-first, self-custodial AI + crypto assistant that runs
**on your device, not on a server**. This repository is the public **consumer
edition** source tree — the exact code that builds the app shipped on
[kingdom-ai.netlify.app](https://kingdom-ai.netlify.app).

> **No account required. No tracking. No cloud storage of your keys.**
> Your seed phrase is generated and stored only on your device.

---

## Install

| Platform | How to install                                                                                              |
| -------- | ----------------------------------------------------------------------------------------------------------- |
| Android  | Download [`KingdomAI.apk`](https://github.com/LegendsUp1/KingdomAi/releases/latest) or from the [landing page](https://kingdom-ai.netlify.app) |
| iOS      | Open [kingdom-ai.netlify.app](https://kingdom-ai.netlify.app) in Safari → Share → **Add to Home Screen**     |
| Desktop  | Clone this repo and run `python kingdom_ai_consumer.py` (see [Build from source](#build-from-source))       |

The landing page auto-detects your OS and shows the right installer. If you
prefer sideloading the APK directly, grab it from the
[Releases](https://github.com/LegendsUp1/KingdomAi/releases) page on GitHub —
every release ships with a matching `.sha256` file so you can verify integrity:

```bash
sha256sum -c KingdomAI.apk.sha256
```

---

## Cross-device account sync (no server)

Kingdom AI uses a **BIP-39 seed phrase** (12 or 24 words) as the only source
of truth for your account. The flow:

1. First launch → app generates a seed on-device and shows it to you once.
2. Back it up (paper, metal plate, password manager — your choice).
3. On any other phone or computer, tap **Recover** and type the same seed.
4. Your entire local vault — settings, watchlists, encrypted notes — is
   derived deterministically from that seed.

Because the seed never leaves your device and we run no account server, you
get perfect portability without a login.

Secrets in the local vault are encrypted with **AES-256-GCM**, keyed by
**PBKDF2-HMAC-SHA256** (600 000 iterations, tunable up to 1 000 000). See
[`SECURITY.md`](./SECURITY.md) for the full threat model.

---

## Build from source

You need Python 3.11+, and for mobile builds, the [Flet](https://flet.dev)
CLI + a Flutter / Android SDK.

### Desktop (Linux / macOS / Windows)

```bash
git clone https://github.com/LegendsUp1/KingdomAi.git
cd KingdomAi
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python kingdom_ai_consumer.py
```

### Android APK

```bash
cd mobile_build
flet build apk --yes --module-name kingdom_mobile_consumer
# APK lands in mobile_build/build/apk/
```

### iOS PWA

The iOS experience is a Progressive Web App served from
[`kingdom-landing/`](./kingdom-landing). To build it locally:

```bash
cd kingdom-landing
# static site — no build step; serve the public/ directory
python -m http.server --directory public 8080
```

---

## Verify the bundle yourself

Every tree under this repo can be scanned for secret-leak patterns with the
included verifier:

```bash
./scripts/verify_consumer_bundle.sh .
```

It should print `all targets clean`. If it doesn't, open an issue — that is
a security bug.

---

## What's NOT in this repo

By design, the consumer edition **does not contain**:

- Any real API keys, wallets, or seed phrases
- Creator-only features (private mining pools, admin tooling)
- Release signing keys
- The creator's personal desktop configuration

A separate, private creator edition exists for the developer's own devices.
The public tree you're reading has been scrubbed and is verified leak-free on
every release.

---

## Security

- **Threat model and hardening details:** see [`SECURITY.md`](./SECURITY.md).
- **Report vulnerabilities:** please open a private security advisory on
  GitHub rather than a public issue.
- **Web security headers** (HSTS, CSP, X-Frame-Options, etc.) are enforced on
  the hosted landing page. You can verify with:
  ```bash
  curl -sI https://kingdom-ai.netlify.app/ | grep -iE 'strict-transport|content-security|x-frame'
  ```

---

## License

Licensed under the **Apache License, Version 2.0** — see [`LICENSE`](./LICENSE).

You are free to use, modify, and distribute this code, including for
commercial purposes, provided you retain the license and attribution.
