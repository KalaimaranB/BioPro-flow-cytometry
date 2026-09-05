"""Flow Cytometry half of the Hub's `core_intro` onboarding tour.

The Hub's own `core_intro_v1` course (``karcytics/tutorials/core_intro.py``)
used to walk the user through this module directly, back when Flow Cytometry
ran in-process and the Hub could `findChild()` its buttons. Now that this
plugin runs as a genuinely separate OS process (the V3 isolated engine), the
Hub can no longer reach into its widget tree at all — so this course is the
in-module continuation of that same tour, run entirely by this plugin's own
local Academy engine (`karcytics_sdk.plugin.runtime_services.tutorial_manager`),
the exact mechanism `course1_fundamentals` already proves works for spotlighting
this plugin's own real widgets from inside its own process.

Deliberately **not** registered via `register_courses()` / listed in this
plugin's own Academy catalogue (`AcademyCatalogWindow`) — it's the Hub's tour
content, just executed here; a user picking their own course from Help >
Academy should never see it. It's registered and auto-started only from
`ui_daemon.py`'s `on_panel_ready` hook, gated on `KARCYTICS_ACADEMY_HANDOFF`
(see that file, and `plugin_loader.py::_instantiate_isolated_overlay` on the
Hub side, which sets the flag that becomes that env var).

On completion, `ui_daemon.py` sends an `academy_handoff_complete` event back
to the Hub over the existing daemon IPC channel, which resumes `core_intro_v1`
at its graduation phase (see `karcytics/core/plugins/loader.py`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from karcytics_sdk.plugin.tutorial_models import (
    ActionStep,
    ConsentStep,
    Course,
    InfoStep,
    InteractionStep,
    VerificationStep,
)

from .validators import WorkflowSavedValidator

CORE_INTRO_HANDOFF_COURSE_ID = "core_intro_module_v1"


def _copy_demo_file(_panel: Any) -> None:
    """Copy the bundled demo FCS file to the user's Downloads directory.

    Mirrors the Hub's own `karcytics.tutorials.core_intro._copy_demo_file`
    exactly (same dedup-by-size handling, same destination filename) — the
    Hub used to run that step itself before handing control to the module;
    now this plugin runs the equivalent locally, using the same bundled
    ``demo_tutorial.fcs`` (copied in at repo level, not downloaded — it's
    1KB, no reason to route it through the network-download machinery
    `tutorial_assets.py` uses for Course 1's real, much larger FCS fixtures).
    """
    import contextlib
    import shutil

    from PyQt6.QtCore import QStandardPaths

    src_file = Path(__file__).resolve().parent / "assets" / "demo_tutorial.fcs"
    if not src_file.exists():
        return

    download_loc = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    downloads_dir = Path(download_loc) if download_loc else Path.home() / "Downloads"
    downloads_dir.mkdir(exist_ok=True, parents=True)

    dest_file = downloads_dir / "demo_tutorial.fcs"

    with contextlib.suppress(Exception):
        if dest_file.exists():
            if dest_file.stat().st_size == src_file.stat().st_size:
                return  # Already our demo file

            suffix = 1
            while True:
                new_dest = downloads_dir / f"demo_tutorial_{suffix}.fcs"
                if not new_dest.exists():
                    dest_file = new_dest
                    break
                if new_dest.stat().st_size == src_file.stat().st_size:
                    return
                suffix += 1

        shutil.copy(src_file, dest_file)


core_intro_module = Course(
    id=CORE_INTRO_HANDOFF_COURSE_ID,
    title="Karcytics Onboarding Tour — Flow Cytometry",
    description="The in-module continuation of the Hub's onboarding tour.",
    estimated_minutes=3,
    badge_reward=None,
    badge_icon="",
    prerequisite_course_ids=[],
    steps=[
        InfoStep(
            id="handoff_welcome",
            text=(
                "🧬 Welcome to **Flow Cytometry**! Every module gets a workspace built just for what it does."  # noqa: E501
            ),
            cyto_emotion="surprised",
            next_step_id="handoff_data_integrity",
        ),
        InfoStep(
            id="handoff_data_integrity",
            text=(
                "One thing before you import anything: Karcytics never touches your raw files. On import, it hashes the file (SHA-256) and copies it into this project's `` `assets/` `` folder — your original stays exactly where it was."  # noqa: E501
            ),
            cyto_emotion="talking",
            next_step_id="handoff_consent",
        ),
        ConsentStep(
            id="handoff_consent",
            text="Can we download a demo FCS file into your Downloads folder to use for this tutorial? If you decline, you will need to provide your own valid FCS file.",
            accept_text="Yes, download it",
            decline_text="No, I'll use my own",
            on_accept_step_id="handoff_download_demo",
            on_decline_step_id="handoff_import_custom_action",
        ),
        ActionStep(
            id="handoff_download_demo",
            text="",
            action=_copy_demo_file,
            next_step_id="handoff_import_action",
        ),
        InteractionStep(
            id="handoff_import_custom_action",
            text="No problem! Please click **➕ Add Samples** (highlighted) and import any valid FCS file from your machine to continue.",
            target_widget_names=["ImportDataButton"],
            target_widget_name="WorkspaceRibbon",
            event_trigger="samples_loaded",
            cyto_emotion="pointing",
            next_step_id="handoff_workflow_intro",
        ),
        InteractionStep(
            id="handoff_import_action",
            text=(
                "I've dropped a demo file (`` `demo_tutorial.fcs` ``) in your Downloads folder.\n\n"  # noqa: E501
                "Click **➕ Add Samples** (highlighted) and pick it. When it asks whether to copy the file into your workspace, say yes."  # noqa: E501
            ),
            target_widget_names=["ImportDataButton"],
            target_widget_name="WorkspaceRibbon",
            event_trigger="samples_loaded",
            cyto_emotion="pointing",
            next_step_id="handoff_workflow_intro",
        ),
        InfoStep(
            id="handoff_workflow_intro",
            text=(
                "Loaded! A **Workflow** is a snapshot of everything right now — settings, gates, parameters — so you can pick this exact session back up later."  # noqa: E501
            ),
            cyto_emotion="talking",
            next_step_id="handoff_save_action",
        ),
        VerificationStep(
            id="handoff_save_action",
            text=("Let's lock this in. Click **Save Workspace** (highlighted)."),
            cyto_emotion="happy",
            allow_interaction=True,
            target_widget_names=["WorkspaceSaveButton"],
            validator=WorkflowSavedValidator(),
            on_success_step_id="handoff_return_home",
        ),
        InfoStep(
            id="handoff_return_home",
            text=(
                "Saved! Close this window (File → Close, or the OS close button) to head back to Karcytics — Cyto's waiting for you there."  # noqa: E501
            ),
            cyto_emotion="happy",
        ),
    ],
)
