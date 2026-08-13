"""Pseudocolor Overlay options panel — axis channel pickers, density-base
toggle, and overlay opacity.

Generalizes the previous BackgatingOptionsPanel (never registered in
PLOT_REGISTRY). Like every other Comparisons plot type, per-population
colour is auto-assigned from the shared palette (`_PALETTE` in
comparisons_viewer.py) rather than a manual per-row colour picker — no other
plot type in this tab exposes one, so adding it here would be a one-off UI
pattern instead of reusing the existing convention.
"""

from __future__ import annotations

from karcytics.ui.theme import Colors
from karcytics_sdk.plugin.components import BioComboBox, BioHelpButton
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QSlider, QVBoxLayout

from karcytics_plugins.flow_cytometry.ui.widgets.checkbox_style import checkbox_qss

from .base import IOptionsPanel


class PseudocolorOverlayOptionsPanel(IOptionsPanel):
    """SRP: owns controls for pseudocolor-overlay axis selection and layer styling."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._channels: list[tuple[str, str]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        x_row = QHBoxLayout()
        x_lbl = QLabel("X Axis Channel:")
        x_help = BioHelpButton()
        x_help.setHelpText(
            "The channel shown on the horizontal axis.\n\n"
            "Typically FSC-A (cell size) or a scatter parameter for a size/complexity view, "
            "or a fluorescence channel to check gate placement in expression space.",
            "X Axis",
        )
        self._x_combo = BioComboBox()
        x_row.addWidget(x_lbl)
        x_row.addWidget(x_help)
        x_row.addStretch()
        layout.addLayout(x_row)
        layout.addWidget(self._x_combo)

        y_row = QHBoxLayout()
        y_lbl = QLabel("Y Axis Channel:")
        y_help = BioHelpButton()
        y_help.setHelpText(
            "The channel shown on the vertical axis.\n\n"
            "Typically SSC-A (cell complexity/granularity) for a classic scatter view, "
            "or a second fluorescence channel for a bivariate expression view.",
            "Y Axis",
        )
        self._y_combo = BioComboBox()
        y_row.addWidget(y_lbl)
        y_row.addWidget(y_help)
        y_row.addStretch()
        layout.addLayout(y_row)
        layout.addWidget(self._y_combo)

        density_row = QHBoxLayout()
        self._density_cb = QCheckBox("Density-shade base layer (pseudocolor)")
        self._density_cb.setChecked(True)
        density_help = BioHelpButton()
        density_help.setHelpText(
            "When checked, the base/context population (usually All Events) is "
            "rendered as a density-coloured pseudocolor cloud, matching the main "
            "gating canvas. When unchecked, it's a flat grey scatter — lighter to "
            "render for very large event counts.",
            "Density Base Layer",
        )
        density_row.addWidget(self._density_cb)
        density_row.addWidget(density_help)
        density_row.addStretch()
        layout.addLayout(density_row)

        opacity_row = QHBoxLayout()
        self._opacity_lbl = QLabel("Overlay Opacity:  70%")
        opacity_help = BioHelpButton()
        opacity_help.setHelpText(
            "Controls how transparent the coloured overlay populations appear. "
            "Lower opacity (30–50%) works well when overlays are dense; "
            "higher opacity (70–100%) is better for rare populations.",
            "Overlay Opacity",
        )
        opacity_row.addWidget(self._opacity_lbl)
        opacity_row.addWidget(opacity_help)
        opacity_row.addStretch()
        layout.addLayout(opacity_row)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(15, 100)
        self._opacity_slider.setValue(70)
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_lbl.setText(f"Overlay Opacity:  {v}%")
        )
        layout.addWidget(self._opacity_slider)

        layout.addStretch()
        self.apply_theme({})

    def populate_channels(self, channels: list[tuple[str, str]]) -> None:
        self._channels = channels
        prev_x = self._x_combo.currentData()
        prev_y = self._y_combo.currentData()
        self._x_combo.blockSignals(True)
        self._y_combo.blockSignals(True)
        self._x_combo.clear()
        self._y_combo.clear()
        for label, key in channels:
            self._x_combo.addItem(label, key)
            self._y_combo.addItem(label, key)
        for combo, prev, default_idx in [
            (self._x_combo, prev_x, 0),
            (self._y_combo, prev_y, 1),
        ]:
            idx = combo.findData(prev) if prev else -1
            combo.setCurrentIndex(idx if idx >= 0 else min(default_idx, combo.count() - 1))
        self._x_combo.blockSignals(False)
        self._y_combo.blockSignals(False)

    def get_config(self) -> dict:
        return {
            "x_channel": self._x_combo.currentData(),
            "y_channel": self._y_combo.currentData(),
            "x_label": self._x_combo.currentText(),
            "y_label": self._y_combo.currentText(),
            "show_density_base": self._density_cb.isChecked(),
            "layer_opacity": self._opacity_slider.value() / 100.0,
        }

    def apply_theme(self, colors: dict) -> None:
        sec = Colors.FG_SECONDARY
        for lbl in self.findChildren(QLabel):
            lbl.setStyleSheet(f"color: {sec}; font-size: 11px;")
        self._opacity_lbl.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-size: 11px;")
        self._density_cb.setStyleSheet(checkbox_qss())
