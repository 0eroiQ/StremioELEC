# StremioELEC curated settings — first implementation

The skin Settings and SkinSettings entrypoints now show one curated settings
screen. AddonBrowser, FileManager, SettingsProfile and the legacy 1105 skin
dialog redirect to it. There is no Developer mode. This is NOT a security
boundary: direct builtins, other skin windows, keymaps and remote interfaces
have not yet been comprehensively restricted in an OS build.

The independent settings_ui.py script reads/writes Kodi settings via JSON-RPC
and an allowlist of existing Helper settings, without opening Helper settings.
Helper API keys are entered masked, never shown as stored values. Component
credits/licences remain in the installed source.

Implemented: account actions, imported addon names, Home row selection/order
and item limits, relevant catalog/artwork controls and existing Helper API
fields, platform-exposed audio/video/subtitle controls, system information,
confirmed restart/shutdown, restoring Home, and resetting the local account
stores plus Home to QR onboarding. Display mode changes have a 15-second
confirmation with reversion. Current skin reset is explicitly NOT factory reset:
it does not wipe downloaded subtitle files, Helper cache/API keys, system settings
or arbitrary custom skin options. It preserves network and Bluetooth.

Still required before OS acceptance:
- Music/Live TV addon routing and weather provider/location/cache integration.
- Curated LibreELEC network/Bluetooth/CEC screens and OS update integration.
- Full appearance controls, subtitle styling and hardware codec options.
- Comprehensive removal of legacy navigation routes and OS-level enforcement.
- Complete factory reset semantics, including all private caches/keys, with
  isolated-profile acceptance testing and no changes to the user's live account.
- N60 testing and packaging. The macOS UI is not the deployed LibreELEC OS.

Runtime backup: work/kodi-runtime/backups/curated-settings-20260923/skin
in the Codex task directory. No GitHub publication in this step.

Verification: 50 unit tests passed, including cancellation/failure before
logout, named-store reset scope, absence of generic actions on the two main
settings screens and nested Kodi language options. On the portable macOS
runtime, side-tab Settings opened the new screen, catalog controls opened
without Helper settings, and the native multi-language selector opened with
the existing language selections. Selection was cancelled without modifying
languages. No live reset, API-key change, display-mode switch, restart/shutdown
or N60 operation was performed.

Second settings pass: original SettingsCategory routes now redirect to the
curated screen. Home editing has explicit Save/Cancel and preserves unrelated
shortcut properties. Added an allowlisted appearance menu, device-exposed
decoder/passthrough settings and subtitle font size/style/color/position.
Numeric choices use Kodi-reported bounds and step with a bounded list size.
Visibility of an audio codec switch is not proof that the attached receiver
supports it; no codec/passthrough option is automatically enabled here.

Second pass verification: 59 tests passed. Portable Kodi opened the corrected
rounded/left-aligned settings screen; subtitle size options and saving the
existing size 42 worked. Languages and auto-download were unchanged. This
runtime does not include color settings in Settings.GetSettings, so palette
controls are not exposed here; they remain unverified on other platforms.
Appearance toggles, decoder switches and the SettingsCategory redirect still
need individual runtime acceptance; unit/static checks are not that proof.
