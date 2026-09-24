# Trailer integration

## Current StremioELEC runtime: system-bundled SlyGuy resolver

Manual trailer buttons and Trailers & More keep the exact selected TMDb
YouTube clip, but trailer_player.py now hands playback to the checksum-pinned, system-bundled, unmodified SlyGuy Trailers through its /play/ route. The bridge
does not copy SlyGuy implementation code, import account credentials, change
SlyGuy defaults, or add SlyGuy options to Stremio Settings. It does not silently
replace a failed selected clip with an IMDb trailer. Legacy automatic previews
are outside this change.

Pinned in the current StremioELEC image definition (also exercised in the isolated macOS Kodi pilot):

- slyguy.trailers 0.2.0
- script.module.slyguy 0.86.98
- slyguy.dependencies 0.0.30
- repository.slyguy 0.0.9
- inputstream.adaptive 21.5.24 (official Kodi installer)

SlyGuy packages came from the author's matthuisman/slyguy.addons mirror.
The repository remains enabled for upstream updates. SlyGuy downloaded its
QuickJS runtime on the first playback. No cookies or login were supplied.
Reacher official trailer GSycMV-_Csw played in the native Kodi player with
1920x1080 H.264 and English stereo AAC; playback reached 36 seconds of 2:16.
This is macOS playback evidence, not LibreELEC/N60 verification or a promise
that every YouTube video will work.

After the loading-dialog fix, selecting Official Trailer in the skin's
Trailers & More also reached native 1080p playback (14 seconds observed).
The final numeric Dialog.Close(12003,true) route was also exercised via the
main Play Trailer button: fullscreen video displayed without the info overlay.
70 integration unit tests passed, including exact-clip routing, disabled-addon
guard, modal closure, and recovery of a stale busy flag without a loading dialog.

The N60 image builder checksum-locks these upstream packages into SYSTEM, so
users do not install a trailer addon or repository themselves. Keep the original
addon IDs, licences and attribution. Public stable redistribution still requires
the normal licence/dependency review; do not treat a green CI image as that review.

The adapter closes the video-info modal synchronously, then uses Kodi JSON-RPC
Player.Open, without creating an extra loading dialog. A
macOS Kodi 21 sample of the first skin test showed the GUI thread waiting for
the plugin while its Python thread waited for the GUI lock in getCondVisibility.
Do not restore playback dispatch inside the modal video-info dialog; changing
only the dispatch method was insufficient to release the GUI lock.

Downloaded package SHA-256 values (audit, not upstream signatures):

```
782b3be1b9ed9419c9401bcd00299c5241c89e5814da9d4249bd1093e02e16d4  slyguy.trailers-0.2.0.zip
0d732d0bc4b0e2f74e125c6b67b2ec826e71ff71fb68112fa9acdf96f051cd80  script.module.slyguy-0.86.98.zip
ff651f4ca1a6afb963868dc0a962064236b5c9c726a04b9425e43916fb3cb7f2  slyguy.dependencies-0.0.30.zip
079915885866a5cbb8f17191c5ee8f7d044d7a9e788e96d116c9f1bc8bb4c3c0  repository.slyguy-0.0.9.zip
```

## Previous resolver (retained, no longer used by manual trailer entry)

The existing TMDb Bingie Helper Trailers & More catalog is unchanged. Its
selected YouTube link is validated, resolved by bundled yt-dlp, and passed to
Kodi Player. No Kodi YouTube or IMDb trailer addon is installed. Manual trailer
buttons use the same route. A separate TMDb API key can optionally be entered
under Catalogs and artwork for lookup when ListItem.Trailer is absent; it is
stored locally in addon settings and is never copied into the repository.

yt-dlp 2026.8.19 is bundled under plugin.video.stremioelec/vendor from its official
PyPI wheel. Its dist-info/licenses retains the upstream license. Requires Python
3.10+ (the tested macOS Kodi embeds 3.11). No cookies, browser profiles, account
tokens, downloads, remote components or automatic dependency updates are used.
Only a single muxed HTTPS audio/video stream up to 720p is selected. Separate
audio/video and authenticated/blocked videos fail closed with a user message.

Tests cover validated identities, TMDb result ordering, no title guessing,
resolver options, and direct onclick placement in all three trailer controls.
The Reacher official trailer returned YouTube's sign-in/bot-check response on
the development network. This is NOT successful real-video playback evidence.
LibreELEC/N60 playback and JS runtime requirements remain to be validated.
Legacy automatic preview paths are not migrated by this manual trailer change.
