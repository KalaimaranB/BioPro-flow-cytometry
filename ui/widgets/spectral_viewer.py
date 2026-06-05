"""Spectral Viewer Panel — Overlay fluorophore AB / EX / EM spectra from FPbase.

Features:
  - Global AB / EX / EM toggle buttons
  - Student / Pro annotation mode for spectral-overlap callouts
  - Live FPbase search autocomplete
  - QY / EC metadata chips on active spectra
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import numpy as np
from biopro.ui.theme import Colors, Fonts
from biopro_sdk.plugin.components import (
    BioCaptionLabel,
    BioLineEdit,
    BioListWidget,
    BioToggleButton,
    BioHelpButton,
    SecondaryButton,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
    QTabWidget,
)

from .spectral_learning_tab import SpectralLearningTab

if TYPE_CHECKING:
    from analysis.biology_services import FluorophoreService
    from analysis.state import FlowState


# Button style helpers removed (using SDK)


# ── Drop canvas ───────────────────────────────────────────────────────────────


class DropCanvas(QFrame):
    """Transparent frame wrapping the matplotlib canvas; accepts drag-drops from the channel list."""

    def __init__(self, viewer: SpectralViewer, parent: QWidget | None = None):
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
                self._viewer._add_fluor(item.data(Qt.ItemDataRole.UserRole), display_label=item.text())
            event.acceptProposedAction()


# ── Main widget ───────────────────────────────────────────────────────────────


class SpectralViewer(QWidget):
    """Central workspace panel: plots AB / EX / EM spectra with overlap annotation."""

    def __init__(
        self,
        state: FlowState,
        fluor_service: FluorophoreService,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._state = state
        self._fluor_service = fluor_service
        self._active_fluors: dict[str, dict[str, Any]] = {}
        self._color_index = 0

        # Global display toggles (defaults: show EX + EM)
        self._show_ab = False
        self._show_ex = True
        self._show_em = True
        self._hidden_annotations = set()
        self._mpl_annotations = []

        self._setup_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _toggle_btn(self, label: str, active: bool, help_text: str | None = None) -> BioToggleButton:
        btn = BioToggleButton(label)
        btn.setChecked(active)
        btn.setMinimumWidth(135)
        
        if help_text:
            lay = QHBoxLayout(btn)
            lay.setContentsMargins(0, 0, 10, 0)
            
            help_btn = BioHelpButton(btn)
            help_btn.setHelpText(help_text)
            
            # The SDK now isolates child styles natively via #BioToggleButton and #BioHelpButton selectors.
            # We simply inject our left-alignment overrides directly into the BioToggleButton via its new extension hook.
            btn.custom_css_overrides = "text-align: left; padding-left: 12px; padding-right: 32px;"
            # Force a style refresh so the override takes effect immediately
            btn._apply_theme_styles()
            
            lay.addWidget(help_btn, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
        return btn

    def _section_label(self, text: str) -> BioCaptionLabel:
        lbl = BioCaptionLabel(text)
        lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-weight: bold; font-size: 11px;")
        return lbl

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            "QTabWidget::pane { border: none; border-top: 1px solid #30363d; } "
            "QTabBar::tab { padding: 8px 16px; font-size: 13px; font-weight: bold; background: transparent; color: #8b949e; border: none; border-bottom: 2px solid transparent; }"
            "QTabBar::tab:selected { color: #c9d1d9; border-bottom: 2px solid #58a6ff; }"
        )

        analysis_tab = QWidget()
        root = QHBoxLayout(analysis_tab)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # ── Left panel ────────────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(10)

        # FPbase search
        left.addWidget(self._section_label("Search FPbase:"))

        self._search_input = BioLineEdit()
        self._search_input.setPlaceholderText("e.g. APC/Cy7, Alexa Fluor 488…")
        left.addWidget(self._search_input)

        self._search_results = BioListWidget()
        self._search_results.setMaximumHeight(120)
        self._search_results.hide()
        left.addWidget(self._search_results)

        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_results.itemClicked.connect(self._on_search_result_clicked)

        # Channel list
        left.addWidget(self._section_label("Available Channels:"))
        self._source_list = BioListWidget()
        self._source_list.setDragEnabled(True)
        self._source_list.itemDoubleClicked.connect(self._on_source_double_clicked)
        left.addWidget(self._source_list, stretch=1)

        hint = QLabel("↕ Double-click or drag onto plot")
        hint.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")
        left.addWidget(hint)

        # Active spectra list
        left.addWidget(self._section_label("Active Spectra:"))
        self._list_widget = BioListWidget()
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

        self._btn_ab = self._toggle_btn(
            "AB  Absorbance", 
            active=False, 
            help_text="Absorbance (AB): The physical wavelengths of light that the fluorophore absorbs. In flow cytometry, this is mostly a chemistry detail."
        )
        self._btn_ab.setToolTip("Show Absorbance")
        
        self._btn_ex = self._toggle_btn(
            "EX  Excitation", 
            active=True, 
            help_text="Excitation (EX): The wavelengths of light that actually cause the fluorophore to 'light up'. You use the EX curve to figure out which laser on your flow cytometer to use (e.g., the 488 nm Blue laser)."
        )
        self._btn_ex.setToolTip("Show Excitation")
        
        self._btn_em = self._toggle_btn(
            "EM  Emission", 
            active=True, 
            help_text="Emission (EM): The wavelengths of light the fluorophore shoots back out. You use the EM curve to figure out which detector to use to capture the signal."
        )
        self._btn_em.setToolTip("Show Emission")

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

        toolbar.addStretch()

        clear_btn = SecondaryButton("✕ Clear All")
        clear_btn.setMinimumHeight(32)
        clear_btn.clicked.connect(self._clear_all)
        toolbar.addWidget(clear_btn)

        right.addLayout(toolbar)

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

        self._tabs.addTab(analysis_tab, "Spectral Analysis")

        self._learning_tab = SpectralLearningTab(viewer=self)
        self._tabs.addTab(self._learning_tab, "Learning: What is Compensation?")

        self._tabs.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self._tabs)

    def _on_tab_changed(self, index: int):
        if self._tabs.widget(index) is self._learning_tab:
            self._learning_tab.update_view()

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

    def _clear_all(self):
        self._active_fluors.clear()
        self._list_widget.clear()
        self._hidden_annotations.clear()
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
        self._add_fluor(name, display_label=name)

    def _on_source_double_clicked(self, item: QListWidgetItem):
        self._add_fluor(item.data(Qt.ItemDataRole.UserRole), display_label=item.text())

    # ── Data loading ──────────────────────────────────────────────────────────

    def _refresh_sources(self):
        """Repopulate the channel list from the currently selected sample."""
        self._source_list.clear()
        active_id = self._state.view.current_sample_id
        if not active_id:
            return

        sample = self._state.data.experiment.samples.get(active_id)
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
                "APC-Cy7": "APC/Cy7",
                "PerCP-Cy5-5": "PerCP-Cy5.5",
            }
            for k, v in _MAPPINGS.items():
                if k in query_term:
                    query_term = query_term.replace(k, v)

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, query_term)
            self._source_list.addItem(item)

    def _add_fluor(self, text: str, display_label: str | None = None):
        query = text.strip().lower()
        if not query or query in self._active_fluors:
            return

        result = self._fluor_service.get_spectrum(query)
        if not result:
            return

        # Override with a distinct color from tab20 to avoid repeating API colors
        import matplotlib.colors as mcolors
        import matplotlib.pyplot as plt
        cmap = plt.get_cmap("tab20")
        result["color"] = mcolors.to_hex(cmap(self._color_index % 20))
        self._color_index += 1
        
        result["display_label"] = display_label or query.upper()

        self._active_fluors[query] = result

        # Build label with QY / EC metadata chip
        label = result["display_label"]
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
    def _normalise(raw: list) -> tuple[np.ndarray, np.ndarray]:
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
                0.5,
                0.5,
                "Double-click a channel or search FPbase above to add spectra",
                ha="center",
                va="center",
                transform=self._ax.transAxes,
                color="#484f58",
                fontsize=11,
            )
            self._ax.set_xlim(300, 800)
            self._ax.set_ylim(0, 1.15)
            self._canvas.draw()
            return

        # 1 nm resolution grid for overlap integrals
        x_grid = np.linspace(300, 800, 1001)
        em_interps: dict[str, tuple[np.ndarray, str]] = {}

        for name, data in self._active_fluors.items():
            color = data.get("color", "#aaaaaa")
            base = data.get("display_label", name.upper())

            # Absorbance — dotted, very transparent
            if self._show_ab and "ab_data" in data:
                x, y = self._normalise(data["ab_data"])
                self._ax.plot(x, y, color=color, lw=1.2, ls=":", alpha=0.45, label=f"{base} AB")
                self._ax.fill_between(x, y, alpha=0.06, color=color)

            # Excitation — dashed, medium
            if self._show_ex and "ex_data" in data:
                x, y = self._normalise(data["ex_data"])
                self._ax.plot(x, y, color=color, lw=1.8, ls="--", alpha=0.70, label=f"{base} EX")
                self._ax.fill_between(x, y, alpha=0.10, color=color)

            # Emission — solid, bright; also stored for overlap calc
            if self._show_em:
                if "em_data" in data:
                    x, y = self._normalise(data["em_data"])
                    self._ax.plot(x, y, color=color, lw=2.2, alpha=0.95, label=f"{base} EM")
                    self._ax.fill_between(x, y, alpha=0.22, color=color)
                    em_interps[name] = (
                        np.interp(x_grid, x, y, left=0.0, right=0.0),
                        color,
                    )
                else:
                    continue

        # ── Spectral overlap highlighting ──────────────────────────────────────
        self._mpl_annotations.clear()

        if self._show_em and len(em_interps) >= 2:
            self._draw_overlaps(x_grid, em_interps)

        self._ax.legend(
            facecolor="#1e1e1e",
            edgecolor="#30363d",
            labelcolor="#c9d1d9",
            fontsize=8,
            loc="upper right",
        )
        self._ax.set_xlim(300, 800)
        self._ax.set_ylim(0, 1.18)
        self._figure.tight_layout(pad=0.5)
        self._canvas.draw()

    def _draw_overlaps(
        self,
        x_grid: np.ndarray,
        em_interps: dict[str, tuple[np.ndarray, str]],
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
                    x_grid,
                    overlap,
                    where=mask,
                    alpha=0.45,
                    color="white",
                    hatch="///",
                    linewidth=0,
                    label="_nolegend_",
                )

                # Overlap coefficient (Bhattacharyya-style normalised integral)
                denom = max(float(np.trapz(y1, x=x_grid)), float(np.trapz(y2, x=x_grid)))
                coeff = (float(np.trapz(overlap[mask], x=x_grid[mask])) / denom * 100) if denom > 0 else 0

                # Annotation position: peak of overlap curve within mask
                masked_overlap = np.where(mask, overlap, 0)
                peak_idx = int(np.argmax(masked_overlap))
                ann_x = float(x_grid[peak_idx])
                ann_y = float(overlap[peak_idx])

                ann_key = f"{n1}_{n2}"
                if ann_key in self._hidden_annotations:
                    continue

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
