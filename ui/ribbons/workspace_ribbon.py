"""Workspace ribbon — sample and group management actions.

Actions: Add Samples, Create Group, Load Template, Save Template.

File import follows the same pattern as Western Blot: if an FCS file
is outside the project folder, the user is asked whether to copy it
into the project's ``assets`` directory for portability.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from biopro.shared.ui.ui_components import PrimaryButton, SecondaryButton
from biopro_sdk.plugin import CentralEventBus, get_logger
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QWidget

from analysis import events
from analysis.experiment import (
    Sample,
    SampleRole,
    WorkflowTemplate,
)
from analysis.fcs_io import load_fcs
from analysis.state import FlowState

logger = get_logger(__name__, "flow_cytometry")


class WorkspaceRibbon(QWidget):
    """Toolbar ribbon for workspace-level actions.

    Signals:
        samples_loaded:         Emitted after FCS files are loaded.
        group_requested:        Emitted to create a new group.
        template_load_requested: Emitted to load a workflow template.
        template_save_requested: Emitted to save as template.
    """

    samples_loaded = pyqtSignal()
    group_requested = pyqtSignal()
    template_load_requested = pyqtSignal()
    template_save_requested = pyqtSignal()
    workflow_save_requested = pyqtSignal()

    def __init__(self, state: FlowState, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        btn_add = PrimaryButton("➕ Add Samples")
        btn_add.setObjectName("ImportDataButton")
        btn_add.setToolTip("Load FCS files into the workspace")
        btn_add.clicked.connect(self._on_add_samples)
        layout.addWidget(btn_add)

        btn_group = SecondaryButton("📁 Create Group")
        btn_group.setToolTip("Create a new sample group")
        btn_group.clicked.connect(self.group_requested)
        layout.addWidget(btn_group)

        btn_bulk_role = SecondaryButton("🏷️ Bulk Assign Roles")
        btn_bulk_role.setObjectName("BulkAssignRoleButton")
        btn_bulk_role.setToolTip("Assign a role to multiple samples at once")
        btn_bulk_role.clicked.connect(self._on_bulk_assign_roles)
        layout.addWidget(btn_bulk_role)

        layout.addStretch()

    # ── Helpers: Project Manager integration ──────────────────────────

    def _get_project_manager(self):
        """Retrieve the BioPro ProjectManager from the main window."""
        try:
            main_win = self.window()
            return getattr(main_win, "project_manager", None)
        except Exception:
            return None



    # ── Actions ───────────────────────────────────────────────────────

    def _on_add_samples(self) -> None:
        """Open a file dialog, load FCS files, and add them to the state."""
        pm = self._get_project_manager()
        default_dir = str(pm.project_dir) if pm else ""

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select FCS Files",
            default_dir,
            "FCS Files (*.fcs);;All Files (*)",
        )
        if not files:
            return

        # Check if any files are outside the workspace to prompt once
        outside_files = False
        if pm:
            for fpath in files:
                path = Path(fpath)
                is_in_workspace = pm.assets_dir.resolve() in path.resolve().parents
                if not is_in_workspace:
                    outside_files = True
                    break
                    
        copy_all = False
        if outside_files:
            reply = QMessageBox.question(
                self,
                "Copy to Workspace?",
                "Some files are outside the project folder.\n\n"
                "Would you like to copy them into the project's 'assets' "
                "folder for safe keeping and portability?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            copy_all = reply == QMessageBox.StandardButton.Yes

        loaded_count = 0
        for fpath in files:
            try:
                path = Path(fpath)
                final_path = path
                if pm:
                    is_in_workspace = pm.assets_dir.resolve() in path.resolve().parents
                    should_copy = copy_all and not is_in_workspace
                    try:
                        file_hash = pm.add_image(path, should_copy)
                        resolved = pm.get_asset_path(file_hash)
                        if resolved:
                            final_path = resolved
                    except Exception:
                        logger.exception("Asset registration error")
                        
                fcs_data = load_fcs(final_path)
                sample = Sample(
                    sample_id=str(uuid.uuid4()),
                    display_name=final_path.stem,
                    fcs_data=fcs_data,
                    role=SampleRole.OTHER,
                    markers=[m for m in fcs_data.markers if m],
                    is_compensated=fcs_data.is_compensated,
                )
                self._state.data.experiment.add_sample(sample)
                loaded_count += 1
                logger.info("Loaded sample: %s (%d events)", sample.display_name, fcs_data.num_events)
            except Exception as exc:
                logger.error("Failed to load %s: %s", fpath, exc)
                QMessageBox.warning(self, "Load Error", f"Failed to load:\n{Path(fpath).name}\n\n{exc}")

        if loaded_count > 0:
            self.samples_loaded.emit()
            CentralEventBus.publish(events.SAMPLE_LOADED, {"count": loaded_count, "source": "WorkspaceRibbon"})
            logger.info("Loaded %d FCS files.", loaded_count)
            
            # --- FALLBACK FOR TUTORIAL ADVANCEMENT ---
            try:
                from biopro.core.tutorial_manager import global_tutorial_manager
                if global_tutorial_manager.current_step and global_tutorial_manager.current_step.id == "c1_s2_import":
                    global_tutorial_manager.next_step()
            except Exception as exc:
                logger.debug(f"Tutorial advance skipped: {exc}")

    def _on_bulk_assign_roles(self) -> None:
        """Open the bulk role assignment dialog."""
        from ui.dialogs.bulk_role_dialog import BulkRoleDialog
        
        dialog = BulkRoleDialog(self._state, parent=self)
        if dialog.exec():
            # Refresh UI after bulk assigning roles
            self.samples_loaded.emit()
            CentralEventBus.publish(events.SAMPLE_UPDATED, {"source": "BulkRoleDialog"})

    def _on_load_template(self) -> None:
        """Open a template file and apply it to the workspace."""
        # Default to the built-in workflows directory
        workflows_dir = Path(__file__).resolve().parent.parent.parent / "workflows"
        default_dir = str(workflows_dir) if workflows_dir.exists() else ""

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Workflow Template",
            default_dir,
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return

        try:
            template = WorkflowTemplate.load(Path(path))
            self._state.data.experiment.apply_template(template)
            self.template_load_requested.emit()

            # Publish event
            CentralEventBus.publish(events.SAMPLE_LOADED, {"template_name": template.name, "source": "WorkspaceRibbon"})
            logger.info("Applied template: %s", template.name)
        except Exception as exc:
            logger.error("Failed to load template %s: %s", path, exc)
            QMessageBox.warning(self, "Template Error", f"Failed to load template:\n{Path(path).name}\n\n{exc}")

    def _on_save_template(self) -> None:
        """Save the current workspace configuration as a reusable template."""
        exp = self._state.data.experiment

        # Build a WorkflowTemplate from the current experiment state
        from analysis.experiment import (
            GroupTemplate,
            TubeDefinition,
        )

        group_templates = []
        for group in exp.groups.values():
            tubes = []
            for sid in group.sample_ids:
                sample = exp.samples.get(sid)
                if sample:
                    tubes.append(
                        TubeDefinition(
                            markers=list(sample.markers),
                            fmo_minus=sample.fmo_minus,
                        )
                    )
            if tubes:
                group_templates.append(
                    GroupTemplate(
                        name=group.name,
                        role=SampleRole.OTHER,
                        tubes=tubes,
                    )
                )

        template = WorkflowTemplate(
            name=exp.name or "Untitled Template",
            description="Saved from active workspace.",
            markers=list({m for mm in exp.marker_mappings for m in [mm.marker_name]}),
            marker_mappings=list(exp.marker_mappings),
            groups=group_templates,
        )

        # Save dialog
        pm = self._get_project_manager()
        default_dir = ""
        if pm:
            wf_dir = pm.project_dir / "workflows"
            wf_dir.mkdir(parents=True, exist_ok=True)
            default_dir = str(wf_dir)
        else:
            default_dir = str(Path(__file__).resolve().parent.parent.parent / "workflows")

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Workflow Template",
            default_dir,
            "JSON Files (*.json)",
        )
        if not path:
            return

        try:
            template.save(Path(path))
            QMessageBox.information(self, "Template Saved", f"Workflow template saved:\n{Path(path).name}")
            self.template_save_requested.emit()
        except Exception as exc:
            logger.error("Failed to save template: %s", exc)
            QMessageBox.warning(self, "Save Error", f"Failed to save template:\n{exc}")
