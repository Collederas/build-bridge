# Build Bridge

Build Bridge is a simple Windows App to build, organize and publish Unreal projects. I built it to help the workflow of playtesting and distributing my first game (One Last Toast - on Steam and Itch).

The idea is:
- to have a predefined build directory where builds are stored by version number
- to be able to then push those builds to Steam and to Itch without using the command line and/or having to edit vdf files manually.

## AI DISCLAIMER

While the overall design is intentional, I heavily relied on LLMs to code review and sometimes even to re-generate various pages for the sake of speed. Over time I plan refactor most of it (starting in v0.4.0 already).

## Contact

I very much welcome feedback and bug reports. You can:
- Create or comment on [GitHub Issues](https://github.com/Collederas/build-bridge/issues)
- Leave a comment on [Build Bridge Itch Page](https://collederas.itch.io/build-bridge)

## Core components

* **Unreal Engine Build system:** Uses the engine in the user's system (this is a **prerequisite**) to wrap the RunUAT.bat process. Arguments and preferences can be filled through the graphical interface in a dialog.
* **Publish system:** Allows to configure punlishing preferences through GUI.
    * **Steam:** Configures `app_build.vdf` file. Uses `steamcmd` for uploads.
    * **Itch.io:** Uses `butler` for uploads.
* **Configuration Management:**
    * Stores project settings, build targets, and publishing profiles in a local SQLite database.
    * Securely stores sensitive credentials (like passwords and API keys) using the system's keyring.

## Documentation

I wrote [the docs](https://collederas.github.io/build-bridge/)!

## Prerequisites

* Python (>=3.9,<3.14)
* Unreal Engine (Version detected from `.uproject` file)
* For Steam publishing: [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD#Downloading_SteamCMD)
* For Itch.io publishing: [Butler](https://itchio.itch.io/butler)

## Installation & Setup

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
    ```
    alembic upgrade head
    ```
5. **Run the app**
   ```bash
   python app.py
   ```
