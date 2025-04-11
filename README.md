# Build Bridge

Build Bridge is a tool that streamlines building and deploying Unreal Engine projects to major platforms like Itch.io and Steam. With a user-friendly PyQt6 GUI, you can trigger versioned builds and publish them—all in just a few clicks.

## Features

* **GUI:** Provides a user-friendly interface built with PyQt6 for managing builds and publishing.

* **Unreal Engine Builder:** Automates the build process for Unreal Engine projects.
    * Supports different build configurations (e.g., Development, Shipping).
    * Option to optimize packaging for Steam distribution.

_Currently supports only Win target platforms (e.g., Win64, Win32)_

* **Publishing:** Manages publishing profiles and automates uploads to:
    * **Steam:** Configures `app_build.vdf` files, manages depots, and uses `steamcmd` for uploads.
    * **Itch.io:** Uses `butler` for uploads, managing API keys securely via the system keyring.
* **Configuration Management:**
    * Stores project settings, build targets, and publishing profiles in a local SQLite database.
    * Securely stores sensitive credentials (like passwords and API keys) using the system's keyring.

## Documentation
Check out the documentation [here](https://collederas.github.io/build-bridge/)!

### Prerequisites

* Python (>=3.9,<3.14)
* Unreal Engine (Version detected from `.uproject` file)
* For Steam publishing: [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD#Downloading_SteamCMD)
* For Itch.io publishing: [Butler](https://itchio.itch.io/butler)

### Installation & Setup

1.  **Clone/Download:** Get the project code.
2. **Install poetry**
    ```bash
    pipx install poetry
    ```
2.  **Install Dependencies:**
    ```bash
    poetry install
    ```
3.  **Database Initialization:** The application uses a SQLite database stored in the user's application data directory (`%APPDATA%\BuildBridge` on Windows). The database should be initialized with alembic:
    ```alembic upgrade head```
You can customize the database location by setting the `BUILD_BRIDGE_DB_PATH` environment variable.

## Configuration

* **Main Configuration:** Stored in the SQLite database. Managed via the Settings dialog.
* **Credentials:** Passwords and API keys are stored `keyring`.
* **Database Location:** Determined automatically based on OS or via the `BUILD_BRIDGE_DB_PATH` environment variable.

## Contact
I very much welcome feedback and bug reports. You can use:
- Create or comment on [GitHub Issues](https://github.com/Collederas/build-bridge/issues)
- Leave a comment on [Build Bridge Itch Page](https://collederas.itch.io/build-bridge)

## Development notes
I built this app quite quickly and I think we are at a point where adopting an actual View-ViewModel pattern could be useful especially to deal with big widgets like settings or to validate configurations (like Publish Profiles).
If you have a design suggestion please let me know using one of the [channels above](#contact)
