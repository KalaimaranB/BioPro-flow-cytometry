"""Violin plot options panel."""

from __future__ import annotations

from biopro.ui.theme import Colors
from biopro_sdk.plugin.components import BioComboBox, BioHelpButton
from PyQt6.QtWidgets import QCheckBox, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout

from .base import IOptionsPanel


class ViolinOptionsPanel(IOptionsPanel):
    """SRP: owns Qt controls for violin plot settings only."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        form = QFormLayout()
        form.setSpacing(10)

        # Orientation
        orient_row = QHBoxLayout()
        orient_lbl = QLabel("Orientation:")
        orient_help = BioHelpButton()
        orient_help.setHelpText(
            "Vertical: violins grow upward (channels on X axis).\n"
            "Horizontal: violins grow rightward (channels on Y axis).",
            "Orientation",
        )
        self._orient_combo = BioComboBox()
        self._orient_combo.addItem("Vertical", "vertical")
        self._orient_combo.addItem("Horizontal", "horizontal")
        orient_row.addWidget(orient_lbl)
        orient_row.addWidget(orient_help)
        orient_row.addStretch()
        layout.addLayout(orient_row)
        layout.addWidget(self._orient_combo)

        # Show box overlay
        box_row = QHBoxLayout()
        self._show_box_cb = QCheckBox("Show box plot overlay")
        self._show_box_cb.setChecked(True)
        box_help = BioHelpButton()
        box_help.setHelpText(
            "Draws a thin box-and-whisker plot inside each violin showing "
            "the median, IQR and 1.5×IQR whiskers.",
            "Box Overlay",
        )
        box_row.addWidget(self._show_box_cb)
        box_row.addWidget(box_help)
        box_row.addStretch()
        layout.addLayout(box_row)

        # Show individual points
        pts_row = QHBoxLayout()
        self._show_pts_cb = QCheckBox("Show individual data points")
        self._show_pts_cb.setChecked(False)
        pts_help = BioHelpButton()
        pts_help.setHelpText(
            "Overlays individual event values as small dots (capped at 500 per sample). "
            "Useful for small populations where the shape alone is not informative.",
            "Individual Points",
        )
        pts_row.addWidget(self._show_pts_cb)
        pts_row.addWidget(pts_help)
        pts_row.addStretch()
        layout.addLayout(pts_row)

        layout.addStretch()
        self.apply_theme({})

    def get_config(self) -> dict:
        return {
            "orientation": self._orient_combo.currentData() or "vertical",
            "show_box": self._show_box_cb.isChecked(),
            "show_points": self._show_pts_cb.isChecked(),
        }

    def apply_theme(self, colors: dict) -> None:
        fg = Colors.FG_PRIMARY
        sec = Colors.FG_SECONDARY
        for cb in (self._show_box_cb, self._show_pts_cb):
            cb.setStyleSheet(f"color: {fg}; font-size: 11px;")
        for lbl in self.findChildren(QLabel):
            lbl.setStyleSheet(f"color: {sec}; font-size: 11px;")
