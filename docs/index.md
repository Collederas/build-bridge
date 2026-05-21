---
title: Home
nav_order: 1
---

# Build Bridge

Build Bridge is a simple Windows App that I created to solve a few problems in my build/delivery workflow:
- keeping things organized (where do I put every build? My usual answer was: Desktop. Then I ended up with floating "Windows" folders all over it, ugh)
- avoid lots of context switching when I needed to bring those builds to a store
- keep my configuration somewhere reliable (vdf files, command line tools like steamcmd and their arguments, my Itch game identifier, my Steam APP ID, and so on...)

## Running The App

Extract the BuildBridge app from the archive and run BuildBridge(.exe).

## Prerequisites

### Building
* Unreal Engine. Hopefully if you're making a game in Unreal this step should be self-realizing. Build Bridge uses RunUAT to build your project.

### Publishing

For **Steam**:
* [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD#Downloading_SteamCMD)
* [SteamGuard](https://help.steampowered.com/en/faqs/view/7EFD-3CAE-64D3-1C31#enable): **you will have to authorize publishing the build from your phone** on each upload (see [Publishing Details]({% link publishing.md %}#authentication)).
* An APP ID and Depot ID ready for publishing.

For **Itch**:
* [butler](https://itchio.itch.io/butler): this command line tool is used to manage uploads.
* A valid [Itch API KEY](https://itch.io/user/settings/api-keys) for butler to use.
* Your project page ready on Itch.

## Contact
Questions? Feedback? Bug?
- **On [Itch](https://collederas.itch.io/build-bridge)**: you can leave me a comment!
- **On [GitHub Issues](https://github.com/Collederas/build-bridge/issues)**: create a new issue or comment on an existing one.
