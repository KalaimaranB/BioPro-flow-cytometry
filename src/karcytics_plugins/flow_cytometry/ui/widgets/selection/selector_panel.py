"""Composed sample + population selector: the single integration point used
by StatisticsExplorer, ComparisonsViewer, and PopulationAnalysisViewer in
place of each tab building its own sample checklist and population tree.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .population_tree import PopulationTreeWidget
from .sample_checklist import SampleChecklistWidget

if TYPE_CHECKING:
    from karcytics_plugins.flow_cytometry.analysis.experiment import Sample


def _get_theme_tokens():
    from karcytics_sdk.plugin.theme_fallback import Colors

    return Colors


def _section_label(text: str) -> QLabel:
    Colors = _get_theme_tokens()
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {Colors.FG_SECONDARY}; font-weight: bold; font-size: 11px;"
        " text-transform: uppercase; letter-spacing: 0.5px;"
    )
    return lbl


class SampleAndPopulationSelector(QWidget):
    """Samples checklist + grouped population tree, composed as one widget.

    Signals:
        selectionChanged: emitted whenever checked samples or populations
            change — the one signal callers need to re-run their compute/plot.
    """

    selectionChanged = pyqtSignal()

    def __init__(
        self,
        *,
        multi_population: bool = True,
        sample_help_text: str = "Select one or more samples to include.",
        population_help_text: str = "Select gated populations to include.",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._samples: dict[str, Sample] = {}

        from karcytics_sdk.plugin.components import BioHelpButton

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        smp_hdr = QHBoxLayout()
        smp_hdr.addWidget(_section_label("Samples"))
        smp_help = BioHelpButton()
        smp_help.setHelpText(sample_help_text, "Samples")
        smp_hdr.addWidget(smp_help)
        smp_hdr.addStretch()
        layout.addLayout(smp_hdr)

        self.sample_list = SampleChecklistWidget()
        layout.addWidget(self.sample_list)

        pop_hdr = QHBoxLayout()
        pop_hdr.addWidget(_section_label("Populations"))
        pop_help = BioHelpButton()
        pop_help.setHelpText(population_help_text, "Populations")
        pop_hdr.addWidget(pop_help)
        pop_hdr.addStretch()
        layout.addLayout(pop_hdr)

        self.population_tree = PopulationTreeWidget()
        self.population_tree.set_multi_select(multi_population)
        layout.addWidget(self.population_tree)

        self.sample_list.selectionChanged.connect(self._on_samples_changed)
        self.population_tree.selectionChanged.connect(self.selectionChanged.emit)

    def refresh(self, samples: dict[str, Sample]) -> None:
        """Repopulate from {sample_id: Sample}, preserving prior checks."""
        self._samples = samples
        self.sample_list.refresh(samples)  # triggers _on_samples_changed via its signal

    def set_multi_population(self, enabled: bool) -> None:
        self.population_tree.set_multi_select(enabled)

    def set_sample_mode(self, single: bool) -> None:
        """Force single-select (radio) sample checking for plot types that
        are only defined for one sample (e.g. FMO, Pseudocolor Overlay).
        """
        self.sample_list.set_single_select(single)

    def get_checked_sample_ids(self) -> list[str]:
        return self.sample_list.get_checked_sample_ids()

    def get_checked_populations(self) -> list[tuple[str, str | None, str]]:
        return self.population_tree.get_checked_populations()

    def _on_samples_changed(self) -> None:
        self.population_tree.refresh(self._samples, self.sample_list.get_checked_sample_ids())
        self.selectionChanged.emit()
