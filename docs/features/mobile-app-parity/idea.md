# Idea: close useful gaps with the 9.9.0 mobile apps

- **Date:** 2026-07-15
- **Source:** AVD walkthrough + decrypted HAR + signed APK analysis
- **Owner:** @gentslava

## What is proposed

Add durable event/archive access, guest invitation generation, access-key
visibility and safe private-camera controls to the Home Assistant integration.

## Why

The integration already covers live cameras, doors, finance, DND and realtime
intercom calls. The largest remaining user-facing differences are historical
video, household access administration and settings for owned cameras.

## Who benefits

- residents who want to inspect a missed call or motion clip from HA;
- owners who need to send a guest invitation without opening the stock app;
- subscribers with registered physical access keys;
- subscribers with a private operator camera.

## Alternatives considered

- Keep linking to the stock app: safe, but prevents automations and a unified HA
  surface.
- Reproduce every mobile screen: rejected; advertising, CAPTCHA payment pages,
  Wi-Fi provisioning and firmware update do not fit HA.
- Create entities for guest names and key codes: rejected because recorder and
  diagnostics would persist PII/credentials.

## Out of scope

- accepting an invite on behalf of a guest;
- showing resident names/account IDs in HA states;
- camera Wi-Fi onboarding, tariff purchase or firmware update;
- an alarm panel based only on unverified `placeArmingOn/Off` strings;
- claiming access-key usage history while the 9.9.0 app labels it “Coming soon”.

## Next step

- [x] Capture the idea and evidence.
- [ ] Approve the MVP order in [`prd.md`](prd.md).
- [ ] Collect the static-only HAR fixtures listed in [`tasklist.md`](tasklist.md).

