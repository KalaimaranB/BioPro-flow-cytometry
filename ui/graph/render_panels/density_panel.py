"""Density Heatmap settings panel."""

from __future__ import annotations

from biopro.ui.theme import Colors, Fonts
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from analysis.config import COLORMAPS, DensityConfig

from ._utils import PANEL_STYLE, make_float_row, make_int_row, section_header


class DensitySettingsPanel(QWidget):
    """Settings panel for the 2D Density Heatmap renderer."""

    changed = pyqtSignal()

    def __init__(self, config: DensityConfig, parent=None):
        super().__init__(parent)
        self._build_ui(config)

    def _build_ui(self, cfg: DensityConfig):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        self.setStyleSheet(PANEL_STYLE)

        layout.addWidget(section_header("Heatmap Appearance"))
        form = QFormLayout()
        form.setSpacing(10)

        cmap_lbl = QLabel("Color Scheme:")
        cmap_lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")
        self._cmap_combo = QComboBox()
        for label, name in COLORMAPS:
            self._cmap_combo.addItem(label, name)
        for i in range(self._cmap_combo.count()):
            if self._cmap_combo.itemData(i) == cfg.colormap:
                self._cmap_combo.setCurrentIndex(i)
                break
        self._cmap_combo.setStyleSheet(
            f"QComboBox {{ background: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY};"
            f" border: 1px solid {Colors.BORDER}; border-radius: 3px; padding: 2px 6px; }}"
        )
        self._cmap_combo.currentIndexChanged.connect(lambda _: self.changed.emit())
        form.addRow(cmap_lbl, self._cmap_combo)

        self._spin_grid = make_int_row(
            form,
            "Grid Resolution:",
            "Number of bins per axis for the density grid.\n"
            "Higher = more detail; lower = coarser blocks but faster render.\n"
            "256 is a good balance; use 512+ for fine structure.",
            10,
            500,  # raised from 200 → 500
            10,
            cfg.grid_resolution,
        )
        self._spin_grid.valueChanged.connect(lambda _: self.changed.emit())

        self._spin_smoothing = make_float_row(
            form,
            "Smoothing:",
            "Gaussian blur applied after computing the density grid.\n"
            "0 = no smoothing (blocky); 1–2 = natural look; 3+ = very soft.\n"
            "Smoothing hides fine structure but removes noise artefacts.",
            0.0,
            5.0,
            0.1,
            cfg.smoothing,
        )
        self._spin_smoothing.valueChanged.connect(lambda _: self.changed.emit())

        self._spin_opacity = make_float_row(
            form,
            "Opacity:",
            "Overall transparency of the heatmap layer.\n"
            "Lower opacity allows gate overlays to show through.",
            0.1,
            1.0,
            0.05,
            cfg.opacity,
        )
        self._spin_opacity.valueChanged.connect(lambda _: self.changed.emit())

        layout.addLayout(form)
        layout.addStretch()

    def get_config(self) -> DensityConfig:
        return DensityConfig(
            colormap=self._cmap_combo.currentData() or "jet",
            grid_resolution=self._spin_grid.value(),
            smoothing=self._spin_smoothing.value(),
            opacity=self._spin_opacity.value(),
        )

    def set_config(self, config: DensityConfig) -> None:
        for i in range(self._cmap_combo.count()):
            if self._cmap_combo.itemData(i) == config.colormap:
                self._cmap_combo.setCurrentIndex(i)
                break
        self._spin_grid.setValue(config.grid_resolution)
        self._spin_smoothing.setValue(config.smoothing)
        self._spin_opacity.setValue(config.opacity)
