# Changelog

## v0.8.0

### Added
- Multi-project support: manage and switch between multiple Unreal projects from the main window
- Delete project action in the main window project row (removes build targets, publish profiles, and build records; leaves files on disk)
- Non-modal multi-store publish runs so uploads to different stores can run in parallel
- "Import from disk" to scan pre-refactor build folders into the new Build entity
- Documentation site migrated to just-the-docs with multi-page navigation and dark mode toggle
- Documentation screenshots for the managing-builds flow

### Changed
- Introduced `Build` entity; publish profiles now live on `BuildTarget`
- Publish profiles limited to one per (target, store) pair
- Inline preflight status surfaced in the publish UI
- Upgraded to Python 3.14

### Removed
- Steam playtest publishing paths
- Disclaimer from README

### Fixed
- Project deletion / settings save no longer references removed `Project.builds_path`
- Build overwrite output handling
- Target map cooking and build registration
- 13 UX issues: silent errors, missing confirmations, footguns, discoverability
- 10 bugs: import crash, model validation errors, SIGKILL race, macOS browse dialog
- Broken test imports and Python 3.9 compat issues; added preflight tests
