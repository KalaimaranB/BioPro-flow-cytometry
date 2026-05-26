"""UMAP Viewer — UI component for visualizing and configuring UMAP reduction.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Optional
import numpy as np
import scipy.spatial

from PyQt6.QtWidgets import (
    QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QSpinBox, QComboBox, QStackedWidget, QProgressBar, QLineEdit,
    QPushButton, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QIntValidator, QPainter, QColor, QBrush, QCursor

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
import matplotlib.pyplot as plt

from ...analysis.state import FlowState
from ...analysis.services.umap_service import UmapService, UmapParams
from ...analysis.animation.animation_prep import UmapAnimationDataPrep
from .umap_animator_widget import UmapAnimatorWidget
from biopro.ui.theme import Colors, Fonts

if TYPE_CHECKING:
    from ..ribbons.umap_ribbon import UmapRibbon


# Button toggle styles
_STYLE_ON_BLUE  = f"QPushButton {{ background-color: {Colors.ACCENT_PRIMARY}; color: #ffffff; border: 1px solid {Colors.BORDER_FOCUS}; border-radius: 4px; padding: 4px 12px; font-size: 11px; font-weight: bold; }}"
_STYLE_ON_GREEN = f"QPushButton {{ background-color: {Colors.ACCENT_SUCCESS}; color: #ffffff; border: 1px solid #3fb950; border-radius: 4px; padding: 4px 12px; font-size: 11px; font-weight: bold; }}"
_STYLE_OFF      = f"QPushButton {{ background-color: {Colors.BG_MEDIUM}; color: {Colors.FG_SECONDARY}; border: 1px solid {Colors.BORDER}; border-radius: 4px; padding: 4px 12px; font-size: 11px; }}"
_STYLE_OFF_HOVER = f"QPushButton:hover {{ background-color: {Colors.BG_LIGHT}; color: {Colors.FG_PRIMARY}; }}"

_COMBO_STYLE = f"""
    QComboBox {{
        background-color: {Colors.BG_MEDIUM};
        color: {Colors.FG_PRIMARY};
        border: 1px solid {Colors.BORDER};
        border-radius: 4px;
        padding: 4px;
    }}
    QComboBox:disabled {{
        color: {Colors.FG_SECONDARY};
    }}
    QComboBox QAbstractItemView {{
        background-color: {Colors.BG_DARK};
        color: {Colors.FG_PRIMARY};
        selection-background-color: {Colors.ACCENT_PRIMARY};
        outline: 0px;
    }}
"""

class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(40, 22)
        self._checked = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
    def setChecked(self, value: bool):
        self._checked = value
        self.update()
        
    def isChecked(self) -> bool:
        return self._checked
        
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._checked = not self._checked
            self.toggled.emit(self._checked)
            self.update()
            
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background pill
        if self._checked:
            bg_color = QColor(Colors.ACCENT_PRIMARY) # Pro (Blue)
        else:
            bg_color = QColor(Colors.FG_DISABLED) # Student (Grey)
            
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        rect = self.rect()
        painter.drawRoundedRect(0, 0, rect.width(), rect.height(), 11, 11)
        
        # Draw knob
        painter.setBrush(QBrush(QColor("#ffffff")))
        if self._checked:
            # right side
            painter.drawEllipse(rect.width() - 20, 2, 18, 18)
        else:
            # left side
            painter.drawEllipse(2, 2, 18, 18)
            
        painter.end()


class UmapViewer(QWidget):
    """Component that plots the UMAP embedding and exposes Student/Pro configurations."""

    def __init__(self, state: FlowState, umap_service: UmapService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._umap_service = umap_service
        self._student_mode = True
        
        self._is_animation_playing = False
        self._is_analysis_running = False
        
        self._last_results: Optional[dict[str, Any]] = None
        self._kdtree: Optional[scipy.spatial.KDTree] = None
        
        # Colorbar reference to remove/update
        self._colorbar = None
        self._scatter = None
        
        self._setup_ui()



    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-weight: bold; font-size: 11px; text-transform: uppercase;")
        return lbl

    def _setup_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # ── Left Control Panel (220px) ──
        left_panel = QFrame()
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet(f"""
            QFrame {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.BORDER};
                border-radius: 8px;
            }}
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(14)

        # Student / Pro Mode Selector
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)
        
        student_lbl = QLabel("🎓 Student")
        student_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-weight: bold; font-size: 11px;")
        
        self._mode_switch = ToggleSwitch()
        self._mode_switch.setChecked(not self._student_mode)
        self._mode_switch.toggled.connect(self._on_mode_toggled)
        
        pro_lbl = QLabel("🔬 Pro")
        pro_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-weight: bold; font-size: 11px;")
        
        mode_layout.addWidget(student_lbl)
        mode_layout.addWidget(self._mode_switch)
        mode_layout.addWidget(pro_lbl)
        mode_layout.addStretch()
        left_layout.addLayout(mode_layout)

        # ── Group 1: Visual Options (Always Visible) ──
        vis_group = QWidget()
        vis_group.setStyleSheet("background: transparent; border: none;")
        vis_layout = QVBoxLayout(vis_group)
        vis_layout.setContentsMargins(0, 0, 0, 0)
        vis_layout.setSpacing(6)
        
        vis_layout.addWidget(self._section_label("Visual Options"))
        
        # Visual Options (Color By)
        color_lbl = QLabel("Color By Marker:")
        color_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        vis_layout.addWidget(color_lbl)
        
        self._color_by_combo = QComboBox()
        self._color_by_combo.setStyleSheet(_COMBO_STYLE)
        self._color_by_combo.currentIndexChanged.connect(self._on_color_marker_changed)
        self._color_by_combo.setEnabled(False)
        vis_layout.addWidget(self._color_by_combo)
        
        # Replay Animation Button
        self._replay_anim_btn = QPushButton("▶ Replay Animation")
        self._replay_anim_btn.setStyleSheet(_STYLE_OFF)
        self._replay_anim_btn.setEnabled(False)
        self._replay_anim_btn.clicked.connect(self._play_animation)
        vis_layout.addWidget(self._replay_anim_btn)
        
        vis_layout.addSpacing(10)
        left_layout.addWidget(vis_group)

        # ── Group 2: Pro Parameters (Hidden in Student Mode) ──
        self._pro_container = QWidget()
        self._pro_container.setStyleSheet("background: transparent; border: none;")
        pro_layout = QVBoxLayout(self._pro_container)
        pro_layout.setContentsMargins(0, 0, 0, 0)
        pro_layout.setSpacing(12)
        
        pro_layout.addWidget(self._section_label("Umap Parameters"))

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
        n_events_lbl = QLabel("Subsample Events:")
        n_events_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        pro_layout.addWidget(n_events_lbl)
        
        self._n_events_box = QSpinBox()
        self._n_events_box.setRange(1000, 100000)
        self._n_events_box.setSingleStep(5000)
        self._n_events_box.setValue(10000)
        self._n_events_box.setStyleSheet(f"""
            QSpinBox {{
                background-color: {Colors.BG_MEDIUM};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 4px;
            }}
        """)
        pro_layout.addWidget(self._n_events_box)

        # Metric
        metric_lbl = QLabel("Distance Metric:")
        metric_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        pro_layout.addWidget(metric_lbl)

        self._metric_combo = QComboBox()
        self._metric_combo.addItems(["euclidean", "cosine", "manhattan"])
        self._metric_combo.setStyleSheet(_COMBO_STYLE)
        pro_layout.addWidget(self._metric_combo)

        # Random Seed
        seed_lbl = QLabel("Random Seed:")
        seed_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        pro_layout.addWidget(seed_lbl)

        self._seed_input = QLineEdit("42")
        self._seed_input.setValidator(QIntValidator(0, 999999))
        self._seed_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Colors.BG_MEDIUM};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 4px;
            }}
        """)
        pro_layout.addWidget(self._seed_input)

        left_layout.addWidget(self._pro_container)

        # ── Group 3: Educational Caption (Default Student Mode explanation) ──
        self._caption_lbl = QLabel(
            "🎓 <b>What is UMAP?</b><br/>"
            "Each dot is a single cell. Cells that share similar protein marker expressions "
            "are placed close together, forming 'islands' or clusters.<br/><br/>"
            "This makes it easy to visually identify CD4+ T-cells, B-cells, and other populations "
            "in one view!"
        )
        self._caption_lbl.setWordWrap(True)
        self._caption_lbl.setStyleSheet(f"""
            QLabel {{
                color: {Colors.FG_SECONDARY};
                font-size: 11px;
                line-height: 1.4;
                border: none;
                background: transparent;
            }}
        """)
        left_layout.addWidget(self._caption_lbl)
        
        left_layout.addStretch()
        main_layout.addWidget(left_panel)

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

        # Stacked display (Placeholder vs Canvas)
        self._display_stack = QStackedWidget()
        self._display_stack.setStyleSheet(f"background-color: {Colors.BG_DARKER}; border-radius: 8px;")
        
        # Placeholder
        self._placeholder = QLabel("🧬 UMAP Embeddings Workspace\n\nSelect a sample and gate, then click 'Run UMAP'.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: 14px;")
        
        # Static Plot Viewer
        self._canvas_frame = QFrame()
        self._canvas_frame.setStyleSheet("border: none; background: transparent;")
        canvas_box = QVBoxLayout(self._canvas_frame)
        canvas_box.setContentsMargins(0, 0, 0, 0)
        
        self._figure = Figure(facecolor=Colors.BG_DARK)
        self._canvas = FigureCanvasQTAgg(self._figure)
        canvas_box.addWidget(self._canvas)
        
        self._ax = self._figure.add_subplot(111)
        self._style_axes()
        self._colorbar = None
        self._scatter = None
        
        self._canvas.mpl_connect("motion_notify_event", self._on_mouse_hover)
        
        # Animator
        self._animator = UmapAnimatorWidget()
        self._animator.animation_finished.connect(self._on_animation_finished)
        
        self._display_stack.addWidget(self._placeholder)
        self._display_stack.addWidget(self._canvas_frame)
        self._display_stack.addWidget(self._animator)
        
        right_layout.addWidget(self._display_stack, stretch=1)
        
        main_layout.addWidget(right_panel, stretch=1)

        # ── Tooltip Initialization ──
        self._tooltip = QLabel(self)
        self._tooltip.setStyleSheet(f"""
            QLabel {{
                background-color: {Colors.BG_DARK};
                color: {Colors.FG_PRIMARY};
                border: 1px solid {Colors.BORDER_LIGHT};
                border-radius: 6px;
                padding: 10px;
                font-family: {Fonts.FAMILY_MONO};
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        self._tooltip.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self._tooltip.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._tooltip.hide()

        # Initial visibility state
        self._set_student_mode(self._student_mode)

    def _style_axes(self) -> None:
        self._ax.set_facecolor("#0d1117")
        self._ax.tick_params(colors=Colors.FG_SECONDARY, labelsize=9)
        for spine in ("bottom", "left"):
            self._ax.spines[spine].set_color(Colors.BORDER)
        for spine in ("top", "right"):
            self._ax.spines[spine].set_visible(False)
        self._ax.set_title("UMAP Reduction Space", color=Colors.FG_PRIMARY, fontsize=12, fontweight='bold', pad=12)

    def _apply_theme_styles(self) -> None:
        """Triggered dynamically when the global theme changes."""
        if hasattr(self, '_mode_switch'):
            self._mode_switch.update()
        
        # Make sure our inline styled labels re-fetch the new Colors.* definitions
        if hasattr(self, '_caption_lbl'):
            self._caption_lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: 11px; line-height: 1.4; border: none; background: transparent;")
        if hasattr(self, '_placeholder'):
            self._placeholder.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_LARGE}px; border: 1px dashed {Colors.BORDER}; border-radius: 8px; background-color: {Colors.BG_DARKEST};")
        if hasattr(self, '_tooltip'):
            self._tooltip.setStyleSheet(f"background-color: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; border: 1px solid {Colors.BORDER_LIGHT}; border-radius: 6px; padding: 10px; font-family: {Fonts.FAMILY_MONO}; font-size: 10px; font-weight: bold;")
            
        if self._last_results:
            self._update_plot()

    def _on_mode_toggled(self, is_pro: bool) -> None:
        self._set_student_mode(not is_pro)

    def _set_student_mode(self, student_on: bool) -> None:
        self._student_mode = student_on
        self._pro_container.setVisible(not student_on)
        
        if student_on:
            self._caption_lbl.setText(
                "🎓 <b>What is UMAP?</b><br/>"
                "Each dot is a single cell. Cells that share similar protein marker expressions "
                "are placed close together, forming 'islands' or clusters.<br/><br/>"
                "This makes it easy to visually identify CD4+ T-cells, B-cells, and other populations "
                "in one view!"
            )
        else:
            self._caption_lbl.setText(
                "🔬 <b>Pro Mode Active</b><br/>"
                "Exposes parameters to control UMAP topology, cluster spacing, metrics, "
                "and subsampling settings."
            )

    def start_analysis(self, sample_id: str, node_id: object = None, ribbon: "UmapRibbon | None" = None) -> None:
        """Invoked by ribbon to trigger UMAP reduction."""
        if not sample_id:
            return
            
        self._is_analysis_running = True
        self._is_animation_playing = False
        
        params = UmapParams(
            target_sample_id=sample_id,
            target_node_id=node_id,  # None = All Events
            n_neighbors=self._n_neigh_slider.value() if not self._student_mode else 15,
            min_dist=(self._min_dist_slider.value() / 100.0) if not self._student_mode else 0.1,
            n_events=self._n_events_box.value() if not self._student_mode else 10000,
            metric=self._metric_combo.currentText() if not self._student_mode else "euclidean",
            random_seed=int(self._seed_input.text() or "42") if not self._student_mode else 42
        )
        
        self._progress_bar.setValue(0)
        self._progress_bar.show()
        
        if ribbon:
            ribbon.set_running(True)
            gate_hint = f" (gate: {node_id[:8]}\u2026)" if node_id else " (all events)"
            ribbon.set_status(f"Running UMAP analysis{gate_hint}...")

        # Prepare and start animation in background — never block the main thread
        sample = self._state.experiment.samples.get(sample_id)
        if sample and sample.fcs_data is not None:
            from ...analysis.fcs_io import get_fluorescence_channels
            from PyQt6.QtCore import QThread
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
            animator_ref = self._animator  # capture for thread

            class _PrepThread(QThread):
                def __init__(self):
                    super().__init__()
                    self.prep: UmapAnimationDataPrep | None = None
                    self.success = False

                def run(self):
                    # Step 1: Run mini-UMAP with the SAME params user configured
                    # (n_neighbors, min_dist, seed) so the layout matches the final result
                    p = UmapAnimationDataPrep(
                        n_neighbors=params.n_neighbors,
                        random_seed=params.random_seed,
                    )
                    self.success = p.prepare(
                        events_df, fluo_channels, state_ref, sample_id,
                        min_dist=params.min_dist,
                        color_marker_idx=0,
                    )
                    if not self.success:
                        return

                    self.prep = p

                    # Step 2: Pre-compute ALL 750 animation frames here in the background.
                    # This is the expensive Python loop (segment building) that was freezing
                    # the main thread. Moving it here means _play_animation() just calls start().
                    animator_ref.prepare_animation(p)

            self._prep_thread = _PrepThread()

            def _on_prep_done():
                # Both mini-UMAP and frame pre-computation are done.
                # Safe to start the background full UMAP now (sequential, no concurrent numba).
                self._tooltip.hide()
                if self._prep_thread and self._prep_thread.success and self._prep_thread.prep:
                    self._last_prep_data = self._prep_thread.prep
                    # Frames already pre-computed — just start the timer loop
                    self._is_animation_playing = True
                    self._display_stack.setCurrentIndex(2)
                    self._animator.start()
                else:
                    self._display_stack.setCurrentIndex(0)

                # Now launch background UMAP (sequential after prep, no concurrent numba)
                self._umap_service.run_analysis(
                    params=params,
                    on_done=lambda results: self._on_analysis_done(results, ribbon),
                    on_error_cb=lambda err: self._on_analysis_error(err, ribbon),
                    on_progress=self._progress_bar.setValue
                )

            self._prep_thread.finished.connect(_on_prep_done)
            self._prep_thread.start()

            # ⚠️  Background UMAP is kicked off INSIDE _on_prep_done (not here),
            # so the two numba contexts are always sequential, never concurrent.
            return  # early return — run_analysis called from callback below

        else:
            self._display_stack.setCurrentIndex(0)

        # Hide tooltip just in case
        self._tooltip.hide()

        # Fallback: if no sample data, run analysis immediately
        self._umap_service.run_analysis(
            params=params,
            on_done=lambda results: self._on_analysis_done(results, ribbon),
            on_error_cb=lambda err: self._on_analysis_error(err, ribbon),
            on_progress=self._progress_bar.setValue
        )

    def _on_analysis_done(self, results: dict[str, Any], ribbon: UmapRibbon | None) -> None:
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
                    embedding = embedding - X_mean           # 1. Center
                    embedding = embedding / scale_X          # 2. Normalize scale
                    embedding = embedding @ R                # 3. Rotate to match animation
                    embedding = (embedding * scale_Y) + Y_mean # 4. Scale and translate to animation space

        results["embedding"] = embedding
        self._last_results = results
        self._kdtree = scipy.spatial.KDTree(results["embedding"])

        # Populate Color By combo
        self._color_by_combo.blockSignals(True)
        self._color_by_combo.clear()
        self._color_by_combo.addItems(results["channels"])
        self._color_by_combo.setEnabled(True)
        self._replay_anim_btn.setEnabled(True)
        self._color_by_combo.blockSignals(False)

        self._check_transition_to_results()

    def _check_transition_to_results(self) -> None:
        """Switch to static results if both the computation and animation are done."""
        if self._is_animation_playing or self._is_analysis_running:
            return
        if self._last_results is not None:
            self._animator.stop()
            self._display_stack.setCurrentIndex(1)
            self._update_plot()

    def _on_animation_finished(self) -> None:
        self._is_animation_playing = False
        self._check_transition_to_results()

    def _play_animation(self) -> None:
        """Trigger the 25s animation playback."""
        self._is_animation_playing = True
        if not hasattr(self, '_last_prep_data') or not self._last_prep_data:
            return
        # Reset the poll counter so timing is fresh
        if hasattr(self._animator, '_anim_frame_counter'):
            self._animator._anim_frame_counter = 0
        self._display_stack.setCurrentIndex(2)
        self._animator.prepare_animation(self._last_prep_data)
        self._animator.start()

    def _on_analysis_error(self, error_msg: str, ribbon: UmapRibbon | None) -> None:
        self._progress_bar.hide()
        if ribbon:
            ribbon.set_running(False)
            ribbon.set_status(f"Error: {error_msg}")
            
        self._placeholder.setText(f"🧬 UMAP Embeddings Workspace\n\nAnalysis Failed:\n{error_msg}")
        self._display_stack.setCurrentIndex(0)

    def _update_plot(self) -> None:
        if not self._last_results:
            return

        self._figure.clear()
        self._ax = self._figure.add_subplot(111)
        self._style_axes()
        
        embedding = self._last_results["embedding"]
        channels = self._last_results["channels"]
        intensities = self._last_results["intensities"]

        # Color based on active marker selection
        idx = self._color_by_combo.currentIndex()
        if idx < 0:
            idx = 0
            
        color_data = intensities[:, idx]
        
        # Scatter plot
        self._scatter = self._ax.scatter(
            embedding[:, 0],
            embedding[:, 1],
            c=color_data,
            cmap="viridis",
            s=2.0,
            alpha=0.75,
            edgecolors="none"
        )
        
        # Configure colorbar
        self._colorbar = self._figure.colorbar(self._scatter, ax=self._ax)
        self._colorbar.ax.yaxis.set_tick_params(colors=Colors.FG_SECONDARY, labelsize=8)
        self._colorbar.outline.set_color(Colors.BORDER)
        
        label_text = self._color_by_combo.currentText()
        self._colorbar.set_label(f"{label_text} Intensity", color=Colors.FG_SECONDARY, fontsize=9, labelpad=8)
        
        self._canvas.draw()

    def _on_color_marker_changed(self, index: int) -> None:
        if self._last_results and index >= 0:
            # Revert to static plot if they change markers while animation is frozen
            self._display_stack.setCurrentIndex(1)
            self._update_plot()

    def _on_mouse_hover(self, event) -> None:
        if self._kdtree is None or self._last_results is None:
            return

        # Check if cursor is inside the axes
        if event.inaxes != self._ax:
            self._tooltip.hide()
            return

        x, y = event.xdata, event.ydata
        
        # Query 20 nearest neighbours
        dists, indices = self._kdtree.query([x, y], k=20)
        
        # Compute mean intensities
        intensities = self._last_results["intensities"][indices]
        mean_expr = np.mean(intensities, axis=0)
        
        # Normalize to full min/max range of each marker to scale text-based bars
        min_vals = np.min(self._last_results["intensities"], axis=0)
        max_vals = np.max(self._last_results["intensities"], axis=0)
        
        # Build text-based bar chart
        tooltip_lines = ["NEIGHBOR EXPRESSION (N=20)", "─" * 32]
        
        channels = self._last_results["channels"]
        for i, ch in enumerate(channels):
            val = mean_expr[i]
            mn, mx = min_vals[i], max_vals[i]
            
            # Simple [0,1] normalization for bars
            norm = (val - mn) / (mx - mn + 1e-6)
            norm = max(0.0, min(1.0, norm))
            
            # Create a 10-char bar: e.g. "████░░░░░░"
            bar_len = 10
            filled = int(round(norm * bar_len))
            filled = max(0, min(bar_len, filled))
            bar = "█" * filled + "░" * (bar_len - filled)
            
            # Shorten label if too long (CD45RA (V450) -> CD45RA)
            short_ch = ch.split(" (")[0][:12]
            
            tooltip_lines.append(f"{short_ch:<12} {bar} {val:.2f}")

        self._tooltip.setText("\n".join(tooltip_lines))

        # Use global cursor position mapped into this widget's coordinate space.
        # This avoids the double-offset bug where guiEvent.pos() (canvas-local)
        # + mapTo(self) adds the canvas position a second time.
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        
        # Offset to prevent cursor overlap
        tip_x = local_pos.x() + 16
        tip_y = local_pos.y() + 16
        
        # Flip to the left/above if we'd bleed off the widget edge
        if tip_x + self._tooltip.width() > self.width():
            tip_x = local_pos.x() - self._tooltip.width() - 8
        if tip_y + self._tooltip.height() > self.height():
            tip_y = local_pos.y() - self._tooltip.height() - 8

        self._tooltip.move(tip_x, tip_y)
        self._tooltip.show()

    def leaveEvent(self, event) -> None:
        """Ensure tooltip hides when mouse leaves viewer."""
        self._tooltip.hide()
        super().leaveEvent(event)
