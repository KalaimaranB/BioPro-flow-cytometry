"""Spectral Viewer Panel — Overlay fluorophore AB / EX / EM spectra from FPbase.

Features:
  - Global AB / EX / EM toggle buttons
  - Student / Pro annotation mode for spectral-overlap callouts
  - Live FPbase search autocomplete
  - QY / EC metadata chips on active spectra
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from biopro.shared.ui.ui_components import PrimaryButton
from biopro.ui.theme import Colors, Fonts

if TYPE_CHECKING:
    from ...analysis.biology_services import FluorophoreService
    from ...analysis.state import FlowState


# ── Button style helpers ──────────────────────────────────────────────────────

def _btn_style(bg: str, fg: str, border: str, hover_bg: str = "") -> str:
    hover = f"QPushButton:hover {{ background: {hover_bg}; color: #c9d1d9; }}" if hover_bg else ""
    return (
        f"QPushButton {{ background: {bg}; color: {fg}; border: 1px solid {border};"
        f" border-radius: 4px; padding: 4px 11px; font-size: 11px; }}"
        + hover
    )

_STYLE_ON_BLUE    = _btn_style("#1f6feb", "#ffffff", "#388bfd")
_STYLE_ON_GREEN   = _btn_style("#1a7f37", "#ffffff", "#3fb950")
_STYLE_OFF        = _btn_style("#21262d", "#8b949e", "#30363d", hover_bg="#30363d")


# ── Drop canvas ───────────────────────────────────────────────────────────────

class DropCanvas(QFrame):
    """Transparent frame wrapping the matplotlib canvas; accepts drag-drops from the channel list."""

    def __init__(self, viewer: SpectralViewer, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._viewer = viewer
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.canvas_layout = lay

    def dragEnterEvent(self, event):
        if event.source() is self._viewer._source_list:
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.source() is self._viewer._source_list:
            item = event.source().currentItem()
            if item:
                self._viewer._add_fluor(item.data(Qt.ItemDataRole.UserRole))
            event.acceptProposedAction()


# ── Main widget ───────────────────────────────────────────────────────────────

class SpectralViewer(QWidget):
    """Central workspace panel: plots AB / EX / EM spectra with overlap annotation."""

    def __init__(
        self,
        state: FlowState,
        fluor_service: FluorophoreService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._state = state
        self._fluor_service = fluor_service
        self._active_fluors: Dict[str, Dict[str, Any]] = {}

        # Global display toggles (defaults: show EX + EM, student mode on)
        self._show_ab = False
        self._show_ex = True
        self._show_em = True
        self._student_mode = True
        self._comp_value = 0.0  # 0.0 to 1.0
        self._hidden_annotations = set()
        self._band_warning_dismissed = False
        self._mpl_annotations = []

        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _toggle_btn(self, label: str, active: bool, style_on: str = _STYLE_ON_BLUE) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setFixedHeight(28)
        btn.setStyleSheet(style_on if active else _STYLE_OFF)
        btn.toggled.connect(lambda checked, b=btn, s=style_on: b.setStyleSheet(s if checked else _STYLE_OFF))
        return btn

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-weight: bold; font-size: 11px;")
        return lbl

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)

        # FPbase search
        left.addWidget(self._section_label("Search FPbase:"))

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("e.g. APC/Cy7, Alexa Fluor 488…")
        self._search_input.setStyleSheet(
            f"background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 4px; padding: 4px;"
        )
        left.addWidget(self._search_input)

        self._search_results = QListWidget()
        self._search_results.setStyleSheet(
            f"background: {Colors.BG_DARKER}; color: {Colors.FG_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 4px;"
        )
        self._search_results.setMaximumHeight(120)
        self._search_results.hide()
        left.addWidget(self._search_results)

        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_results.itemClicked.connect(self._on_search_result_clicked)

        # Channel list
        left.addWidget(self._section_label("Available Channels:"))
        self._source_list = QListWidget()
        self._source_list.setStyleSheet(
            f"background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 4px;"
        )
        self._source_list.setDragEnabled(True)
        self._source_list.itemDoubleClicked.connect(self._on_source_double_clicked)
        left.addWidget(self._source_list, stretch=1)

        hint = QLabel("↕ Double-click or drag onto plot")
        hint.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")
        left.addWidget(hint)

        # Active spectra list
        left.addWidget(self._section_label("Active Spectra:"))
        self._list_widget = QListWidget()
        self._list_widget.setStyleSheet(
            f"background: {Colors.BG_DARKER}; color: {Colors.FG_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 4px;"
        )
        self._list_widget.setMaximumHeight(130)
        left.addWidget(self._list_widget)

        remove_hint = QLabel("Double-click to remove")
        remove_hint.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")
        left.addWidget(remove_hint)

        self._list_widget.itemDoubleClicked.connect(self._remove_fluor)

        root.addLayout(left, stretch=1)

        # ── Right panel ───────────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        toolbar.addWidget(QLabel("Show:"))

        self._btn_ab = self._toggle_btn("AB  Absorbance", active=False)
        self._btn_ex = self._toggle_btn("EX  Excitation", active=True)
        self._btn_em = self._toggle_btn("EM  Emission",   active=True)

        self._btn_ab.toggled.connect(lambda c: self._set_mode("ab", c))
        self._btn_ex.toggled.connect(lambda c: self._set_mode("ex", c))
        self._btn_em.toggled.connect(lambda c: self._set_mode("em", c))

        toolbar.addWidget(self._btn_ab)
        toolbar.addWidget(self._btn_ex)
        toolbar.addWidget(self._btn_em)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {Colors.BORDER};")
        toolbar.addWidget(sep)

        self._btn_student = self._toggle_btn("🎓 Student", active=True, style_on=_STYLE_ON_GREEN)
        self._btn_student.setToolTip(
            "Student mode: plain-language overlap explanations.\n"
            "Pro mode: numerical overlap coefficients."
        )
        self._btn_student.toggled.connect(self._on_student_toggle)
        toolbar.addWidget(self._btn_student)

        toolbar.addStretch()

        clear_btn = QPushButton("✕ Clear All")
        clear_btn.setStyleSheet(_STYLE_OFF)
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self._clear_all)
        toolbar.addWidget(clear_btn)

        right.addLayout(toolbar)

        # Compensation Simulator (hidden by default)
        self._comp_container = QWidget()
        comp_layout = QHBoxLayout(self._comp_container)
        comp_layout.setContentsMargins(8, 8, 8, 8)
        self._comp_container.setStyleSheet(f"background: {Colors.BG_DARK}; border: 1px solid {Colors.BORDER}; border-radius: 4px;")
        
        self._comp_label = QLabel("Apply Compensation: 0%")
        self._comp_label.setMinimumWidth(200)
        self._comp_label.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-weight: bold;")
        comp_layout.addWidget(self._comp_label)
        
        self._comp_slider = QSlider(Qt.Orientation.Horizontal)
        self._comp_slider.setRange(0, 100)
        self._comp_slider.setValue(0)
        self._comp_slider.valueChanged.connect(self._on_comp_slider_changed)
        comp_layout.addWidget(self._comp_slider)
        
        right.addWidget(self._comp_container)
        self._comp_container.hide()

        # Simulated Bands Warning (hidden by default)
        self._band_warning = QWidget()
        warn_layout = QHBoxLayout(self._band_warning)
        warn_layout.setContentsMargins(8, 8, 8, 8)
        self._band_warning.setStyleSheet(f"background: #d29922; border-radius: 4px;")
        
        warn_lbl = QLabel("⚠ Detector bands are simulated around peak emissions to demonstrate compensation.")
        warn_lbl.setStyleSheet("color: #161b22; font-weight: bold;")
        warn_layout.addWidget(warn_lbl)
        
        close_warn = QPushButton("✕")
        close_warn.setStyleSheet("background: transparent; color: #161b22; border: none; font-weight: bold; font-size: 14px;")
        close_warn.setFixedSize(20, 20)
        close_warn.clicked.connect(lambda: (setattr(self, "_band_warning_dismissed", True), self._band_warning.hide()))
        warn_layout.addWidget(close_warn)
        
        right.addWidget(self._band_warning)
        self._band_warning.hide()

        # Canvas with drag-drop wrapper
        self._drop_frame = DropCanvas(self)
        right.addWidget(self._drop_frame, stretch=1)

        root.addLayout(right, stretch=3)

        # Matplotlib setup
        self._figure = Figure(facecolor="#161b22")
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._drop_frame.canvas_layout.addWidget(self._canvas)
        self._canvas.mpl_connect("button_press_event", self._on_canvas_click)

        self._ax = self._figure.add_subplot(111)
        self._style_axes()
        self._update_plot()

    def _style_axes(self):
        self._ax.set_facecolor("#161b22")
        self._ax.tick_params(colors="#8b949e", labelsize=9)
        for spine in ("bottom", "left"):
            self._ax.spines[spine].set_color("#30363d")
        for spine in ("top", "right"):
            self._ax.spines[spine].set_visible(False)

    # ── Event handlers ────────────────────────────────────────────────────────

    def _set_mode(self, kind: str, checked: bool):
        setattr(self, f"_show_{kind}", checked)
        self._update_plot()

    def _on_student_toggle(self, checked: bool):
        self._student_mode = checked
        self._update_plot()

    def _clear_all(self):
        self._active_fluors.clear()
        self._list_widget.clear()
        self._comp_slider.setValue(0)
        self._comp_value = 0.0
        self._hidden_annotations.clear()
        self._update_plot()

    def _on_comp_slider_changed(self, value: int):
        self._comp_value = value / 100.0
        self._comp_label.setText(f"Apply Compensation: {value}%")
        self._update_plot()

    def _on_canvas_click(self, event):
        """Hide an annotation if it is clicked."""
        if not event.inaxes:
            return
        for ann, key in self._mpl_annotations:
            if ann.contains(event)[0]:
                self._hidden_annotations.add(key)
                self._update_plot()
                break

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_sources()

    def _on_search_changed(self, text: str):
        self._search_results.clear()
        if len(text) < 2:
            self._search_results.hide()
            return
        matches = self._fluor_service.search_dyes(text)
        if matches:
            for m in matches:
                self._search_results.addItem(m)
            self._search_results.show()
        else:
            self._search_results.hide()

    def _on_search_result_clicked(self, item: QListWidgetItem):
        name = item.text()
        self._search_input.clear()
        self._search_results.hide()
        self._add_fluor(name)

    def _on_source_double_clicked(self, item: QListWidgetItem):
        self._add_fluor(item.data(Qt.ItemDataRole.UserRole))

    # ── Data loading ──────────────────────────────────────────────────────────

    def _refresh_sources(self):
        """Repopulate the channel list from the currently selected sample."""
        self._source_list.clear()
        active_id = self._state.current_sample_id
        if not active_id:
            return

        sample = self._state.experiment.samples.get(active_id)
        if not sample or not sample.has_data:
            return

        fcs = sample.fcs_data
        for i, channel in enumerate(fcs.channels):
            if any(s in channel for s in ("Time", "FSC", "SSC")):
                continue

            marker = fcs.markers[i] if i < len(fcs.markers) else ""
            label = f"{marker} ({channel})" if marker else channel

            # Strip detector suffix (-A, -H, -W) without destroying tandem dye names
            query_term = re.sub(r"-[AHW]$", "", channel).strip()

            # Normalise common naming discrepancies vs FPbase
            _MAPPINGS = {
                "APC-Cy7":    "APC/Cy7",
                "PerCP-Cy5-5": "PerCP-Cy5.5",
            }
            for k, v in _MAPPINGS.items():
                if k in query_term:
                    query_term = query_term.replace(k, v)

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, query_term)
            self._source_list.addItem(item)

    def _add_fluor(self, text: str):
        query = text.strip().lower()
        if not query or query in self._active_fluors:
            return

        result = self._fluor_service.get_spectrum(query)
        if not result:
            return

        self._active_fluors[query] = result

        # Build label with QY / EC metadata chip
        label = query.upper()
        chips = []
        if result.get("qy") is not None:
            chips.append(f"QY: {result['qy']:.2f}")
        if result.get("ext_coeff") is not None:
            chips.append(f"EC: {int(result['ext_coeff']):,}")
        if chips:
            label = f"{label}  [{', '.join(chips)}]"

        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, query)
        self._list_widget.addItem(item)
        self._update_plot()

    def _remove_fluor(self, item: QListWidgetItem):
        query = item.data(Qt.ItemDataRole.UserRole)
        self._active_fluors.pop(query, None)
        self._list_widget.takeItem(self._list_widget.row(item))
        self._update_plot()

    # ── Plotting ──────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise(raw: list) -> Tuple[np.ndarray, np.ndarray]:
        """Return (x, y) arrays from a raw [[wl, intensity]] list, normalised 0-1."""
        arr = np.array(raw, dtype=float)
        x, y = arr[:, 0], arr[:, 1]
        peak = np.max(y)
        if peak > 0:
            y = y / peak
        return x, y

    def _update_plot(self):
        self._ax.clear()
        self._style_axes()
        self._ax.set_xlabel("Wavelength (nm)", color="#8b949e", fontsize=10)
        self._ax.set_ylabel("Normalised Intensity", color="#8b949e", fontsize=10)

        if not self._active_fluors:
            self._ax.text(
                0.5, 0.5,
                "Double-click a channel or search FPbase above to add spectra",
                ha="center", va="center",
                transform=self._ax.transAxes,
                color="#484f58", fontsize=11,
            )
            self._ax.set_xlim(300, 800)
            self._ax.set_ylim(0, 1.15)
            self._canvas.draw()
            return

        # 1 nm resolution grid for overlap integrals
        x_grid = np.linspace(300, 800, 1001)
        em_interps: Dict[str, Tuple[np.ndarray, str]] = {}

        for name, data in self._active_fluors.items():
            color = data.get("color", "#aaaaaa")
            base = name.upper()

            # Absorbance — dotted, very transparent
            if self._show_ab and "ab_data" in data:
                x, y = self._normalise(data["ab_data"])
                self._ax.plot(x, y, color=color, lw=1.2, ls=":", alpha=0.45,
                              label=f"{base} AB")
                self._ax.fill_between(x, y, alpha=0.06, color=color)

            # Excitation — dashed, medium
            if self._show_ex and "ex_data" in data:
                x, y = self._normalise(data["ex_data"])
                self._ax.plot(x, y, color=color, lw=1.8, ls="--", alpha=0.70,
                              label=f"{base} EX")
                self._ax.fill_between(x, y, alpha=0.10, color=color)

            # Emission — solid, bright; also stored for overlap calc
            if self._show_em:
                if "em_data" in data:
                    x, y = self._normalise(data["em_data"])
                    self._ax.plot(x, y, color=color, lw=2.2, alpha=0.95,
                                  label=f"{base} EM")
                    self._ax.fill_between(x, y, alpha=0.22, color=color)
                    em_interps[name] = (
                        np.interp(x_grid, x, y, left=0.0, right=0.0),
                        color,
                    )
                else:
                    continue

        # ── Spectral overlap highlighting & Simulator ──────────────────────────
        self._mpl_annotations.clear()
        
        is_sim_mode = self._student_mode and len(em_interps) == 2
        if is_sim_mode:
            self._comp_container.show()
            if not self._band_warning_dismissed:
                self._band_warning.show()
                
            names = list(em_interps.keys())
            # order by peak to determine which is the "spill"
            peak0 = np.argmax(em_interps[names[0]][0])
            peak1 = np.argmax(em_interps[names[1]][0])
            if peak0 > peak1:
                names.reverse()
                
            n1, n2 = names[0], names[1]
            y1, c1 = em_interps[n1]
            y2, c2 = em_interps[n2]
            
            p1_nm = x_grid[np.argmax(y1)]
            p2_nm = x_grid[np.argmax(y2)]
            
            # Detector bands
            self._ax.axvspan(p1_nm - 15, p1_nm + 15, color=c1, alpha=0.15, label=f"{n1.upper()} Detector")
            self._ax.axvspan(p2_nm - 15, p2_nm + 15, color=c2, alpha=0.15, label=f"{n2.upper()} Detector")
            
            # Composite & Compensated curves
            y_comp = y1 + y2
            y_compensated = np.maximum(0, y_comp - self._comp_value * y1)
            
            self._ax.plot(x_grid, y_comp, color="white", lw=1.5, ls=":", label="Uncompensated Signal")
            self._ax.plot(x_grid, y_compensated, color="#d2a8ff", lw=2, label="Compensated Signal")
        else:
            self._comp_container.hide()
            self._band_warning.hide()

        if self._show_em and len(em_interps) >= 2:
            self._draw_overlaps(x_grid, em_interps)

        self._ax.legend(
            facecolor="#1e1e1e", edgecolor="#30363d",
            labelcolor="#c9d1d9", fontsize=8, loc="upper right",
        )
        self._ax.set_xlim(300, 800)
        self._ax.set_ylim(0, 1.18)
        self._figure.tight_layout(pad=0.5)
        self._canvas.draw()

    def _draw_overlaps(
        self,
        x_grid: np.ndarray,
        em_interps: Dict[str, Tuple[np.ndarray, str]],
    ):
        """Shade pairwise EM spectral overlap regions and annotate them."""
        THRESHOLD = 0.05
        names = list(em_interps.keys())

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                n1, n2 = names[i], names[j]
                y1, _ = em_interps[n1]
                y2, _ = em_interps[n2]

                overlap = np.minimum(y1, y2)
                mask = (y1 > THRESHOLD) & (y2 > THRESHOLD)
                if not mask.any():
                    continue

                # Shade
                self._ax.fill_between(
                    x_grid, overlap,
                    where=mask,
                    alpha=0.45, color="white", hatch="///",
                    linewidth=0, label="_nolegend_",
                )

                # Overlap coefficient (Bhattacharyya-style normalised integral)
                denom = max(float(np.trapezoid(y1, x=x_grid)), float(np.trapezoid(y2, x=x_grid)))
                coeff = (float(np.trapezoid(overlap[mask], x=x_grid[mask])) / denom * 100) if denom > 0 else 0

                # Annotation position: peak of overlap curve within mask
                masked_overlap = np.where(mask, overlap, 0)
                peak_idx = int(np.argmax(masked_overlap))
                ann_x = float(x_grid[peak_idx])
                ann_y = float(overlap[peak_idx])

                ann_key = f"{n1}_{n2}"
                if ann_key in self._hidden_annotations:
                    continue

                if self._student_mode:
                    text = (
                        f"⚠ Spectral Overlap\n"
                        f"{n1.upper()} bleeds into {n2.upper()}.\n"
                        f"→ Compensation needed.\n"
                        f"(Click to dismiss)"
                    )
                else:
                    text = (
                        f"Overlap integral: {coeff:.1f}%\n"
                        f"{n1.upper()} → {n2.upper()} spillover\n"
                        f"(Click to dismiss)"
                    )

                # Place the callout to whichever side has more room
                text_x = min(ann_x + 30, 750) if ann_x < 550 else max(ann_x - 160, 310)

                ann = self._ax.annotate(
                    text,
                    xy=(ann_x, ann_y),
                    xytext=(text_x, min(ann_y + 0.28, 1.0)),
                    fontsize=9,
                    color=Colors.FG_PRIMARY,
                    ha="left",
                    arrowprops=dict(arrowstyle="-|>", color=Colors.FG_PRIMARY, lw=1.2),
                    bbox=dict(
                        boxstyle="round,pad=0.4",
                        facecolor=Colors.BG_MEDIUM,
                        edgecolor=Colors.BORDER,
                        alpha=0.95,
                    ),
                )
                self._mpl_annotations.append((ann, ann_key))
