# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this app is

Build Bridge is a **PyQt6 desktop app** (primarily targeting Windows) that wraps the Unreal Engine build pipeline and publishing workflows for Steam and Itch.io. It stores all configuration in a local SQLite database and uses the system keyring for credentials.

## Commands

```bash
# Install dependencies
poetry install

# Run the app
python app.py

# Run DB migrations (required on first run or after schema changes)
alembic upgrade head

# Run tests
pytest

# Run a single test file
pytest build_bridge/tests/test_utils.py

# Create a new migration after model changes
alembic revision --autogenerate -m "description"
```

Use `BUILD_BRIDGE_DB_PATH` env var to override the default DB location (useful for testing without touching the real user DB).

## Architecture

### Entry point

`app.py` bootstraps logging, runs `create_or_update_db()` (which auto-migrates via Alembic), then launches `BuildBridgeWindow` (QMainWindow).

### Data layer (`build_bridge/models.py`, `build_bridge/database.py`)

All state lives in SQLite via SQLAlchemy. Key models:

- **`Project`** — one per app instance currently; holds `source_dir`, `archive_directory`, and the derived `builds_path` (`archive_directory / project_name`).
- **`BuildTarget`** — links to a `Project`; holds UE engine path, platform, build type, target `.cs` file, and maps. One VCSConfig per target.
- **`PublishProfile`** (polymorphic) → `SteamPublishProfile` / `ItchPublishProfile` — store-specific publish settings linked to a `Project`.
- **`SteamConfig`** / **`ItchConfig`** — store-level auth/tool config (one per store, shared across profiles). Passwords and API keys are never stored in the DB; they go through `keyring`.

The DB is located at `%APPDATA%\BuildBridge\build_bridge.db` on Windows, `~/Library/Application Support/BuildBridge/` on macOS. `database.py` handles integrity checks and migration repairs automatically on startup.

### Core logic (`build_bridge/core/`)

- **`builder/unreal_builder.py`** — `UnrealBuilder` constructs the `RunUAT.bat/sh` command from `BuildTarget` fields. It validates the UE install, locates the `.uproject`, and raises typed exceptions (`BuildAlreadyExistsError`, `UnrealEngineNotInstalledError`, etc.).
- **`publisher/base_publisher.py`** — abstract `BasePublisher`.
- **`publisher/steam/steam_publisher.py`** — `SteamPublisher` runs `steamcmd` via `GenericUploadDialog`. Writes/updates the `.vdf` file via `SteamPipeConfigurator` before upload.
- **`publisher/itch/itch_publisher.py`** — `ItchPublisher` runs `butler` similarly.
- **`preflight.py`** — pure validation layer. `validate_build_preflight()` and `validate_publish_preflight()` return `PreflightResult` (list of `PreflightIssue` with severity ok/warning/error) without touching the UI.

### Views (`build_bridge/views/`)

- **`dialogs/build_dialog.py`** — `BuildWindowDialog` drives the UE build via `QProcess`, streams stdout to a log widget, and emits `build_ready_signal` on completion.
- **`dialogs/publish_dialog.py`** — `GenericUploadDialog` is the shared upload runner for both Steam and Itch; success detection is injected as a `Callable[[int, str], bool]`.
- **`dialogs/preflight_dialog.py`** — shows `PreflightResult` before build or publish; blocks on errors.
- **`dialogs/build_target_setup_dialog.py`**, **`publish_profile_dialog.py`**, **`publish_profile_manager_dialog.py`**, **`settings_dialog.py`** — CRUD dialogs for the corresponding models.
- **`widgets/`** — reusable list widgets (`BuildTargetListWidget`, `PublishProfileListWidget`) shown in the main window.

### Styling

All Qt stylesheet strings live in `build_bridge/style/app_style.py` and are applied globally in `app.py`.

### Migrations

Alembic migrations are in `alembic/versions/`. After changing `models.py`, generate a migration with `alembic revision --autogenerate`. The `create_or_update_db()` function in `database.py` is called at startup and handles both fresh installs and upgrades, including a repair path for a known stamped-but-empty DB edge case from v0.6.x.
