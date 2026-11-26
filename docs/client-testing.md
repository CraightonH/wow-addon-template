# Client testing before a release

Record addon version, client version and build, interface, character class, and other enabled addons in the release PR. A successful Lua test or ZIP build does not exercise protected frames, combat restrictions or the real game API.

- Install the packaged ZIP in a clean test setup. Verify the top folder and TOC names match and the addon appears in the list.
- Test fresh SavedVariables and a copy from the previous version. Check migrations preserve settings and do not affect another character or addon.
- Log in, reload, log out and return. Check for duplicate event handlers, missing initialization and unexpected saved-data changes.
- Exercise the main feature both outside and inside combat where applicable. Capture Lua errors and blocked-action messages.
- Test options and defaults, UI scale, moving/resizing frames, and the feature when its target unit, item, spell or data is unavailable.
- Confirm packaged files include required textures and libraries. Test with and without optional dependencies.

For LootGoblins, cover solo/group changes, roll and queue lifecycle, addon message handling, history and existing saved data. For Rangefinder, cover friendly/enemy nameplates, hover and last-cast range, unknown spells, minimum range, combat and nameplate visibility changes. These addon-specific scenarios require their actual implementations.
