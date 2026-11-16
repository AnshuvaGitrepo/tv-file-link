# Publishing in app stores (plan)

Status: **not started**. TV File Link is distributed as a signed APK on the GitHub releases page. This page collects what each store would need.

Fire TV devices do not have Google Play; Fire TV apps come from the **Amazon Appstore**. Google Play reaches Google TV / Android TV devices (Chromecast with Google TV, Sony, TCL, Philips, Nvidia Shield). Store rules change often: check the numbers below in each developer console before starting.

| | Amazon Appstore (Fire TV) | Google Play (Android TV / Google TV) |
|---|---|---|
| Audience | Fire TV Stick, Cube, Fire TV smart TVs | Google TV and Android TV devices |
| Account | Free | One-time fee (USD 25) |
| Package | The current APK | Android App Bundle (`.aab`) |
| Effort | Low: store listing | Medium: build and code changes, closed test |

## Shared by both stores

- **Privacy policy URL**, even though the app collects nothing (for example a GitHub Pages page in this repo): no accounts, no analytics, no ads; files move only between the TV and devices on the same local network, during a session the user starts.
- Icon 512 x 512 (`docs/app-icon.svg`), TV screenshots 1920 x 1080 (`screenshots/`), short and long description, content rating questionnaire.
- Explain in the description that the app runs a temporary local web server for transfers, protected by a six-digit code.

## 1. Amazon Appstore (first step)

1. Amazon Developer Console account (identity and tax details).
2. New app, upload `TV-File-Link-Fire-OS.apk` (Fire TV device targeting).
3. Listing, privacy policy, content rating; submit. Amazon tests the app on real Fire TV devices, which also covers the pending physical-device test.

## 2. Google Play (later, as v1.5)

Account
- New personal developer accounts must run a **closed test with at least 12 testers for 14 days** before production, and verify identity.

App and build changes
1. **App Bundle**: move the build to Gradle (the current `fire-os/build-apk.py` is Windows-only and produces an APK).
2. **Target API**: raise `targetSdkVersion` from 34 to the level Play requires for new apps, then retest on the emulators.
3. **All files access** (`MANAGE_EXTERNAL_STORAGE`) is restricted on Play. File managers are an allowed use but need a declaration and review. Alternative: Storage Access Framework folder grants, which would also enable USB writing on Fire OS 6/7.
4. **Android TV**: declare touchscreen not required, keep the leanback launcher and banner, D-pad everywhere (already done); Play reviews TV apps against its TV quality guidelines.
5. **Signing**: Play App Signing; uploading the existing key keeps store builds compatible with the GitHub APK.
6. **Native code**: 64-bit libraries (present) and 16 KB page alignment (NDK 28 and `zipalign -P 16`; verify).

Listing
- Feature graphic 1024 x 500, TV banner 1280 x 720, TV screenshots, Data safety form (no data collected or shared), target audience, no ads.

## Suggested order

1. Privacy policy page.
2. Amazon Appstore submission with the current APK.
3. v1.5 for Google Play: Gradle + `.aab`, new target API, storage access decision, full retest.
4. Google Play closed test (12 testers, 14 days), then production.
