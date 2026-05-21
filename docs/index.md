---
title: Build Bridge Documentation
---

## Build Bridge

Build Bridge is a simple Windows App that I created to solve the following problems in my build/delivery workflow:
- keeping things organized (where do I put every build? My usual answer was: Desktop. Then I ended up having floating "Windows" folders there, ugh)
- avoid lots of context switching when I needed to bring those builds to a store 
- keep my configuration preferences saved somewhere (vdf files, switching to command line tools like steamcmd, then remembering the arguments to pass in: hey wait what was my Itch game name identifier?, and my Steam APP ID? and so on...)

## DISCLAIMER
I developed this tool with my own workflow in mind and it's tailored to my current setup (Windows-based).

**But**, I would love if other people would find it useful too and in that case I am more than happy to listen for feedback and add/tweak functionality to cover a wider ranges of scenarios.

**Also**, while I have used it successfully, I cannot exclude lingering bugs here and there.

**So**, if you want to let me know of any feature idea, _UX_ improvement or simply report a bug, please reach out in one of these places:

- **On [Itch](https://collederas.itch.io/build-bridge)**: you can leave me a comment!
- **On [GitHub Issues](https://github.com/Collederas/build-bridge/issues)**: creating or commenting on an existing issue.


## Running The App
Extract the BuildBridge app from the archive and run BuildBridge(.exe).


## Prerequisites

### Building
* Unreal Engine. Hopefully if you are making a game in Unreal this step should be self-realizing. Build Bridge uses RunUAT to build your project.

### Publishing

For **Steam**:
* [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD#Downloading_SteamCMD)
* [SteamGuard](https://help.steampowered.com/en/faqs/view/7EFD-3CAE-64D3-1C31#enable): **you will have to authorize publishing the build from your phone**.
* An APP ID and Depot ID ready for publishing.

**STEAMGUARD 2FA**. SteamGuard with confirmation on your Steam Phone App is the only currenlty supported 2FA method.
If your account is protected by 2FA you need to confirm the login on each upload.
{: .notice--danger }

For **Itch**:
* [butler](https://itchio.itch.io/butler): this command line tool is used to manage uploads.
* A valid [Itch API KEY](https://itch.io/user/settings/api-keys) for butler to use.
* Your project page ready on Itch.

## Getting Started

1.  **Add a Project**
* This is what you should see if you load the app for the first time:
    ![Empty App]({{ 'assets/images/mainui_empty.png' | relative_url }})
* To add a Project go to **File -> Settings -> Project** (or use **+ New** in the
    project row at the top of the main window) and add a name (will be used to
    name the folder containing your builds).
    ![Add a project]({{ 'assets/images/settings_project_empty.png' | relative_url }})
* Set Source Directory: this is the folder containing the .uproject file.
* Set the Archive Directory: this is the root folder where all builds will go.
* You can add as many projects as you want and switch between them using the
    **Project** dropdown at the top of the main window. The selected project
    drives which build targets and builds are shown below.
    ![Project Selector]({{ 'assets/images/project_selection_dropdown.png' | relative_url }})


2.  **Configure Build Target**
* Click "+ Add new Build Target" or "Edit" to open the setup dialog. If you didn't create a Project you'll see a shortcut here.
    ![Add a Build Target]({{ 'assets/images/build_target_empty.png' | relative_url }})
* Select the Project you just created, verify the Source Directory.
    ![Add a Build Target]({{ 'assets/images/build_target_proj_filled.png' | relative_url }})
* Set the Build Type (Development/Shipping) and Target Platform (Win64, etc.).
    ![Add a Build Target]({{ 'assets/images/build_target_build.png' | relative_url }})
* Save the build target.

From version 0.6.0 the Maps and Target section was added. This allows you to specify a target and specific maps to be included using the `"-map"` argument.
        ![Maps and Target]({{ 'assets/images/build_target_maps_target.png' | relative_url }})
{: .notice--info }

3.  **Build**
* The build target is now active in the main window.
        ![Build Target Created]({{ 'assets/images/mainui_build_target_filled.png' | relative_url }})
* Enter a Build Version/Release Name (e.g., "1.0.0", "0.2-beta").
* Click "Build". A dialog will show the Unreal Engine build process output and output build logs from RunUAT.
        ![Building]({{ 'assets/images/build.png' | relative_url }})

4.  **Publish**
* Once the build is complete, it will appear in the "Available Builds" list in a folder named _{Project.archive_directory}/{Project.name}/{BuildId}_
        ![Build List]({{ 'assets/images/build_list_multi_store.png' | relative_url }})
* Each build row shows a checkbox per store (Steam, Itch.io) with an inline
    status indicator:
    * **✓ ready** — preflight passed, ready to publish.
    * **⚠ warnings** — publishable, but something's worth a glance (hover the label for details).
    * **✗ issues** — a blocking problem; the checkbox is disabled until it's fixed.
    * **⚠ not configured** — no profile exists yet for that store.
* Hover the status text to see exactly what's missing or off.
        ![Store Status Tooltip]({{ 'assets/images/store_status_tooltip.png' | relative_url }})
* Click **Configure** next to a store to set its publishing details (Steam App ID
    and Depots, or Itch.io User/Game ID and Channel). You'll need to have
    configured the related Steam/Itch.io settings first — see [Publishing Details](#publishing-details).
* Tick the stores you want to publish this build to. You can pick one, or
    several. Then click **Publish**.
* A publishing window opens with one pane per selected store. Uploads run
    in parallel, each with its own log, status, and cancel button. The window
    is non-modal, so you can keep using the main app while it runs.
        ![Publish Dialog]({{ 'assets/images/publish_dialog_multi.png' | relative_url }})
*SteamCMD buffers its output so you will see logs appearing with delay.*
* If Steam is one of the selected stores and your account uses SteamGuard,
    the Steam pane will switch to a "Confirm on phone" state while you
    approve the login. Other stores keep uploading in the meantime.
* When a pane finishes successfully, it offers shortcuts to open the build
    folder or the store page for that release.

### Managing builds

* **Browse** opens the build's output folder on disk.
* **Remove** deletes the build entry from the list. You'll be asked whether
  to also delete the files on disk.
* **Import from disk** (toolbar button above the build list) scans your
  project's archive directory for folders that look like builds and adds
  them to the list — handy if you have builds from before BuildBridge
  started tracking them, or if you cleared the database.
* Running a new build with a version name that already exists will offer
  to overwrite the previous folder.

# Publishing Details
For now Steam and Itch are the supported stores.
Publishing to each requires you to have on your machine a recent version of their respective command line tools: SteamCMD and Butler. See [Prerequisites](#prerequisites).

Build Bridge needs to authenticate to Itch and Steam so a set of credentials are required. Passwords and API Keys are stored using `keyring` and not kept in the local database.

You can configure each Store authentication from File -> Settings
        ![Store settings]({{ 'assets/images/settings_steam_empty.png' | relative_url }})


## Steam

### Authentication
Steam Publishing requires authenticating to the Steam Servers like any other upload. 
To authenticate you will have to add you username and password to Steam Settings.

**STEAMGUARD 2FA**.
If your account is protected by 2FA you need to confirm the login on the Steam app on each upload. Keep your phone near.
{: .notice--danger }

Once you have entered the credentials **and the path to your local SteamCMD executable** (used to try a login call), you will be able to verify the connection.

If everything goes well, after you accept the access on your Steam app you should see a confirmation message. Else the error will be logged.
        ![Steam Connection Sunny Scenario]({{ 'assets/images/settings_steam_testing_success.png' | relative_url }})

### Publishing Configuration
The Steam configuration dialog (Build List entry -> Configure button next to
Steam) lets you specify the fields that will end up in the vdf file: App ID,
depot mappings (Depot ID + content folder), and which Steam authentication
profile to use.
        ![Steam Publishing Configuration]({{ 'assets/images/publish_profile_steam.png' | relative_url }})

Build Bridge automatically creates the required vdf file, using the single
file approach (no separation for depots). It will place the generated config
and build logs in an auto-generated `Steam` folder under your Project's
archive directory — this is managed for you, no configuration needed.
{: .notice--info }
![Steam Config Folder]({{ 'assets/images/builds_folder.png' | relative_url }})

## Itch

### Authentication
Itch Publishing requires only a username and your [API KEY](https://itch.io/user/settings/api-keys).
You can test a connection without butler (as it is done via simple HTTP API call). But you will need butler to publish anyways so ensure you point to it.
        ![Itch Config Folder]({{ 'assets/images/settings_itch_testing_success.png' | relative_url }})

### Publishing Configuration
This dialog (Build List entry -> Configure button next to Itch.io) allows you to specify the fields that butler uses to publish the build on your game's page.
        ![Itch Publishing Configuration]({{ 'assets/images/publish_profile_itch.png' | relative_url }})


## Contact
Questions? Feedback? Bug?
- **On [Itch](https://collederas.itch.io/build-bridge)**: you can leave me a comment!
- **On [GitHub Issues](https://github.com/Collederas/build-bridge/issues)**: create a new issue or comment on an existing one.
