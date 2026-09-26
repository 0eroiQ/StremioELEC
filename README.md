# StremioELEC

**StremioELEC** is an experimental, TV-first Linux media distribution built on the LibreELEC/Kodi platform. The goal is to provide a focused Stremio-style experience where the custom interface and Stremio integration feel like part of the operating system instead of a collection of separately installed Kodi add-ons.

> **Development status:** early development. The native UI, Stremio Core bridge and distribution integration are currently being built and tested.

## Project direction

StremioELEC keeps LibreELEC as the low-level OS/build foundation and Kodi as the mature media and playback engine, while replacing the user-facing experience with a dedicated Stremio-oriented layer.

```text
StremioELEC
├── Main UI / Skin
│   └── Nimbus-based UI foundation, heavily customized for StremioELEC
├── Stremio Core bridge
│   ├── catalogs
│   ├── metadata
│   ├── seasons / episodes
│   ├── streams
│   ├── continue watching
│   └── playback integration
├── Portable / Setup Controller
│   └── Kodi Program add-on
├── Kodi media engine
└── LibreELEC Linux foundation
```

## Native UI

The current UI work uses **Nimbus** as the initial Kodi skin foundation. Nimbus provides proven Kodi layout, navigation, focus, dialog and animation behavior while StremioELEC progressively replaces Nimbus-specific integrations with its own Stremio Core data layer.

Nimbus is currently being integrated as a reproducible package for development and boot testing. It is not yet the finished StremioELEC interface.

## Distribution architecture

StremioELEC-specific changes are being isolated from the LibreELEC upstream base wherever practical. The project owns the custom distribution identity, Main UI, Stremio Core bridge, compatibility helpers, setup controller and StremioELEC defaults.

This separation is intended to make future LibreELEC updates easier to integrate without mixing application-specific code into the upstream base unnecessarily.

## Current development milestones

- [x] Create dedicated `stremio-native-ui` development branch
- [x] Add Nimbus source/package baseline
- [x] Establish `distributions/StremioELEC` project area
- [ ] Complete build-valid StremioELEC distribution configuration
- [ ] Integrate Nimbus Helper dependency
- [ ] Boot-test Nimbus from a StremioELEC image
- [ ] Connect Stremio Core data to the Main UI
- [ ] Convert Portable/setup controller to a Kodi Program add-on
- [ ] Replace Nimbus-specific integrations with StremioELEC-native equivalents
- [ ] Add repeatable test/update builds

## Development policy

Active StremioELEC work is committed to the project repository so test builds can be reproduced and installed on development hardware. Experimental native-UI work is currently kept off `master` until the integration is ready.

## Upstream projects and attribution

StremioELEC builds on open-source work from several projects, including:

- **LibreELEC** — Linux distribution and build system foundation
- **Kodi** — media center, playback and add-on platform
- **Nimbus** by ivarbrandt — current skin/UI foundation used during native UI development

StremioELEC does not claim ownership of upstream project code. Upstream code and modifications remain subject to their respective licenses and copyright notices.

## License

This repository is derived from LibreELEC and contains software from multiple upstream projects. LibreELEC original code is released under GPLv2. Individual packages, patches and upstream components may have their own compatible licenses; consult the relevant source and license headers for details.

## Contributing

The project is under active development and its architecture is still evolving. Before making large changes, check the active development branch and existing package/layout conventions so changes remain compatible with the StremioELEC build and test workflow.
