"""UMAP Viewer — UI component for visualizing and configuring UMAP reduction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import scipy.spatial
from biopro.ui.theme import Colors
from biopro_sdk.plugin.components import (
    BioComboBox,
    BioLineEdit,
    BioListWidget,
    BioSpinBox,
    SecondaryButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QProgressBar,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from analysis.animation.animation_prep import UmapAnimationDataPrep
from analysis.services.umap_service import UmapParams, UmapService
from analysis.state import FlowState

from .cluster_results_panel import ClusterResultsPanel
from .umap_animator_widget import UmapAnimatorWidget

if TYPE_CHECKING:
    from ..ribbons.umap_ribbon import UmapRibbon


# Button toggle styles removed (using SDK)
# ToggleSwitch removed


class UmapViewer(QWidget):
    """Component that plots the UMAP embedding and exposes Student/Pro configurations."""

    def __init__(
        self, state: FlowState, umap_service: UmapService, gate_coordinator=None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._umap_service = umap_service
        self._gate_coordinator = gate_coordinator
        self._total_events = 0
        self._is_animation_playing = False
        self._is_analysis_running = False

        self._last_results: dict[str, Any] | None = None
        self._kdtree: scipy.spatial.KDTree | None = None

        # Colorbar reference to remove/update
        self._colorbar = None
        self._scatter = None

        self._setup_ui()

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-weight: bold; font-size: 11px; text-transform: uppercase;"
        )
        return lbl

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ── Left Control Panel (280px) ──
        self._left_panel = QFrame()
        self._left_panel.setFixedWidth(280)
        self._left_panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        left_layout = QVBoxLayout(self._left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(14)

        # ── Group 1: Visual Options (Always Visible) ──
        vis_group = QWidget()
        vis_group.setStyleSheet("background: transparent; border: none;")
        vis_layout = QVBoxLayout(vis_group)
        vis_layout.setContentsMargins(0, 0, 0, 0)
        vis_layout.setSpacing(6)

        vis_layout.addWidget(self._section_label("Visual Options"))

        # Replay Animation Button
        self._replay_anim_btn = SecondaryButton("▶ Replay Animation")
        self._replay_anim_btn.setEnabled(False)
        self._replay_anim_btn.clicked.connect(self._play_animation)
        vis_layout.addWidget(self._replay_anim_btn)

        vis_layout.addSpacing(10)
        left_layout.addWidget(vis_group)

        # ── Run Details ──
        left_layout.addWidget(self._section_label("Run Details"))
        self._run_details_lbl = QLabel("Create a new run to see details.")
        self._run_details_lbl.setWordWrap(True)
        self._run_details_lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: 11px;")
        left_layout.addWidget(self._run_details_lbl)

        left_layout.addStretch()
        main_layout.addWidget(self._left_panel)

        # ── Right Workspace Panel ──
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Progress bar (only visible during computation)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {Colors.ACCENT_PRIMARY};
                border-radius: 4px;
            }}
        """)
        self._progress_bar.hide()
        right_layout.addWidget(self._progress_bar)

        # Stacked display
        self._display_stack = QStackedWidget()
        self._display_stack.setStyleSheet(f"background-color: {Colors.BG_DARKER}; border-radius: 8px;")

        # 0: Configuration Panel (Centered)
        self._config_panel = QWidget()
        config_outer_layout = QVBoxLayout(self._config_panel)
        config_outer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        config_inner = QFrame()
        config_inner.setFixedWidth(400)
        config_inner.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        pro_layout = QVBoxLayout(config_inner)
        pro_layout.setContentsMargins(20, 20, 20, 20)
        pro_layout.setSpacing(12)

        pro_layout.addWidget(self._section_label("Configure UMAP Run"))

        # Run Name
        name_lbl = QLabel("Run Name:")
        name_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        pro_layout.addWidget(name_lbl)
        self._run_name_input = BioLineEdit("")
        self._run_name_input.setPlaceholderText("e.g., Global Overview")
        pro_layout.addWidget(self._run_name_input)

        # n_neighbors
        n_neigh_lbl_layout = QHBoxLayout()
        n_neigh_title = QLabel("Neighbors:")
        n_neigh_title.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        self._n_neigh_val_lbl = QLabel("15")
        self._n_neigh_val_lbl.setStyleSheet(f"color: {Colors.DNA_PRIMARY}; font-weight: bold; font-size: 11px;")
        n_neigh_lbl_layout.addWidget(n_neigh_title)
        n_neigh_lbl_layout.addStretch()
        n_neigh_lbl_layout.addWidget(self._n_neigh_val_lbl)
        pro_layout.addLayout(n_neigh_lbl_layout)

        self._n_neigh_slider = QSlider(Qt.Orientation.Horizontal)
        self._n_neigh_slider.setRange(5, 50)
        self._n_neigh_slider.setValue(15)
        self._n_neigh_slider.setToolTip("Higher = more global structure. Lower = finer local clusters.")
        self._n_neigh_slider.valueChanged.connect(lambda val: self._n_neigh_val_lbl.setText(str(val)))
        pro_layout.addWidget(self._n_neigh_slider)

        # min_dist
        min_dist_lbl_layout = QHBoxLayout()
        min_dist_title = QLabel("Min Distance:")
        min_dist_title.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        self._min_dist_val_lbl = QLabel("0.10")
        self._min_dist_val_lbl.setStyleSheet(f"color: {Colors.DNA_PRIMARY}; font-weight: bold; font-size: 11px;")
        min_dist_lbl_layout.addWidget(min_dist_title)
        min_dist_lbl_layout.addStretch()
        min_dist_lbl_layout.addWidget(self._min_dist_val_lbl)
        pro_layout.addLayout(min_dist_lbl_layout)

        self._min_dist_slider = QSlider(Qt.Orientation.Horizontal)
        self._min_dist_slider.setRange(1, 50)  # Represents 0.01 to 0.50
        self._min_dist_slider.setValue(10)
        self._min_dist_slider.setToolTip("Lower = tighter packed islands.")
        self._min_dist_slider.valueChanged.connect(lambda val: self._min_dist_val_lbl.setText(f"{val/100:.2f}"))
        pro_layout.addWidget(self._min_dist_slider)

        # n_events
        self._n_events_title_lbl = QLabel("Subsample Events: 10% (0 events)")
        self._n_events_title_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        pro_layout.addWidget(self._n_events_title_lbl)

        self._n_events_slider = QSlider(Qt.Orientation.Horizontal)
        self._n_events_slider.setRange(1, 100)
        self._n_events_slider.setValue(10)
        self._n_events_slider.setToolTip("Percentage of events to subsample. Max is all events.")
        self._n_events_slider.valueChanged.connect(self._on_subsample_changed)
        pro_layout.addWidget(self._n_events_slider)

        # Metric
        metric_lbl = QLabel("Distance Metric:")
        metric_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        pro_layout.addWidget(metric_lbl)

        self._metric_combo = BioComboBox()
        self._metric_combo.addItems(["euclidean", "cosine", "manhattan"])
        pro_layout.addWidget(self._metric_combo)

        # Random Seed
        seed_lbl = QLabel("Random Seed:")
        seed_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        pro_layout.addWidget(seed_lbl)

        self._seed_input = BioLineEdit("42")
        self._seed_input.setValidator(QIntValidator(0, 999999))
        pro_layout.addWidget(self._seed_input)

        # HDBSCAN Auto-Clustering
        hdbscan_lbl = QLabel("Auto-Clustering (HDBSCAN):")
        hdbscan_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px; font-weight: bold;")
        pro_layout.addWidget(hdbscan_lbl)

        self._run_hdbscan_cb = QCheckBox("Run HDBSCAN")
        self._run_hdbscan_cb.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        pro_layout.addWidget(self._run_hdbscan_cb)

        self._hdbscan_space_combo = BioComboBox()
        self._hdbscan_space_combo.addItem("High-Dimensional (Accurate)", "high_dim")
        self._hdbscan_space_combo.addItem("Low-Dimensional (Visual)", "low_dim")
        self._hdbscan_space_combo.setEnabled(False)
        pro_layout.addWidget(self._hdbscan_space_combo)

        self._min_cluster_size_box = BioSpinBox()
        self._min_cluster_size_box.setRange(2, 500)
        self._min_cluster_size_box.setValue(100)
        self._min_cluster_size_box.setPrefix("Min Cluster Size: ")
        self._min_cluster_size_box.setEnabled(False)
        pro_layout.addWidget(self._min_cluster_size_box)

        self._run_hdbscan_cb.toggled.connect(self._hdbscan_space_combo.setEnabled)
        self._run_hdbscan_cb.toggled.connect(self._min_cluster_size_box.setEnabled)

        # Channels Selection
        channels_lbl = QLabel("Select Channels:")
        channels_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px; font-weight: bold;")
        pro_layout.addWidget(channels_lbl)

        self._channel_list = BioListWidget()
        self._channel_list.setMaximumHeight(120)
        pro_layout.addWidget(self._channel_list)

        config_outer_layout.addWidget(config_inner)

        # 1: Results Panel (Instantiated after run)
        self._results_panel = QWidget()

        # 2: Animator
        self._animator = UmapAnimatorWidget()
        self._animator.animation_finished.connect(self._on_animation_finished)

        self._display_stack.addWidget(self._config_panel)
        self._display_stack.addWidget(self._results_panel)
        self._display_stack.addWidget(self._animator)

        right_layout.addWidget(self._display_stack, stretch=1)

        main_layout.addWidget(right_panel, stretch=1)

    def _apply_theme_styles(self) -> None:
        """Triggered dynamically when the global theme changes."""
        if hasattr(self, "_caption_lbl"):
            self._caption_lbl.setStyleSheet(
                f"color: {Colors.FG_SECONDARY}; font-size: 11px; line-height: 1.4; border: none; background: transparent;"
            )
        if hasattr(self, "_placeholder"):
            pass

    def _on_subsample_changed(self, value: int) -> None:
        num_events = int(self._total_events * (value / 100.0))
        self._n_events_title_lbl.setText(f"Subsample Events: {value}% ({num_events:,} events)")

    def on_sample_changed(self, sample_id: str) -> None:
        """Called when the active sample changes in the ribbon."""
        self._channel_list.clear()
        sample = self._state.data.experiment.samples.get(sample_id)
        if not sample:
            return

        from analysis.fcs_io import get_fluorescence_channels

        fluo_channels = get_fluorescence_channels(sample.fcs_data)

        for ch in fluo_channels:
            item = QListWidgetItem(ch)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._channel_list.addItem(item)

    def on_gate_changed(self, sample_id: str, gate_id: object) -> None:
        """Called when the active gate changes in the ribbon."""
        sample = self._state.data.experiment.samples.get(sample_id)
        if not sample or sample.fcs_data is None:
            self._total_events = 0
        else:
            if gate_id and sample.gate_tree:
                gate_node = sample.gate_tree.find_node_by_id(gate_id)
                if gate_node:
                    df = gate_node.apply_hierarchy(sample.fcs_data.events)
                    self._total_events = len(df)
                else:
                    self._total_events = len(sample.fcs_data.events)
            else:
                self._total_events = len(sample.fcs_data.events)

        self._on_subsample_changed(self._n_events_slider.value())

    def on_history_run_selected(self, run_data: dict | None) -> None:
        """When the user picks a past run from the ribbon history."""
        if run_data is None:
            # Blank out for New Run
            self._display_stack.setCurrentIndex(0)
            self._last_results = None
            self._animator.stop()
            self._replay_anim_btn.setEnabled(False)
            self._run_details_lbl.setText("Configure a new run in the center panel.")
            self._run_name_input.setText("")
            return

        self._last_results = run_data

        # Populate run details label
        details = []
        if "name" in run_data and run_data["name"]:
            details.append(f"Name: {run_data['name']}")
        details.append(f"Neighbors: {run_data.get('n_neighbors')}")
        details.append(f"Min Dist: {run_data.get('min_dist')}")
        details.append(f"Subsample: {run_data.get('percentage', 10.0)}% ({run_data.get('n_events', 0):,} events)")
        details.append(f"Metric: {run_data.get('metric')}")
        details.append(f"Seed: {run_data.get('random_seed')}")
        if run_data.get("run_hdbscan"):
            details.append("HDBSCAN: Yes")
        channels = run_data.get("channels", [])
        details.append(f"Channels ({len(channels)}): {', '.join(channels)}")

        self._run_details_lbl.setText("\n".join(details))

        self._display_stack.removeWidget(self._results_panel)
        self._results_panel.deleteLater()

        self._results_panel = ClusterResultsPanel(
            self._last_results, state=self._state, gate_coordinator=self._gate_coordinator
        )
        self._display_stack.insertWidget(1, self._results_panel)

        self._animator.stop()
        self._display_stack.setCurrentIndex(1)
        self._replay_anim_btn.setEnabled(True)

    def on_delete_run_requested(self, run_data: dict, ribbon: UmapRibbon) -> None:
        """Deletes a run from the history."""
        key = f"{run_data['sample_id']}::{run_data['node_id'] or 'root'}"
        if key in self._state.data.umap_results:
            runs = self._state.data.umap_results[key]
            # Find and remove matching run
            for i, r in enumerate(runs):
                if r is run_data:
                    runs.pop(i)
                    break
        ribbon.refresh_history()
        self.on_history_run_selected(None)

    def start_analysis(self, sample_id: str, node_id: object = None, ribbon: UmapRibbon | None = None) -> None:
        """Invoked by ribbon to trigger UMAP reduction."""
        if not sample_id:
            return

        self._is_analysis_running = True
        self._is_animation_playing = False

        # Get selected channels
        selected_channels = []
        for i in range(self._channel_list.count()):
            item = self._channel_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_channels.append(item.text())

        if not selected_channels:
            self._on_analysis_error("No channels selected. Please select at least one channel for UMAP.", ribbon)
            return

        percentage = self._n_events_slider.value() / 100.0
        n_events_to_sample = int(self._total_events * percentage) if self._total_events > 0 else 0
        n_events_to_sample = max(50, n_events_to_sample) if self._total_events > 50 else self._total_events

        params = UmapParams(
            target_sample_id=sample_id,
            target_node_id=node_id,  # None = All Events
            name=self._run_name_input.text().strip(),
            percentage=float(self._n_events_slider.value()),
            n_neighbors=self._n_neigh_slider.value(),
            min_dist=(self._min_dist_slider.value() / 100.0),
            n_events=n_events_to_sample,
            metric=self._metric_combo.currentText(),
            random_seed=int(self._seed_input.text() or "42"),
            run_hdbscan=self._run_hdbscan_cb.isChecked(),
            hdbscan_space=self._hdbscan_space_combo.currentData(),
            min_cluster_size=self._min_cluster_size_box.value(),
            channels=selected_channels,
        )

        self._progress_bar.setRange(0, 0)  # Indeterminate mode
        self._progress_bar.show()

        if ribbon:
            ribbon.set_running(True)
            gate_hint = f" (gate: {node_id[:8]}\u2026)" if node_id else " (all events)"
            ribbon.set_status(f"Running UMAP analysis{gate_hint}...")

        # Prepare and start animation in background — never block the main thread
        sample = self._state.data.experiment.samples.get(sample_id)
        if sample and sample.fcs_data is not None:
            from analysis.fcs_io import get_fluorescence_channels

            fluo_channels = get_fluorescence_channels(sample.fcs_data)

            events_df = sample.fcs_data.events
            if node_id and sample.gate_tree is not None:
                gate_node = sample.gate_tree.find_node_by_id(node_id)
                if gate_node is not None:
                    events_df = gate_node.apply_hierarchy(events_df)

            # Show animator pane immediately with a loading message
            self._animator.show_loading()
            self._display_stack.setCurrentIndex(2)

            state_ref = self._state
            animator_ref = self._animator

            def _prep_task():
                p = UmapAnimationDataPrep(
                    n_neighbors=params.n_neighbors,
                    random_seed=params.random_seed,
                )
                success = p.prepare(
                    events_df,
                    fluo_channels,
                    state_ref,
                    sample_id,
                    min_dist=params.min_dist,
                    color_marker_idx=0,
                )
                if not success:
                    return {"success": False, "prep": None}

                animator_ref.prepare_animation(p)
                return {"success": True, "prep": p}

            def _on_prep_done(results: dict):
                success = results.get("success", False)
                if success:
                    self._last_prep_data = results.get("prep")
                    self._is_animation_playing = True
                    self._display_stack.setCurrentIndex(2)
                    self._animator.start()
                else:
                    self._display_stack.setCurrentIndex(0)

                # Now launch background UMAP (sequential after prep, no concurrent numba)
                self._umap_service.run_analysis(
                    params=params,
                    on_done=lambda res: self._on_analysis_done(res, ribbon),
                    on_error_cb=lambda err: self._on_analysis_error(err, ribbon),
                    on_progress=self._progress_bar.setValue,
                )

            def _on_prep_error(err: str):
                self._display_stack.setCurrentIndex(0)
                self._on_analysis_error(f"Animation prep failed: {err}", ribbon)

            from biopro.core.task_scheduler import task_scheduler
            from biopro_sdk.plugin.managed_task import FunctionalTask

            task = FunctionalTask(_prep_task, name="UMAP Prep")
            worker = task_scheduler.submit(task, None)
            worker.finished.connect(_on_prep_done)
            worker.error.connect(_on_prep_error)

            # ⚠️ Background UMAP is kicked off INSIDE _on_prep_done (not here),
            # so the two numba contexts are always sequential, never concurrent.
            return  # early return — run_analysis called from callback below

        else:
            self._display_stack.setCurrentIndex(0)

        # Fallback: if no sample data, run analysis immediately
        self._umap_service.run_analysis(
            params=params,
            on_done=lambda results: self._on_analysis_done(results, ribbon),
            on_error_cb=lambda err: self._on_analysis_error(err, ribbon),
            on_progress=self._progress_bar.setValue,
        )

    def _on_analysis_done(self, results: dict[str, Any], ribbon: UmapRibbon | None) -> None:
        self._progress_bar.setRange(0, 100)  # Restore determinate mode
        self._progress_bar.hide()

        self._is_analysis_running = False

        if "error" in results:
            if ribbon:
                ribbon.set_running(False)
                ribbon.set_status("Error computing UMAP.")
            self._on_analysis_error(results["error"], ribbon)
            return

        if ribbon:
            ribbon.set_running(False)
            ribbon.set_status(f"Completed — {results['n_events']:,} events")

        embedding = results["embedding"]

        # 1. Perfectly align the full embedding to the mini-UMAP coordinate space.
        # This prevents any "jumping" or "flipping" when the animation ends,
        # and naturally scales the data without using hard clipping (which causes flat edges).
        if hasattr(self, "_last_prep_data") and self._last_prep_data and self._last_prep_data.final_2d is not None:
            import scipy.linalg

            n_sub = len(self._last_prep_data.final_2d)
            if len(embedding) >= n_sub:
                X_sub = embedding[:n_sub]
                Y = self._last_prep_data.final_2d

                # Centers
                X_mean = X_sub.mean(axis=0)
                Y_mean = Y.mean(axis=0)
                X_c = X_sub - X_mean
                Y_c = Y - Y_mean

                # Uniform scale factor
                scale_X = np.linalg.norm(X_c)
                scale_Y = np.linalg.norm(Y_c)

                if scale_X > 0:
                    # Normalize for rotation
                    X_c = X_c / scale_X
                    Y_c = Y_c / scale_Y

                    # Optimal orthogonal rotation/reflection R
                    U, _, Vt = scipy.linalg.svd(X_c.T @ Y_c)
                    R = U @ Vt

                    # Apply global transformation to the ENTIRE dataset
                    embedding = embedding - X_mean  # 1. Center
                    embedding = embedding / scale_X  # 2. Normalize scale
                    embedding = embedding @ R  # 3. Rotate to match animation
                    embedding = (embedding * scale_Y) + Y_mean  # 4. Scale and translate to animation space

        results["embedding"] = embedding
        self._last_results = results

        key = f"{results['sample_id']}::{results['node_id'] or 'root'}"
        if key not in self._state.data.umap_results:
            self._state.data.umap_results[key] = []
        self._state.data.umap_results[key].append(results)

        if ribbon:
            ribbon.blockSignals(True)
            ribbon.refresh_history()
            ribbon.select_last_run()
            ribbon.blockSignals(False)

        from biopro_sdk.plugin import CentralEventBus

        from analysis import events

        CentralEventBus.publish(events.UMAP_COMPLETED, {})

        # Create new results panel
        self._display_stack.removeWidget(self._results_panel)
        self._results_panel.deleteLater()

        self._results_panel = ClusterResultsPanel(
            self._last_results, state=self._state, gate_coordinator=self._gate_coordinator
        )
        self._display_stack.insertWidget(1, self._results_panel)

        self._replay_anim_btn.setEnabled(True)

        self._check_transition_to_results()

    def _check_transition_to_results(self) -> None:
        """Switch to static results if both the computation and animation are done."""
        if self._is_animation_playing or self._is_analysis_running:
            return
        if self._last_results is not None:
            self._animator.stop()
            self._display_stack.setCurrentIndex(1)

    def _on_animation_finished(self) -> None:
        self._is_animation_playing = False
        self._check_transition_to_results()

    def _play_animation(self) -> None:
        """Trigger the 25s animation playback."""
        self._is_animation_playing = True
        if not hasattr(self, "_last_prep_data") or not self._last_prep_data:
            return
        # Reset the poll counter so timing is fresh
        if hasattr(self._animator, "_anim_frame_counter"):
            self._animator._anim_frame_counter = 0
        self._display_stack.setCurrentIndex(2)
        self._animator.prepare_animation(self._last_prep_data)
        self._animator.start()

    def _on_analysis_error(self, error_msg: str, ribbon: UmapRibbon | None) -> None:
        self._progress_bar.setRange(0, 100)
        self._progress_bar.hide()
        if ribbon:
            ribbon.set_running(False)
            ribbon.set_status(f"Error: {error_msg}")

        self._run_details_lbl.setText(f"Analysis Failed:\n{error_msg}")
        self._display_stack.setCurrentIndex(0)
