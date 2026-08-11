"""FMO overlay options panel."""

from __future__ import annotations

from biopro.ui.theme import Colors
from biopro_sdk.plugin.components import BioComboBox, BioHelpButton
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QVBoxLayout

from biopro_plugins.flow_cytometry.ui.widgets.checkbox_style import checkbox_qss

from .base import IOptionsPanel


class FmoOptionsPanel(IOptionsPanel):
    """SRP: owns controls for FMO overlay settings only."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._samples: list[tuple[str, str]] = []  # [(display_name, sample_id)]
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # FMO control sample picker
        fmo_row = QHBoxLayout()
        fmo_lbl = QLabel("FMO Control Sample:")
        fmo_help = BioHelpButton()
        fmo_help.setHelpText(
            "Select the FMO (Fluorescence Minus One) control tube for the chosen channel.\n\n"
            "An FMO control is a sample prepared identically to your experimental sample "
            "but with ONE antibody left out. It shows you exactly where background "
            "fluorescence (from spillover of other channels) ends.\n\n"
            "Any events in the real sample that go past this FMO background are genuine "
            "positive cells — this is how you set a scientifically defensible gate.",
            "FMO Control Sample",
        )
        self._fmo_combo = BioComboBox()
        fmo_row.addWidget(fmo_lbl)
        fmo_row.addWidget(fmo_help)
        fmo_row.addStretch()
        layout.addLayout(fmo_row)
        layout.addWidget(self._fmo_combo)

        # Show suggested gate line
        gate_row = QHBoxLayout()
        self._gate_cb = QCheckBox("Show suggested gate line (FMO 99th percentile)")
        self._gate_cb.setChecked(True)
        gate_help = BioHelpButton()
        gate_help.setHelpText(
            "Draws a dashed orange vertical line at the 99th percentile of the FMO control.\n\n"
            "This is a commonly used starting point for gate placement:\n"
            "• 99% of FMO events fall to the LEFT of this line (background).\n"
            "• Events in your real sample to the RIGHT of this line are positive.\n\n"
            "The exact position depends on your panel and should be verified experimentally.",
            "Suggested Gate Line",
        )
        gate_row.addWidget(self._gate_cb)
        gate_row.addWidget(gate_help)
        gate_row.addStretch()
        layout.addLayout(gate_row)

        layout.addStretch()
        self.apply_theme({})

    def populate_samples(self, samples: list[tuple[str, str]]) -> None:
        """Populate the FMO control sample dropdown.

        Args:
            samples: [(display_name, sample_id), ...]
        """
        self._samples = samples
        prev = self._fmo_combo.currentData()
        self._fmo_combo.blockSignals(True)
        self._fmo_combo.clear()
        for name, sid in samples:
            self._fmo_combo.addItem(name, sid)
        idx = self._fmo_combo.findData(prev)
        if idx >= 0:
            self._fmo_combo.setCurrentIndex(idx)
        self._fmo_combo.blockSignals(False)

    def get_config(self) -> dict:
        return {
            "fmo_sample_id": self._fmo_combo.currentData(),
            "show_gate_line": self._gate_cb.isChecked(),
        }

    def apply_theme(self, colors: dict) -> None:
        sec = Colors.FG_SECONDARY
        self._gate_cb.setStyleSheet(checkbox_qss())
        for lbl in self.findChildren(QLabel):
            lbl.setStyleSheet(f"color: {sec}; font-size: 11px;")
