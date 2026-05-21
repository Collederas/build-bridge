from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from build_bridge.models import StoreEnum


@dataclass
class UploadSpec:
    """Everything needed to run one publish to one store, with no UI bound to it.

    Publishers return an UploadSpec from prepare(); the run dialog turns it into
    a QProcess inside an UploadPane. pre_run runs synchronously on the main
    thread right before QProcess.start() (used by Steam to write the VDF).
    """

    store: StoreEnum
    executable: str
    arguments: list[str]
    success_checker: Callable[[int, str], bool]
    title: str
    display_info: dict[str, str]

    environment: dict[str, str] | None = None
    working_directory: str | None = None
    log_files: list[str] = field(default_factory=list)
    log_directories: list[str] = field(default_factory=list)

    build_folder: str | None = None
    store_page_url: str | None = None

    pre_run: Callable[[], None] | None = None
    on_success: Callable[[], None] | None = None
