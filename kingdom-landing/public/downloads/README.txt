Kingdom AI - public downloads directory
========================================

This directory is where verified consumer artifacts are published:

  KingdomAI.apk            - Android consumer build (signed, R8 obfuscated)
  KingdomAI.apk.sha256     - companion integrity file
  KingdomAI-Desktop-Win.exe
  KingdomAI-Desktop-macOS.dmg
  KingdomAI-Desktop-Linux.AppImage

How artifacts get here:

  1. Creator builds locally with:
       flet build apk --release         (consumer APK)
       scripts/build_desktop_consumer.sh (desktop AppImage)
  2. Creator runs:
       scripts/verify_consumer_bundle.sh <artifact>
     which must exit 0 (no creator data leaks).
  3. Creator atomically swaps the new artifacts into this directory and
     uploads the whole kingdom-landing/public/ tree to Netlify.

If this directory is empty, the landing page index.html automatically
detects the missing APK and steers Android users to the Web App (PWA)
install flow instead, which works without any download.

Never commit signed APKs or desktop installers to source control.
