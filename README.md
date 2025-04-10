# Build Bridge

Build Bridge is a tool that streamlines building and deploying Unreal Engine projects to major platforms like Itch.io and Steam. With a user-friendly PyQt6 GUI, it simplifies configuration, automates builds, and manages uploads—all in just a few clicks.

## Features

* **Unreal Engine Builder:** Automates the build process for Unreal Engine projects.
    * Supports different build configurations (e.g., Development, Shipping).
    * Supports Win target platforms (e.g., Win64, Win32). More Platform support TBD.
    * Option to optimize packaging for Steam distribution.
* **Publishing:** Manages publishing profiles and automates uploads to:
    * **Steam:** Configures `app_build.vdf` files, manages depots, and uses `steamcmd` for uploads.
    * **Itch.io:** Uses `butler` for uploads, managing API keys securely via the system keyring.
* **Configuration Management:**
    * Stores project settings, build targets, and publishing profiles in a local SQLite database.
    * Securely stores sensitive credentials (like passwords and API keys) using the system's keyring.
* **GUI:** Provides a user-friendly interface built with PyQt6 for managing builds and publishing.
* **VCS Integration (Experimental):** Includes support for Perforce (P4) for source control operations like syncing and switching streams/branches.

## Getting Started

### Prerequisites

* Python (>=3.9,<3.14)
* Unreal Engine (Version detected from `.uproject` file)
* For Steam publishing: SteamCMD (https://developer.valvesoftware.com/wiki/SteamCMD#Downloading_SteamCMD)
* For Itch.io publishing: Butler (https://itchio.itch.io/butler)

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
4.  **Configure Settings:** Launch the application and navigate to the Settings dialog to configure:
    * **Project Details:** Project Name, Source Directory, Archive Directory.
    * **Steam:** SteamCMD path, Username.
    * **Itch.io:** Butler path, Username, API Key.
    * **(Currently unused) Perforce:** Server, User, Client Workspace.

## Usage

1.  **Run the Application:**
    ```bash
    python app.py
    ```
2.  **Configure Build Target:**
    * Use the "Build Target" section in the main window.
    * Click "+ Add new Build Target" or "Edit" to open the setup dialog.
    * Select the Project, set the Source Directory.
    * Configure VCS settings if needed (e.g., Perforce stream/branch).
    * Set the Build Type (Development/Shipping) and Target Platform (Win64, etc.).
    * Save the build target.
3.  **Build Project:**
    * Select the desired build target in the main window.
    * Enter a Build Version/Release Name (e.g., "1.0.0", "0.2-beta").
    * Click "Build". A dialog will show the Unreal Engine build process output.
4.  **Publish Build:**
    * Once a build is complete, it will appear in the "Available Builds" list.
    * Select the target platform (Steam/Itch.io) from the dropdown next to the build.
    * Click "Profile" to configure the publishing profile for that platform and build ID (e.g., Steam App ID, Depots, Itch.io User/Game ID, Channel). You'll need to have configured the base Steam/Itch.io settings first.
    * Once the profile is configured and valid, click "Publish". An upload dialog will show the progress.

## Configuration

* **Main Configuration:** Stored in the SQLite database. Managed via the Settings dialog.
* **Credentials:** Passwords and API keys are stored securely using the system's keyring service.
* **Database Location:** Determined automatically based on OS or via the `BUILD_BRIDGE_DB_PATH` environment variable.

## Testing

The project wishfully integrates pytest and a test folder. It was used early in development and quickly abandoned. If the app will grow, this will become a main TODO.
