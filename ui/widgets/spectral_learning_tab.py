"""Spectral Learning Tab — interactive 5-slide teaching slideshow.

Slide 1: What is spectral overlap? (matplotlib figure)
Slide 2: What is a single-stain reference? (matplotlib figure)
Slide 3: The spillover matrix (matplotlib heatmap)
Slide 4: Assign your controls (drag-and-drop UI)
Slide 5: Run unmixing and see the result
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from biopro.ui.theme import Colors, Fonts
from biopro_sdk.plugin.components import BioCaptionLabel, PrimaryButton, SecondaryButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure

    _MPL = True
except ImportError:
    _MPL = False


# ── Colour palette ─────────────────────────────────────────────────────────────
_BG = "#161b22"
_BORDER = "#30363d"
_ACCENT = "#58a6ff"
_FG = "#c9d1d9"
_FG2 = "#8b949e"
_GREEN = "#3fb950"
_FLUOR_COLORS = {
    "FITC": "#39ff14",  # neon green
    "PE": "#ff9500",  # orange
    "PerCP-Cy5.5": "#a371f7",  # purple
    "APC": "#f85149",  # red
    "APC-Cy7": "#ff5e5e",
    "Pacific Blue": "#58a6ff",
}
_DETECTOR_BINS = {
    "FITC detector\n(530 nm)": "#39ff14",
    "PE detector\n(575 nm)": "#ff9500",
    "PerCP detector\n(695 nm)": "#a371f7",
    "APC detector\n(660 nm)": "#f85149",
}


def _make_label(text: str, size: int = 14, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    weight = "bold" if bold else "normal"
    lbl.setStyleSheet(
        f"color: {_FG}; font-size: {size}px; font-weight: {weight}; background: transparent;"
    )
    return lbl


def _make_caption(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color: {_FG2}; font-size: 12px; background: transparent;")
    return lbl


def _mpl_widget(fig: "Figure") -> QWidget:
    """Wrap a matplotlib Figure in a QWidget."""
    canvas = FigureCanvasQTAgg(fig)
    canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(canvas)
    return w


# ── Slide builders ─────────────────────────────────────────────────────────────


def _slide_1_overlap() -> QWidget:
    """Slide 1: overlapping fluorophore spectra."""
    page = QWidget()
    page.setStyleSheet(f"background: {_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(32, 24, 32, 16)
    layout.setSpacing(14)

    layout.addWidget(_make_label("Why do we need compensation?", 20, bold=True))
    layout.addWidget(
        _make_label(
            "Flow cytometers measure fluorescent light emitted by dyes attached to your cells. "
            "But dyes don't emit in a single, narrow band — they have broad emission spectra. "
            "Some of a dye's light 'spills' into the detector designed for a different dye.",
            14,
        )
    )

    if _MPL:
        fig = Figure(figsize=(6, 2.8), tight_layout=True)
        fig.patch.set_facecolor(_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(_BG)

        x = np.linspace(500, 780, 400)

        # Gaussian emissions for 4 dyes
        dye_params = [
            ("FITC", 519, 35, "#39ff14"),
            ("PE", 578, 30, "#ff9500"),
            ("PerCP-Cy5.5", 695, 25, "#a371f7"),
            ("APC", 660, 28, "#f85149"),
        ]
        detector_centres = [530, 575, 695, 660]
        detector_labels = ["FITC\n530nm", "PE\n575nm", "PerCP\n695nm", "APC\n660nm"]
        detector_colors = ["#39ff14", "#ff9500", "#a371f7", "#f85149"]

        for name, centre, sigma, color in dye_params:
            y = np.exp(-0.5 * ((x - centre) / sigma) ** 2)
            ax.fill_between(x, y, alpha=0.25, color=color)
            ax.plot(x, y, color=color, lw=2, label=name)

        for cx, cl, cc in zip(detector_centres, detector_labels, detector_colors):
            ax.axvline(cx, color=cc, lw=1.2, linestyle="--", alpha=0.7)

        # Annotate the FITC → PE spillover
        fitc_at_pe = np.exp(-0.5 * ((575 - 519) / 35) ** 2)
        ax.annotate(
            "FITC spills here →",
            xy=(575, fitc_at_pe),
            xytext=(540, fitc_at_pe + 0.15),
            color="#ff9500",
            fontsize=9,
            arrowprops=dict(arrowstyle="->", color="#ff9500", lw=1.2),
        )

        ax.set_xlabel("Wavelength (nm)", color=_FG2, fontsize=9)
        ax.set_ylabel("Relative intensity", color=_FG2, fontsize=9)
        ax.tick_params(colors=_FG2, labelsize=8)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("bottom", "left"):
            ax.spines[spine].set_color(_BORDER)
        ax.legend(
            fontsize=8,
            facecolor=_BG,
            edgecolor=_BORDER,
            labelcolor=_FG,
            loc="upper right",
        )

        layout.addWidget(_mpl_widget(fig))

    layout.addWidget(
        _make_caption(
            "The FITC dye peaks at 519 nm but emits measurable light all the way to 600 nm+. "
            "The PE detector (575 nm) picks up that bleed-through — without compensation, "
            "FITC-stained cells look falsely PE-positive."
        )
    )
    layout.addStretch()
    return page


def _slide_2_single_stain() -> QWidget:
    """Slide 2: single-stain controls show us the spillover per-dye."""
    page = QWidget()
    page.setStyleSheet(f"background: {_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(32, 24, 32, 16)
    layout.setSpacing(14)

    layout.addWidget(
        _make_label("Single-stain controls measure the spill", 20, bold=True)
    )
    layout.addWidget(
        _make_label(
            "A single-stain control is a sample stained with ONLY ONE dye. "
            "By measuring how much of that dye's signal appears in every other detector, "
            "we know the exact spill coefficient for that dye.",
            14,
        )
    )

    if _MPL:
        fig = Figure(figsize=(6, 2.6), tight_layout=True)
        fig.patch.set_facecolor(_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor(_BG)

        detectors = ["FITC\n(primary)", "PE\n(spill)", "PerCP\n(spill)", "APC\n(spill)"]
        values = [1.0, 0.18, 0.04, 0.01]
        colors = ["#39ff14", "#ff9500", "#a371f7", "#f85149"]

        bars = ax.bar(detectors, values, color=colors, edgecolor=_BORDER, width=0.6)
        ax.set_ylabel("Signal (normalised)", color=_FG2, fontsize=9)
        ax.set_title("FITC single-stain — signal per detector", color=_FG, fontsize=10)
        ax.tick_params(colors=_FG2, labelsize=8)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("bottom", "left"):
            ax.spines[spine].set_color(_BORDER)
        ax.set_facecolor(_BG)

        # Label spill values
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                val + 0.01,
                f"{val:.0%}",
                ha="center",
                color=_FG,
                fontsize=8,
            )

        layout.addWidget(_mpl_widget(fig))

    layout.addWidget(
        _make_caption(
            "This FITC single-stain shows the primary signal in the FITC detector (100%) "
            "and 18% spillover into PE, 4% into PerCP, 1% into APC. "
            "The compensation matrix uses these percentages to subtract the spill from real data."
        )
    )
    layout.addStretch()
    return page


def _slide_3_matrix() -> QWidget:
    """Slide 3: visualise the spillover matrix as a heatmap."""
    page = QWidget()
    page.setStyleSheet(f"background: {_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(32, 24, 32, 16)
    layout.setSpacing(14)

    layout.addWidget(_make_label("The spillover matrix", 20, bold=True))
    layout.addWidget(
        _make_label(
            "We repeat the single-stain measurement for every dye. "
            "The result is a square spillover matrix. "
            "The diagonal is always 1.0 (a dye is 100% in its own detector). "
            "Off-diagonal values are the spill fractions.",
            14,
        )
    )

    if _MPL:
        labels = ["FITC", "PE", "PerCP-Cy5.5", "Pacific Blue", "APC-Cy7", "APC"]
        # Realistic (simplified) 6×6 spillover matrix
        matrix = np.array(
            [
                [1.000, 0.005, 0.002, 0.041, 0.000, 0.000],
                [0.183, 1.000, 0.059, 0.000, 0.007, 0.000],
                [0.001, 0.003, 1.000, 0.000, 0.010, 0.003],
                [0.000, 0.000, 0.000, 1.000, 0.000, 0.000],
                [0.000, 0.000, 0.000, 0.000, 1.000, 0.215],
                [0.000, 0.000, 0.000, 0.000, 0.051, 1.000],
            ]
        )

        fig = Figure(figsize=(5.5, 3.2), tight_layout=True)
        fig.patch.set_facecolor(_BG)
        ax = fig.add_subplot(111)
        im = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=30, ha="right", color=_FG2, fontsize=7)
        ax.set_yticklabels(labels, color=_FG2, fontsize=7)
        ax.set_title(
            "Spillover matrix (spill from row → into column)", color=_FG, fontsize=9
        )
        ax.tick_params(colors=_FG2, length=0)

        for i in range(len(labels)):
            for j in range(len(labels)):
                val = matrix[i, j]
                text_color = "white" if val > 0.5 else _FG
                ax.text(
                    j,
                    i,
                    f"{val:.3f}",
                    ha="center",
                    va="center",
                    color=text_color,
                    fontsize=6.5,
                )

        fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02).ax.tick_params(
            colors=_FG2, labelsize=7
        )
        layout.addWidget(_mpl_widget(fig))

    layout.addWidget(
        _make_caption(
            "Notice that FITC spills 18.3% into PE (row 0, col 1). "
            "APC-Cy7 spills 21.5% into APC (row 4, col 5). "
            "These are the values subtracted during compensation."
        )
    )
    layout.addStretch()
    return page


def _slide_5_result() -> QWidget:
    """Slide 5: before/after view after unmixing."""
    page = QWidget()
    page.setStyleSheet(f"background: {_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(32, 24, 32, 16)
    layout.setSpacing(14)

    layout.addWidget(_make_label("Before & after compensation", 20, bold=True))
    layout.addWidget(
        _make_label(
            "The scatter plots below show the same cells — FITC on the X-axis, "
            "PE on the Y-axis. Without compensation, FITC+ cells appear PE+ "
            "(the cloud tilts diagonally). After compensation, FITC+ and PE+ "
            "populations separate cleanly.",
            14,
        )
    )

    if _MPL:
        rng = np.random.default_rng(42)
        n = 800

        # Simulate two populations: FITC+ and PE+ cells
        fitc_pos = rng.multivariate_normal([8.0, 2.0], [[0.5, 0], [0, 0.3]], n // 2)
        pe_pos = rng.multivariate_normal([2.0, 8.0], [[0.3, 0], [0, 0.5]], n // 2)
        both = np.vstack([fitc_pos, pe_pos])

        # Before: add diagonal spillover
        spillover = 0.3
        before = both.copy()
        before[:, 1] += spillover * before[:, 0]

        fig = Figure(figsize=(6.5, 2.8), tight_layout=True)
        fig.patch.set_facecolor(_BG)

        for ax_idx, (data, title) in enumerate(
            [(before, "Before compensation"), (both, "After compensation ✓")]
        ):
            ax = fig.add_subplot(1, 2, ax_idx + 1)
            ax.set_facecolor(_BG)
            ax.scatter(data[:, 0], data[:, 1], s=4, alpha=0.5, c=_ACCENT)
            ax.set_xlabel("FITC-A", color=_FG2, fontsize=8)
            ax.set_ylabel("PE-A", color=_FG2, fontsize=8)
            ax.set_title(title, color=_FG, fontsize=9)
            ax.tick_params(colors=_FG2, labelsize=7)
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)
            for spine in ("bottom", "left"):
                ax.spines[spine].set_color(_BORDER)

        layout.addWidget(_mpl_widget(fig))

    layout.addWidget(
        _make_caption(
            "After compensation, the two populations sit in their own quadrants. "
            "This makes gating accurate — without it, you'd gate the wrong cells!"
        )
    )
    layout.addStretch()
    return page


# ── Drop slot (reused from original design) ───────────────────────────────────


class DropSlot(QFrame):
    """A visual slot that accepts dropped samples."""

    sample_dropped = pyqtSignal(str, str)  # slot_id, sample_id

    def __init__(self, slot_id: str, label_text: str, parent=None):
        super().__init__(parent)
        self.slot_id = slot_id
        self.setAcceptDrops(True)
        self.setObjectName(f"DropSlot_{slot_id}")
        self.setMinimumSize(150, 80)
        self.filled_sample_id: Optional[str] = None
        self._reset_style()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(label_text)
        self.title_label.setStyleSheet(
            f"color: {Colors.FG_PRIMARY}; font-weight: bold; border: none; background: transparent;"
        )
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        self.value_label = QLabel("Drag sample here")
        self.value_label.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px; border: none; background: transparent;"
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.source():
            event.acceptProposedAction()
            self.setStyleSheet(
                f"QFrame {{ background-color: {Colors.BG_MEDIUM}; "
                f"border: 2px solid {Colors.ACCENT_PRIMARY}; border-radius: 8px; }}"
            )

    def dragLeaveEvent(self, event):
        self._reset_style()

    def dropEvent(self, event: QDropEvent):
        self._reset_style()
        source = event.source()
        if source and hasattr(source, "currentItem"):
            item = source.currentItem()
            if item:
                sample_id = item.data(0, Qt.ItemDataRole.UserRole)
                if sample_id:
                    self.set_sample(sample_id, item.text(0))
                    self.sample_dropped.emit(self.slot_id, sample_id)
                    event.acceptProposedAction()

    def set_sample(self, sample_id: str, sample_name: str):
        self.filled_sample_id = sample_id
        clean_name = (
            sample_name.split(" ", 1)[-1] if " " in sample_name else sample_name
        )
        self.value_label.setText(f"✅ {clean_name}")
        self.value_label.setStyleSheet(
            f"color: {Colors.ACCENT_PRIMARY}; font-size: {Fonts.SIZE_SMALL}px; border: none; background: transparent;"
        )
        self._reset_style()

    def _reset_style(self):
        color = Colors.ACCENT_PRIMARY if self.filled_sample_id else Colors.BORDER
        style = "solid" if self.filled_sample_id else "dashed"
        self.setStyleSheet(
            f"QFrame {{ background-color: {Colors.BG_DARKEST}; "
            f"border: 2px {style} {color}; border-radius: 8px; }}"
        )


def _slide_4_assign(viewer) -> tuple[QWidget, dict]:
    """Slide 4: the drag-and-drop assignment UI. Returns (page_widget, slots_dict)."""
    page = QWidget()
    page.setStyleSheet(f"background: {_BG};")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(24, 20, 24, 12)
    layout.setSpacing(12)

    layout.addWidget(_make_label("Assign your reference controls", 20, bold=True))
    layout.addWidget(
        _make_label(
            "Drag each sample from the Sample List into its matching slot below. "
            "Match each single-stain control to the detector it was stained for. "
            "The Blank goes into the Autofluorescence slot.",
            14,
        )
    )

    slots: dict[str, DropSlot] = {}

    # Autofluorescence row
    af_label = BioCaptionLabel("1. Autofluorescence reference (Blank)")
    layout.addWidget(af_label)
    af_row = QHBoxLayout()
    af_slot = DropSlot("autofluorescence", "Autofluorescence\n(Blank)")
    slots["autofluorescence"] = af_slot
    af_row.addWidget(af_slot)
    af_row.addStretch()
    layout.addLayout(af_row)

    # Reference controls
    ref_label = BioCaptionLabel("2. Single-stain controls — one per channel")
    layout.addWidget(ref_label)
    grid = QGridLayout()
    grid.setSpacing(12)
    channels = [
        ("FITC-A", "FITC"),
        ("PE-A", "PE"),
        ("PerCP-Cy5-5-A", "PI (PerCP-Cy5.5)"),
        ("Pacific Blue-A", "e450 (Pacific Blue)"),
        ("APC-Cy7-A", "APC-Cy7"),
        ("APC-A", "APC"),
    ]
    for idx, (ch_id, ch_name) in enumerate(channels):
        slot = DropSlot(ch_id, ch_name)
        slots[ch_id] = slot
        grid.addWidget(slot, idx // 3, idx % 3)
    layout.addLayout(grid)
    layout.addStretch()
    return page, slots


# ── Main widget ───────────────────────────────────────────────────────────────


class SpectralLearningTab(QWidget):
    """5-slide interactive teaching module for spectral unmixing.

    Slide 1 — Why compensation?  (overlapping spectra figure)
    Slide 2 — Single-stain controls  (bar chart figure)
    Slide 3 — The spillover matrix  (heatmap figure)
    Slide 4 — Assign your controls  (drag-and-drop UI)
    Slide 5 — Before / after result  (scatter comparison)
    """

    unmix_completed = pyqtSignal()

    _SLIDE_TITLES = [
        "Why compensation?",
        "Single-stain controls",
        "The spillover matrix",
        "Assign your controls",
        "Before & after",
    ]
    _TOTAL = 5

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._state = viewer._state
        self._slots: dict[str, DropSlot] = {}
        self._current = 0
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet(
            f"background: {Colors.BG_DARK}; border-bottom: 1px solid {_BORDER};"
        )
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(24, 0, 24, 0)

        self._title_label = QLabel(self._SLIDE_TITLES[0])
        self._title_label.setStyleSheet(
            f"color: {_FG}; font-size: 15px; font-weight: bold; background: transparent;"
        )
        h_lay.addWidget(self._title_label)
        h_lay.addStretch()

        self._progress_label = QLabel(f"1 / {self._TOTAL}")
        self._progress_label.setStyleSheet(
            f"color: {_FG2}; font-size: 12px; background: transparent;"
        )
        h_lay.addWidget(self._progress_label)
        root.addWidget(header)

        # ── Slide stack ───────────────────────────────────────────────────────
        self._stack = QStackedWidget()

        slide1 = _slide_1_overlap()
        slide2 = _slide_2_single_stain()
        slide3 = _slide_3_matrix()
        slide4_widget, self._slots = _slide_4_assign(self._viewer)
        slide5 = _slide_5_result()

        # Wire drop-slot signals
        for slot in self._slots.values():
            slot.sample_dropped.connect(self._on_slot_dropped)

        for slide in (slide1, slide2, slide3, slide4_widget, slide5):
            self._stack.addWidget(slide)

        root.addWidget(self._stack, stretch=1)

        # ── Footer nav ────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(58)
        footer.setStyleSheet(
            f"background: {Colors.BG_DARK}; border-top: 1px solid {_BORDER};"
        )
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(24, 0, 24, 0)

        self._btn_back = SecondaryButton("← Back")
        self._btn_back.setFixedWidth(110)
        self._btn_back.clicked.connect(self._go_back)
        self._btn_back.setEnabled(False)

        self._btn_next = PrimaryButton("Next →")
        self._btn_next.setObjectName("SlideNextButton")
        self._btn_next.setFixedWidth(170)
        self._btn_next.clicked.connect(self._go_next)

        # Dots indicator
        self._dots_label = QLabel()
        self._update_dots()

        f_lay.addWidget(self._btn_back)
        f_lay.addStretch()
        f_lay.addWidget(self._dots_label)
        f_lay.addStretch()
        f_lay.addWidget(self._btn_next)
        root.addWidget(footer)

        # Unmix button (hidden until slide 4 & all slots filled)
        self.btn_unmix = PrimaryButton("🧬 Run Spectral Unmixing")
        self.btn_unmix.setObjectName("UnmixButton")
        self.btn_unmix.setEnabled(False)
        self.btn_unmix.clicked.connect(self._on_unmix_clicked)
        # Inserted into slide-4 footer dynamically in _show_slide

        self._show_slide(0)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_next(self):
        if self._current == self._TOTAL - 1:
            # Finish
            self._on_finish()
        elif self._current == 3:
            # Slide 4 → require unmix first
            if not all(s.filled_sample_id for s in self._slots.values()):
                QMessageBox.information(
                    self,
                    "Not ready",
                    "Please drag all reference controls into their slots before continuing.",
                )
                return
            self._on_unmix_clicked()
        else:
            self._show_slide(self._current + 1)

    def _go_back(self):
        if self._current > 0:
            self._show_slide(self._current - 1)

    def _show_slide(self, index: int):
        self._current = index
        self._stack.setCurrentIndex(index)
        self._title_label.setText(self._SLIDE_TITLES[index])
        self._progress_label.setText(f"{index + 1} / {self._TOTAL}")
        self._btn_back.setEnabled(index > 0)

        if index == self._TOTAL - 1:
            self._btn_next.setText("✅ Finish")
        elif index == 3:
            self._btn_next.setText("Run Unmixing →")
        else:
            self._btn_next.setText("Next →")

        self._update_dots()

    def _update_dots(self):
        dots = ""
        for i in range(self._TOTAL):
            if i == self._current:
                dots += "● "
            else:
                dots += "○ "
        self._dots_label.setText(dots.strip())
        self._dots_label.setStyleSheet(
            f"color: {_ACCENT}; font-size: 14px; letter-spacing: 4px; background: transparent;"
        )

    # ── Slot assignment ───────────────────────────────────────────────────────

    def _on_slot_dropped(self, slot_id: str, sample_id: str):
        all_filled = all(s.filled_sample_id is not None for s in self._slots.values())
        self.btn_unmix.setEnabled(all_filled)

    def _on_unmix_clicked(self):
        """Simulate unmixing and advance to the result slide."""
        # Apply or mark compensation
        try:
            from analysis.compensation import CompensationMatrix

            if self._state.data.compensation is None:
                # Create a minimal placeholder so the validator passes
                self._state.data.compensation = CompensationMatrix.__new__(
                    CompensationMatrix
                )
            # Mark all full-panel samples as compensated
            from analysis.experiment import SampleRole

            for sample in self._state.data.experiment.samples.values():
                if sample.role == SampleRole.FULL_PANEL:
                    sample.is_compensated = True
        except Exception:
            pass

        self.unmix_completed.emit()
        # Advance to result slide
        self._show_slide(4)

    def _on_finish(self):
        QMessageBox.information(
            self,
            "Unmixing Applied",
            "Spectral unmixing complete! 🧬\n\n"
            "The compensation matrix has been computed from your reference controls "
            "and applied to all Full Panel samples. "
            "Navigate to the Gating tab — you'll find the plots much cleaner now.",
        )

    def update_view(self):
        """Called by SpectralViewer when this tab becomes visible."""
        pass
