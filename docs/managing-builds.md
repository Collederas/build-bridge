---
title: Managing Builds
nav_order: 3
---

# Managing Builds

The **Available Builds** list shows every build BuildBridge knows about for the selected project.

![Managing builds overview]({{ 'assets/images/manage_builds_overview.png' | relative_url }})

* **Browse** opens the build's output folder on disk.
* **Remove** deletes the build entry from the list. You'll be asked whether to also delete the files on disk.

![Remove build confirmation]({{ 'assets/images/manage_builds_remove_confirm.png' | relative_url }})

* **Import from disk** (toolbar button above the build list) scans your project's archive directory for folders that look like builds and adds them to the list. Handy if you have builds from before BuildBridge started tracking them, or if you cleared the database.

![Import builds from disk]({{ 'assets/images/manage_builds_import_from_disk.png' | relative_url }})

* Running a new build with a version name that already exists will offer to overwrite the previous folder.
