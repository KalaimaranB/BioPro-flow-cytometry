"""GateHierarchy — top-level gate hierarchy panel (icicle chart redesign).

Preserves the complete public API of the original gate_hierarchy.py so that
main_panel.py and all other callers need no changes except wiring the new
propagation_mode_changed signal.

New public additions:
    Signal: propagation_mode_changed(bool)
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

try:
    from biopro.ui.theme import Colors, Fonts, theme_manager
except ImportError:

    class Colors:
        BG_DARKEST = "#0d1117"
        BG_DARK = "#161b22"
        BG_MEDIUM = "#21262d"
        FG_PRIMARY = "#e6edf3"
        FG_SECONDARY = "#8b949e"
        FG_DISABLED = "#484f58"
        BORDER = "#30363d"
        ACCENT_PRIMARY = "#00bcd4"
        ACCENT_NEGATIVE = "#ef5350"

    class Fonts:
        SIZE_SMALL = 11
        FAMILY_UI = "Inter, sans-serif"

    class _FakeManager:
        class _S:
            def connect(self, *a):
                pass

        theme_changed = _S()

    theme_manager = _FakeManager()

from biopro_sdk.plugin.events import CentralEventBus

from analysis import events
from analysis.state import FlowState

from .all_samples_popup import AllSamplesPopup
from .node_tree_engine import NodeTreeEngine
from .propagation_toggle import PropagationToggle
from .sample_view import SampleViewWidget


class GateHierarchy(QWidget):
    """Icicle-chart gate hierarchy panel for the lower-left sidebar.

    Backward-compatible public API:
        Signals:
            gate_double_clicked(node_id)
            selection_changed(node_id)
            gate_rename_requested(sample_id, node_id, new_name)
            gate_delete_requested(sample_id, node_id)
            copy_gates_requested(sample_id)

        New signal:
            propagation_mode_changed(bool)

        Methods:
            set_active_sample(sample_id)
            refresh()
            update_gate_stats(sample_id, node_id)
            update_all_sample_stats(sample_id)
    """

    # ── Signals (backward-compatible) ────────────────────────────────
    gate_double_clicked = pyqtSignal(str)
    selection_changed = pyqtSignal(str)
    gate_rename_requested = pyqtSignal(str, str, str)
    gate_delete_requested = pyqtSignal(str, str)
    copy_gates_requested = pyqtSignal(str)

    # New
    propagation_mode_changed = pyqtSignal(bool)

    def __init__(self, state: FlowState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._active_sample_id: str | None = None
        self._engine = NodeTreeEngine()

        self._setup_ui()
        self._setup_events()

    # ── UI construction ───────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header strip ──────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(72)
        header.setStyleSheet(f"background: {Colors.BG_DARK};" f" border-bottom: 1px solid {Colors.BORDER};")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(4)

        # Section label
        section_label = QLabel("GATING HIERARCHY")
        section_label.setStyleSheet(
            f"color: {Colors.FG_DISABLED}; font-size: 9px; font-weight: 700;"
            " letter-spacing: 1px; background: transparent;"
        )
        header_layout.addWidget(section_label)

        # Toggle + All Samples button row
        controls_row = QHBoxLayout()
        controls_row.setSpacing(6)

        self._toggle = PropagationToggle()
        self._toggle.propagation_mode_changed.connect(self._on_propagation_toggled)
        controls_row.addWidget(self._toggle, stretch=1)

        self._btn_all_samples = QPushButton("⊞")
        self._btn_all_samples.setToolTip("All Samples Overview")
        self._btn_all_samples.setFixedSize(28, 22)
        self._btn_all_samples.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_all_samples.setStyleSheet(f"""
            QPushButton {{
                background: {Colors.BG_MEDIUM};
                color: {Colors.ACCENT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {Colors.BORDER};
                color: #ffffff;
            }}
        """)
        self._btn_all_samples.clicked.connect(self._on_all_samples_clicked)
        controls_row.addWidget(self._btn_all_samples)

        header_layout.addLayout(controls_row)
        layout.addWidget(header)

        # ── Icicle scroll area ─────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {Colors.BG_DARKEST}; border: none; }}"
            f"QScrollBar:vertical {{ background: {Colors.BG_DARK}; width: 4px; }}"
            f"QScrollBar::handle:vertical {{ background: {Colors.BORDER}; border-radius: 2px; }}"
        )

        self._sample_view = SampleViewWidget(self._state)
        self._sample_view.node_clicked.connect(self._on_node_clicked)
        self._sample_view.node_double_clicked.connect(self._on_node_double_clicked)
        self._sample_view.rename_requested.connect(self._on_rename_requested)
        self._sample_view.delete_requested.connect(self._on_delete_requested)

        self._scroll.setWidget(self._sample_view)
        layout.addWidget(self._scroll, stretch=1)

        # ── Overlay Controls ──
        overlay_layout = QHBoxLayout(self._scroll)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        overlay_layout.setContentsMargins(0, 0, 16, 16)
        overlay_layout.setSpacing(8)
        
        btn_style = (
            f"QPushButton {{"
            f"  background: {Colors.BG_MEDIUM};"
            f"  color: {Colors.FG_PRIMARY};"
            f"  border: 1px solid {Colors.BORDER};"
            f"  border-radius: 4px;"
            f"  padding: 6px 12px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {Colors.BORDER};"
            f"  border: 1px solid {Colors.ACCENT_PRIMARY};"
            f"}}"
        )
        
        self.btn_zoom_in = QPushButton("Zoom In (+)")
        self.btn_zoom_in.setStyleSheet(btn_style)
        self.btn_zoom_in.clicked.connect(self._sample_view.zoom_in)
        
        self.btn_zoom_out = QPushButton("Zoom Out (-)")
        self.btn_zoom_out.setStyleSheet(btn_style)
        self.btn_zoom_out.clicked.connect(self._sample_view.zoom_out)
        
        self.btn_fit = QPushButton("Fit View (F)")
        self.btn_fit.setStyleSheet(btn_style)
        self.btn_fit.clicked.connect(self._sample_view.fit_view)
        
        overlay_layout.addWidget(self.btn_zoom_out)
        overlay_layout.addWidget(self.btn_zoom_in)
        overlay_layout.addWidget(self.btn_fit)

        # ── Empty state ───────────────────────────────────────────────
        self._empty_label = QLabel("No gates applied.\n\n" "Select a sample and use\n" "the toolbar to draw a gate.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(
            f"color: {Colors.FG_DISABLED}; font-size: {Fonts.SIZE_SMALL}px;"
            f" background: {Colors.BG_DARKEST}; padding: 24px;"
        )
        layout.addWidget(self._empty_label)

        # ── All Samples Popup (created once, shown on demand) ─────────
        self._popup = AllSamplesPopup(self.window())
        self._popup.sample_selected.connect(self._on_popup_sample_selected)

    def _setup_events(self) -> None:
        CentralEventBus.subscribe(events.GATE_CREATED, self._on_gate_change)
        CentralEventBus.subscribe(events.GATE_RENAMED, self._on_gate_change)
        CentralEventBus.subscribe(events.GATE_DELETED, self._on_gate_change)

    # ── Public API (backward-compatible) ─────────────────────────────

    def set_active_sample(self, sample_id: str | None) -> None:
        """Update the active sample and refresh the icicle."""
        self._active_sample_id = sample_id
        self.refresh()

    def refresh(self) -> None:
        """Full rebuild of the icicle from current state."""
        sid = self._active_sample_id or self._state.view.current_sample_id
        if not sid:
            self._show_empty(True)
            return

        sample = self._state.data.experiment.samples.get(sid)
        if sample is None:
            self._show_empty(True)
            return

        total_events = 0
        if sample.fcs_data is not None:
            total_events = sample.fcs_data.num_events

        rects = self._engine.compute(sample.gate_tree, total_events)
        has_gates = len(rects) > 1

        if not has_gates:
            self._show_empty(True)
            return

        self._show_empty(False)
        self._sample_view.set_rects(rects)

    def update_gate_stats(self, sample_id: str, node_id: str = "") -> None:
        """Incremental stats update — refreshes the whole icicle for simplicity."""
        sid = self._active_sample_id or self._state.view.current_sample_id
        if sample_id == sid:
            self.refresh()

    def update_all_sample_stats(self, sample_id: str) -> None:
        sid = self._active_sample_id or self._state.view.current_sample_id
        if sample_id == sid:
            self.refresh()

    # ── Compatibility shim: _gate_item_map ───────────────────────────
    # main_panel.py accesses _gate_item_map to sync tree selection.
    # We provide a no-op dict so no AttributeError is raised.

    @property
    def _gate_item_map(self) -> dict:
        return {}

    # ── Internal event handlers ───────────────────────────────────────

    def _on_gate_change(self, _data: dict) -> None:
        self.refresh()

    def _on_propagation_toggled(self, enabled: bool) -> None:
        self.propagation_mode_changed.emit(enabled)

    def _on_all_samples_clicked(self) -> None:
        sid = self._active_sample_id or self._state.view.current_sample_id
        if not sid:
            return
        self._popup = AllSamplesPopup(self.window())
        self._popup.sample_selected.connect(self._on_popup_sample_selected)
        self._popup.show_near(self._btn_all_samples, self._state, sid)

    def _on_popup_sample_selected(self, sample_id: str) -> None:
        self._popup.hide()
        self.set_active_sample(sample_id)

    def _on_node_clicked(self, node_id: str) -> None:
        self._sample_view.set_selected(node_id)
        self.selection_changed.emit(node_id)

    def _on_node_double_clicked(self, node_id: str) -> None:
        self.gate_double_clicked.emit(node_id)

    def _on_rename_requested(self, node_id: str) -> None:
        sid = self._active_sample_id or self._state.view.current_sample_id
        if not sid:
            return
        sample = self._state.data.experiment.samples.get(sid)
        if not sample:
            return
        node = sample.gate_tree.find_node_by_id(node_id)
        current_name = node.name if node else ""

        from PyQt6.QtWidgets import QInputDialog, QLineEdit

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Population",
            "Enter new name:",
            QLineEdit.EchoMode.Normal,
            current_name,
        )
        if ok and new_name:
            self.gate_rename_requested.emit(sid, node_id, new_name)

    def _on_delete_requested(self, node_id: str) -> None:
        sid = self._active_sample_id or self._state.view.current_sample_id
        if sid:
            self.gate_delete_requested.emit(sid, node_id)

    # ── Helpers ───────────────────────────────────────────────────────

    def _show_empty(self, empty: bool) -> None:
        self._scroll.setVisible(not empty)
        self._empty_label.setVisible(empty)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Re-layout on resize so proportions stay correct
        self.refresh()
