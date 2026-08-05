"""ComparisonsViewer — full-screen cross-sample comparison plot workspace.

Follows the same architecture as StatisticsExplorer and PopulationAnalysisViewer:
  - Fixed-width scrollable left sidebar for controls
  - Right workspace with toolbar, progress bar, and matplotlib canvas

SOLID design:
  SRP: this widget assembles Qt layout and wires signals only.
       Rendering is delegated to IPlotRenderer subclasses.
       Data extraction is delegated to ComparisonsDataExtractor.
  OCP: new plot types are added to PLOT_REGISTRY — zero changes here.
  LSP: any IPlotRenderer / IOptionsPanel subclass can be swapped in.
  ISP: depends on narrow IPlotRenderer.render() and IOptionsPanel.get_config().
  DIP: depends on abstractions (IPlotRenderer, FlowState), not concrete renderers.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

try:
    from biopro.ui.theme import Colors, Fonts, theme_manager  # noqa: F401
except ImportError:
    from biopro_sdk.plugin.theme_fallback import Colors, theme_manager

from biopro_sdk.plugin.components import (
    BioComboBox,
    BioHelpButton,
    BioListWidget,
    PrimaryButton,
    SecondaryButton,
)
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from biopro_plugins.flow_cytometry.analysis.state import FlowState
from biopro_plugins.flow_cytometry.analysis.statistics import StatType
from biopro_plugins.flow_cytometry.ui.graph._mpl_compat import FigureCanvasQTAgg

from .comparisons.data_extractor import ComparisonsDataExtractor
from .comparisons.registry import (
    PLOT_HELP,
    PLOT_REGISTRY,
    PLOTS_MULTI_CHANNEL,
    PLOTS_MULTI_POPULATION,
    PLOTS_WITHOUT_CHANNEL_LIST,
)
from .comparisons.worker import ComparisonsWorker

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# BioPro gate palette — auto-assigned per sample/population
_PALETTE = [
    "#00bcd4",
    "#ef5350",
    "#66bb6a",
    "#ffa726",
    "#ab47bc",
    "#26c6da",
    "#ff7043",
    "#9ccc65",
    "#29b6f6",
    "#ec407a",
    "#d4e157",
    "#8d6e63",
]


class ComparisonsViewer(QWidget):
    """Cross-sample comparison plot workspace.

    Provides 5 plot types for comparing samples and populations:
    Violin, Channel Heatmap, Back-gating Overlay, Radar/Spider, FMO Overlay.

    Parameters
    ----------
    state:
        Shared FlowState — read-only access for data extraction.
    gate_coordinator:
        Optional coordinator (not used for rendering, but kept for API parity
        with StatisticsExplorer and PopulationAnalysisViewer).
    parent:
        Qt parent widget.
    """

    def __init__(
        self,
        state: FlowState,
        gate_coordinator=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._gate_coordinator = gate_coordinator
        self._extractor = ComparisonsDataExtractor()
        self._worker: ComparisonsWorker | None = None
        self._current_figure: Figure | None = None
        self._canvas_widget: FigureCanvasQTAgg | None = None

        # Build one options panel per plot type (instantiated once, reused)
        self._options_panels: dict[str, object] = {}

        self._setup_ui()
        self.refresh_samples()

        theme_manager.theme_changed.connect(self._apply_theme_styles)

    # ── UI Construction ──────────────────────────────────────────────────────

    def _setup_ui(self) -> None:  # noqa: PLR0915
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Left Sidebar ─────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("cmp_sidebar")
        sidebar.setFixedWidth(370)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(16, 16, 12, 16)
        cl.setSpacing(14)

        # 1. Plot type selector
        pt_hdr = QHBoxLayout()
        pt_hdr.addWidget(self._section_label("Plot Type"))
        self._plot_help_btn = BioHelpButton()
        pt_hdr.addWidget(self._plot_help_btn)
        pt_hdr.addStretch()
        cl.addLayout(pt_hdr)

        self._plot_type_combo = BioComboBox()
        self._plot_type_combo.setObjectName("ComparisonsPlotTypeCombo")
        for name in PLOT_REGISTRY:
            self._plot_type_combo.addItem(name)
        self._plot_type_combo.currentIndexChanged.connect(self._on_plot_type_changed)
        cl.addWidget(self._plot_type_combo)

        # 2. Samples
        smp_hdr = QHBoxLayout()
        smp_hdr.addWidget(self._section_label("Samples"))
        smp_help = BioHelpButton()
        smp_help.setHelpText(
            "Check which samples to include in the comparison plot. "
            "Each checked sample appears as a separate group or data series.",
            "Samples",
        )
        smp_hdr.addWidget(smp_help)
        smp_hdr.addStretch()
        cl.addLayout(smp_hdr)

        self._sample_list = BioListWidget()
        self._sample_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cl.addWidget(self._sample_list)

        _mini = "QPushButton { padding: 3px 10px; min-height: 26px; }"
        smp_btns = QHBoxLayout()
        btn_all_s = SecondaryButton("All")
        btn_all_s.setStyleSheet(_mini)
        btn_all_s.clicked.connect(lambda: self._check_all_list(self._sample_list, True))
        btn_none_s = SecondaryButton("None")
        btn_none_s.setStyleSheet(_mini)
        btn_none_s.clicked.connect(lambda: self._check_all_list(self._sample_list, False))
        smp_btns.addWidget(btn_all_s)
        smp_btns.addWidget(btn_none_s)
        smp_btns.addStretch()
        cl.addLayout(smp_btns)
        self._sample_list.itemChanged.connect(self._on_sample_changed)

        # 3. Populations
        pop_hdr = QHBoxLayout()
        pop_hdr.addWidget(self._section_label("Populations"))
        pop_help = BioHelpButton()
        pop_help.setHelpText(
            "Select which gated populations to compare.\n\n"
            "• For Violin and FMO: one population per sample is used.\n"
            "• For Radar and Heatmap: each checked population becomes a separate row/trace.\n"
            "• For Back-gating: select TWO populations — first = parent (grey), second = child (coloured).",
            "Populations",
        )
        pop_hdr.addWidget(pop_help)
        pop_hdr.addStretch()
        cl.addLayout(pop_hdr)

        self._pop_tree = QTreeWidget()
        self._pop_tree.setHeaderHidden(True)
        self._pop_tree.setMinimumHeight(200)
        cl.addWidget(self._pop_tree)

        pop_btns = QHBoxLayout()
        btn_all_p = SecondaryButton("All")
        btn_all_p.setStyleSheet(_mini)
        btn_all_p.clicked.connect(lambda: self._check_all_tree(True))
        btn_none_p = SecondaryButton("None")
        btn_none_p.setStyleSheet(_mini)
        btn_none_p.clicked.connect(lambda: self._check_all_tree(False))
        pop_btns.addWidget(btn_all_p)
        pop_btns.addWidget(btn_none_p)
        pop_btns.addStretch()
        cl.addLayout(pop_btns)

        # 4. Channels (hidden for plot types that manage their own channel selection)
        self._channel_section = QWidget()
        csl = QVBoxLayout(self._channel_section)
        csl.setContentsMargins(0, 0, 0, 0)
        csl.setSpacing(6)

        ch_hdr = QHBoxLayout()
        self._channel_section_label = self._section_label("Channels")
        ch_hdr.addWidget(self._channel_section_label)
        self._ch_help_btn = BioHelpButton()
        ch_hdr.addWidget(self._ch_help_btn)
        ch_hdr.addStretch()
        csl.addLayout(ch_hdr)

        self._channel_list = BioListWidget()
        self._channel_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._channel_list.setMaximumHeight(180)
        csl.addWidget(self._channel_list)

        ch_btns = QHBoxLayout()
        btn_all_ch = SecondaryButton("All")
        btn_all_ch.setStyleSheet(_mini)
        btn_all_ch.clicked.connect(lambda: self._check_all_list(self._channel_list, True))
        btn_none_ch = SecondaryButton("None")
        btn_none_ch.setStyleSheet(_mini)
        btn_none_ch.clicked.connect(lambda: self._check_all_list(self._channel_list, False))
        ch_btns.addWidget(btn_all_ch)
        ch_btns.addWidget(btn_none_ch)
        ch_btns.addStretch()
        csl.addLayout(ch_btns)

        cl.addWidget(self._channel_section)

        # 5. Per-plot options (QStackedWidget — one panel per plot type)
        opts_hdr = QHBoxLayout()
        opts_hdr.addWidget(self._section_label("Plot Options"))
        opts_hdr.addStretch()
        cl.addLayout(opts_hdr)

        self._options_stack = QStackedWidget()
        plot_names = list(PLOT_REGISTRY.keys())
        for name in plot_names:
            _, PanelClass = PLOT_REGISTRY[name]
            panel = PanelClass()
            self._options_panels[name] = panel
            self._options_stack.addWidget(panel)
        cl.addWidget(self._options_stack)

        cl.addSpacing(8)

        # 6. Generate button
        self._generate_btn = PrimaryButton("🔬 Generate Plot")
        self._generate_btn.clicked.connect(self._on_generate)
        cl.addWidget(self._generate_btn)

        cl.addStretch()
        scroll.setWidget(content)
        sidebar_layout.addWidget(scroll)
        main.addWidget(sidebar)

        # ── Right Workspace ──────────────────────────────────────────────────
        right = QWidget()
        right.setObjectName("cmp_right")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(16, 12, 16, 16)
        right_layout.setSpacing(10)

        # Toolbar
        toolbar = QHBoxLayout()
        self._status_lbl = QLabel("Select samples and click Generate Plot.")
        self._status_lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: 12px;")
        toolbar.addWidget(self._status_lbl)
        toolbar.addStretch()

        self._export_btn = SecondaryButton("📸 Export")
        self._export_btn.setToolTip("Save the current plot as PNG, PDF, or SVG")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        toolbar.addWidget(self._export_btn)

        right_layout.addLayout(toolbar)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        right_layout.addWidget(self._progress_bar)

        # Display stack: 0=placeholder, 1=canvas
        self._display_stack = QStackedWidget()
        self._display_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Placeholder
        placeholder = QWidget()
        ph_layout = QVBoxLayout(placeholder)
        ph_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_icon = QLabel("📊")
        ph_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph_icon.setStyleSheet("font-size: 52px;")
        ph_layout.addWidget(ph_icon)
        self._ph_lbl = QLabel(
            "Select samples, populations and a plot type\nthen click Generate Plot."
        )
        self._ph_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ph_lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: 14px;")
        ph_layout.addWidget(self._ph_lbl)
        self._display_stack.addWidget(placeholder)

        # Canvas placeholder (replaced when a figure is produced)
        self._canvas_container = QWidget()
        canvas_container_layout = QVBoxLayout(self._canvas_container)
        canvas_container_layout.setContentsMargins(0, 0, 0, 0)
        self._display_stack.addWidget(self._canvas_container)

        right_layout.addWidget(self._display_stack, stretch=1)
        main.addWidget(right, stretch=1)

        # Apply initial styles and trigger first plot-type switch
        self._apply_theme_styles()
        self._on_plot_type_changed(0)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {Colors.FG_SECONDARY}; font-weight: bold; font-size: 11px;"
            " text-transform: uppercase; letter-spacing: 0.5px;"
        )
        return lbl

    # ── Public API ───────────────────────────────────────────────────────────

    def refresh_samples(self) -> None:
        """Repopulate sample list from the current experiment state."""
        prev_checked = set()
        for i in range(self._sample_list.count()):
            item = self._sample_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                prev_checked.add(item.data(Qt.ItemDataRole.UserRole))

        self._sample_list.blockSignals(True)
        self._sample_list.clear()

        for sid, sample in self._state.data.experiment.samples.items():
            item = QListWidgetItem(sample.display_name)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            from PyQt6.QtGui import QColor

            item.setForeground(QColor(Colors.FG_PRIMARY))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if (sid in prev_checked or not prev_checked)
                else Qt.CheckState.Unchecked
            )
            self._sample_list.addItem(item)

        self._sample_list.blockSignals(False)
        row_h = self._sample_list.sizeHintForRow(0) if self._sample_list.count() > 0 else 24
        self._sample_list.setFixedHeight(max(32, self._sample_list.count() * row_h + 4))

        self._refresh_populations()
        self._refresh_channels()
        self._refresh_fmo_options()

    # ── Signals ──────────────────────────────────────────────────────────────

    def _on_plot_type_changed(self, index: int) -> None:
        """SRP: swap options panel + update help text + show/hide channel list."""
        self._options_stack.setCurrentIndex(index)
        plot_name = self._plot_type_combo.currentText()

        # Update the help button text
        if plot_name in PLOT_HELP:
            title, body = PLOT_HELP[plot_name]
            self._plot_help_btn.setHelpText(body, title)

        # Show/hide channel list
        no_channels = any(plot_name == p for p in PLOTS_WITHOUT_CHANNEL_LIST)
        self._channel_section.setVisible(not no_channels)

        # Update channel help text based on mode
        multi_ch = any(plot_name == p for p in PLOTS_MULTI_CHANNEL)
        if multi_ch:
            self._ch_help_btn.setHelpText(
                "Select multiple channels. Each channel becomes one column (heatmap) "
                "or one spoke (radar). Choose channels relevant to the populations you are comparing.",
                "Channels",
            )
        else:
            self._ch_help_btn.setHelpText(
                "Select a single channel to compare across samples. "
                "For example, choose CD3 to compare T-cell expression, or CD19 for B cells.",
                "Channel",
            )

        # Enforce single-channel selection for violin/FMO
        if not multi_ch and not no_channels:
            self._enforce_single_channel_selection()

        # Refresh populations and channels so tree/list use the correct selection mode
        self._refresh_channels()
        self._refresh_populations()

    def _on_sample_changed(self, _item: QListWidgetItem) -> None:
        self._refresh_populations()
        self._refresh_channels()
        self._refresh_fmo_options()

    def _on_generate(self) -> None:
        """Validate inputs, extract data, spawn worker."""
        if self._worker and self._worker.isRunning():
            return

        plot_name = self._plot_type_combo.currentText()
        RendererClass, _ = PLOT_REGISTRY[plot_name]
        panel = self._options_panels[plot_name]
        config = panel.get_config()  # type: ignore

        sample_ids = self._get_checked_sample_ids()
        pop_pairs = self._get_checked_populations()
        channel_keys = self._get_checked_channels()

        # Validate
        if not sample_ids:
            self._status_lbl.setText("⚠ No samples selected.")
            return

        try:
            render_kwargs = self._build_render_kwargs(
                plot_name, RendererClass, config, sample_ids, pop_pairs, channel_keys
            )
        except ValueError as e:
            self._status_lbl.setText(f"⚠ {e}")
            return

        # Inject theme colors (DIP: renderers don't import Qt/theme)
        render_kwargs.update(
            {
                "bg_color": Colors.BG_DARKEST,
                "fg_color": Colors.FG_PRIMARY,
                "border_color": Colors.BORDER,
                "accent_color": Colors.ACCENT_PRIMARY,
                "palette": _PALETTE,
            }
        )

        renderer = RendererClass()
        self._worker = ComparisonsWorker(renderer, render_kwargs)
        self._worker.finished_ok.connect(self._on_render_done)
        self._worker.finished_err.connect(self._on_render_error)
        self._worker.start()

        self._generate_btn.setEnabled(False)
        self._progress_bar.show()
        self._status_lbl.setText("⏳ Rendering…")

    def _build_render_kwargs(  # noqa: PLR0912, PLR0913, PLR0915
        self,
        plot_name: str,
        RendererClass,
        config: dict,
        sample_ids: list[str],
        pop_pairs: list[tuple],
        channel_keys: list[str],
    ) -> dict:
        """SRP: translate UI selections + state into renderer kwargs dict."""
        kwargs = dict(config)

        if plot_name == "🎻  Violin Plot":
            if not channel_keys:
                raise ValueError("Select a single channel for the violin plot.")
            channel = channel_keys[0]
            # Build channel label from first sample
            ch_labels = self._extractor.get_channel_list(self._state, sample_ids[0])
            ch_label = next((lbl for lbl, k in ch_labels if k == channel), channel)

            # For violin: one population per sample. pop_pairs are (sid, nid, label)
            # Build a mapping sid -> node_id from the checked populations
            sid_to_node: dict[str, str | None] = {}
            for pp in pop_pairs:
                pp_sid, pp_nid = pp[0], pp[1]
                if pp_sid not in sid_to_node:  # take first checked per sample
                    sid_to_node[pp_sid] = pp_nid

            data_per_label: dict[str, np.ndarray] = {}
            for sid in sample_ids:
                sample = self._state.data.experiment.samples.get(sid)
                label = sample.display_name if sample else sid
                node_id = sid_to_node.get(sid)
                vals = self._extractor.get_events_for_population(self._state, sid, node_id, channel)
                if len(vals) > 0:
                    data_per_label[label] = vals
            kwargs["data_per_label"] = data_per_label
            kwargs["channel_label"] = ch_label

        elif plot_name == "🗺️  Channel Heatmap":
            if not channel_keys:
                raise ValueError("Select at least one channel for the heatmap.")
            if not pop_pairs:
                raise ValueError("Select at least one population for the heatmap.")

            stat_name = config.get("stat", "median")
            stat_map = {
                "median": StatType.MEDIAN,
                "mean": StatType.MEAN,
                "geometric_mean": StatType.GEOMETRIC_MEAN,
            }
            stat_type = stat_map.get(stat_name, StatType.MEDIAN)

            matrix, row_labels, col_labels = self._extractor.get_statistic_matrix(
                self._state, pop_pairs, channel_keys, stat_type
            )
            kwargs["matrix"] = matrix
            kwargs["row_labels"] = row_labels
            kwargs["col_labels"] = col_labels

        elif plot_name == "🕷️  Radar Chart":
            if not channel_keys:
                raise ValueError("Select at least 3 channels for the radar chart.")
            if len(channel_keys) < 3:  # noqa: PLR2004
                raise ValueError("Select at least 3 channels for the radar chart.")
            if not pop_pairs:
                raise ValueError("Select at least one population for the radar chart.")

            ch_label_map = {}
            for sid in sample_ids:
                for lbl, k in self._extractor.get_channel_list(self._state, sid):
                    ch_label_map[k] = lbl
            col_labels = [ch_label_map.get(ch, ch) for ch in channel_keys]

            stat_name = config.get("stat", "median")
            use_median = stat_name != "mean"

            # One entry per (sample, population) pair — iterate pop_pairs directly
            data: dict[str, list[float]] = {}
            for sid, nid, plabel in pop_pairs:
                sample = self._state.data.experiment.samples.get(sid)
                if not sample or sample.fcs_data is None:
                    continue
                key = f"{sample.display_name} / {plabel}"
                df = sample.fcs_data.events
                if nid and sample.gate_tree:
                    node = sample.gate_tree.find_node_by_id(nid)
                    if node:
                        df = node.apply_hierarchy(df)
                vals_per_ch = []
                for ch in channel_keys:
                    assert df is not None
                    if ch in df.columns:
                        arr = df[ch].to_numpy(dtype=float)
                        arr = arr[np.isfinite(arr)]
                        vals_per_ch.append(
                            float(np.median(arr) if use_median else np.mean(arr))
                            if len(arr) > 0
                            else 0.0
                        )
                    else:
                        vals_per_ch.append(0.0)
                data[key] = vals_per_ch
            kwargs["data"] = data
            kwargs["channel_labels"] = col_labels

        elif plot_name == "📈  FMO Overlay":
            if not channel_keys:
                raise ValueError("Select the channel for the FMO overlay.")
            channel = channel_keys[0]
            fmo_sid = config.get("fmo_sample_id")
            real_sid = sample_ids[0] if sample_ids else None

            if not real_sid:
                raise ValueError("Select a sample to compare against the FMO control.")

            node_id = pop_pairs[0][1] if pop_pairs else None
            sample_vals = self._extractor.get_events_for_population(
                self._state, real_sid, node_id, channel
            )
            fmo_vals = np.array([])
            if fmo_sid:
                fmo_vals = self._extractor.get_events_for_population(
                    self._state, fmo_sid, None, channel
                )

            ch_labels = self._extractor.get_channel_list(self._state, real_sid)
            ch_label = next((lbl for lbl, k in ch_labels if k == channel), channel)
            real_sample = self._state.data.experiment.samples.get(real_sid)

            kwargs["sample_values"] = sample_vals
            kwargs["fmo_values"] = fmo_vals
            kwargs["channel_label"] = ch_label
            kwargs["sample_label"] = real_sample.display_name if real_sample else real_sid
            fmo_sample = self._state.data.experiment.samples.get(fmo_sid) if fmo_sid else None
            kwargs["fmo_label"] = fmo_sample.display_name if fmo_sample else "FMO Control"

        elif plot_name == "📊  Histogram Overlay":
            if not channel_keys:
                raise ValueError("Select a channel for the histogram overlay.")
            channel = channel_keys[0]

            # Build channel display label from first available sample
            ch_labels = self._extractor.get_channel_list(self._state, sample_ids[0])
            ch_label = next((lbl for lbl, k in ch_labels if k == channel), channel)

            # One curve per (sample, population) pair
            data_per_label = {}
            for sid, nid, plabel in pop_pairs:
                sample = self._state.data.experiment.samples.get(sid)
                if not sample:
                    continue
                sample_name = sample.display_name
                # Use "SampleName" when showing All Events, "SampleName / Gate" for sub-populations
                key = sample_name if nid is None else f"{sample_name} / {plabel}"
                vals = self._extractor.get_events_for_population(self._state, sid, nid, channel)
                if len(vals) > 0:
                    data_per_label[key] = vals

            if not data_per_label:
                raise ValueError("No event data found for the selected samples and populations.")

            kwargs["data_per_label"] = data_per_label
            kwargs["channel_label"] = ch_label

        return kwargs

    def _on_render_done(self, fig: Figure) -> None:
        """Replace canvas with the new figure."""
        self._current_figure = fig
        self._generate_btn.setEnabled(True)
        self._progress_bar.hide()

        # Remove old canvas
        container_layout = self._canvas_container.layout()
        if container_layout:
            while container_layout.count():
                item = container_layout.takeAt(0)
                if item:
                    w = item.widget()
                    if w:
                        w.deleteLater()

        canvas = FigureCanvasQTAgg(fig)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        canvas.setStyleSheet("background-color: transparent; border: none;")
        if container_layout:
            container_layout.addWidget(canvas)
        self._canvas_widget = canvas

        self._display_stack.setCurrentIndex(1)
        self._export_btn.setEnabled(True)
        self._status_lbl.setText("✓ Plot ready. Use Export to save.")
        self._worker = None

    def _on_render_error(self, msg: str) -> None:
        self._generate_btn.setEnabled(True)
        self._progress_bar.hide()
        self._status_lbl.setText(f"❌ Error: {msg}")
        logger.error("ComparisonsViewer render error: %s", msg)
        self._worker = None

    def _on_export(self) -> None:
        if not self._current_figure:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Plot",
            "",
            "PNG Image (*.png);;PDF Document (*.pdf);;SVG Vector (*.svg)",
        )
        if path:
            self._current_figure.savefig(path, dpi=300, bbox_inches="tight")
            self._status_lbl.setText(f"✓ Exported to {path}")

    # ── Data helpers ─────────────────────────────────────────────────────────

    def _get_checked_sample_ids(self) -> list[str]:
        result = []
        for i in range(self._sample_list.count()):
            item = self._sample_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def _get_checked_populations(self) -> list[tuple]:
        result = []
        it = QTreeWidgetItemIterator(self._pop_tree)
        while it.value():
            item = it.value()
            if item and item.checkState(0) == Qt.CheckState.Checked:
                sid = item.data(0, Qt.ItemDataRole.UserRole)
                nid = item.data(0, Qt.ItemDataRole.UserRole + 1)
                if nid is not False:  # False means it's a sample header, skip
                    label = item.text(0).strip().lstrip("⬡◆⊘ ")
                    result.append((sid, nid, label))
            it += 1
        return result

    def _is_single_pop_mode(self) -> bool:
        """True for plot types that use exactly one population per sample."""
        plot_name = self._plot_type_combo.currentText()
        # Heatmap and Radar benefit from multiple populations; others use one per sample.
        multi_pop = any(plot_name == p for p in PLOTS_MULTI_POPULATION)
        return not multi_pop

    def _is_multi_channel_mode(self) -> bool:
        plot_name = self._plot_type_combo.currentText()
        return any(plot_name == p for p in PLOTS_MULTI_CHANNEL)

    def _get_checked_channels(self) -> list[str]:
        result = []
        for i in range(self._channel_list.count()):
            item = self._channel_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                result.append(item.data(Qt.ItemDataRole.UserRole))
        return result

    def _check_all_list(self, lst: BioListWidget, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        lst.blockSignals(True)
        is_channel_list = lst is self._channel_list
        for i in range(lst.count()):
            item = lst.item(i)
            if not item:
                continue
            # In single-channel mode, only check the first item when "All" is pressed
            if is_channel_list and not self._is_multi_channel_mode() and checked:
                item.setCheckState(Qt.CheckState.Checked if i == 0 else Qt.CheckState.Unchecked)
            else:
                item.setCheckState(state)
        lst.blockSignals(False)

    def _enforce_single_channel_selection(self) -> None:
        """Ensure only one channel is checked in single-channel plot modes."""
        self._channel_list.blockSignals(True)
        found_checked = False
        for i in range(self._channel_list.count()):
            item = self._channel_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                if found_checked:
                    item.setCheckState(Qt.CheckState.Unchecked)
                else:
                    found_checked = True
        # If nothing is checked, check the first item
        if not found_checked and self._channel_list.count() > 0:
            first = self._channel_list.item(0)
            if first:
                first.setCheckState(Qt.CheckState.Checked)
        self._channel_list.blockSignals(False)

    def _check_all_tree(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._pop_tree.blockSignals(True)
        it = QTreeWidgetItemIterator(self._pop_tree)
        while it.value():
            item = it.value()
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(0, state)
            it += 1
        self._pop_tree.blockSignals(False)

    def _refresh_populations(self) -> None:
        single_pop_mode = self._is_single_pop_mode()
        self._pop_tree.blockSignals(True)
        self._pop_tree.clear()

        sample_ids = self._get_checked_sample_ids()
        for sid in sample_ids:
            sample = self._state.data.experiment.samples.get(sid)
            if not sample or not sample.gate_tree:
                continue

            sample_item = QTreeWidgetItem([sample.display_name])
            sample_item.setData(0, Qt.ItemDataRole.UserRole, sid)
            sample_item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
            sample_item.setFlags(Qt.ItemFlag.ItemIsEnabled)

            # In single-pop mode, default to "All Events" checked and gates unchecked
            all_item = QTreeWidgetItem(["⬡  All Events"])
            all_item.setData(0, Qt.ItemDataRole.UserRole, sid)
            all_item.setData(0, Qt.ItemDataRole.UserRole + 1, None)
            all_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            all_item.setCheckState(0, Qt.CheckState.Checked)
            sample_item.addChild(all_item)

            def _add_nodes(node, parent_item, _sid=sid, _single=single_pop_mode):
                if not node.is_root:
                    icon = "⊘ " if node.negated else "◆ "
                    it = QTreeWidgetItem([f"{icon}{node.name}"])
                    it.setData(0, Qt.ItemDataRole.UserRole, _sid)
                    it.setData(0, Qt.ItemDataRole.UserRole + 1, node.node_id)
                    it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                    # In single-pop mode, gates start unchecked (user picks one per sample)
                    it.setCheckState(
                        0, Qt.CheckState.Unchecked if _single else Qt.CheckState.Checked
                    )
                    parent_item.addChild(it)
                    for child in node.children:
                        _add_nodes(child, it, _sid, _single)
                else:
                    for child in node.children:
                        _add_nodes(child, parent_item, _sid, _single)

            _add_nodes(sample.gate_tree, sample_item)
            self._pop_tree.addTopLevelItem(sample_item)
            sample_item.setExpanded(True)

        self._pop_tree.blockSignals(False)

        # Wire radio-button behaviour for single-pop mode
        # Disconnect first to avoid double-connections on repeated refreshes
        try:
            self._pop_tree.itemChanged.disconnect(self._on_pop_item_changed)
        except TypeError:
            pass
        if single_pop_mode:
            self._pop_tree.itemChanged.connect(self._on_pop_item_changed)

    def _refresh_channels(self) -> None:
        prev_checked = set()
        for i in range(self._channel_list.count()):
            item = self._channel_list.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                prev_checked.add(item.data(Qt.ItemDataRole.UserRole))

        self._channel_list.blockSignals(True)
        self._channel_list.clear()
        no_channels_mode = any(
            self._plot_type_combo.currentText() == p for p in PLOTS_WITHOUT_CHANNEL_LIST
        )

        sample_ids = self._get_checked_sample_ids()
        if not sample_ids:
            self._channel_list.blockSignals(False)
            return

        channels = []
        sample = self._state.data.experiment.samples.get(sample_ids[0])
        if sample and sample.fcs_data:
            from biopro_plugins.flow_cytometry.analysis.fcs_io import (
                get_channel_marker_label,
                get_fluorescence_channels,
            )

            fluo_channels = get_fluorescence_channels(sample.fcs_data)
            channels = [(get_channel_marker_label(sample.fcs_data, ch), ch) for ch in fluo_channels]

        for label, key in channels:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            from PyQt6.QtGui import QColor

            item.setForeground(QColor(Colors.FG_PRIMARY))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if (key in prev_checked or not prev_checked)
                else Qt.CheckState.Unchecked
            )
            self._channel_list.addItem(item)

        row_h = self._channel_list.sizeHintForRow(0) if self._channel_list.count() > 0 else 24
        self._channel_list.setFixedHeight(min(180, self._channel_list.count() * max(24, row_h) + 4))

        # In single-channel mode, enforce only one item is checked after populating
        if not self._is_multi_channel_mode() and not no_channels_mode:
            self._enforce_single_channel_selection()

        self._channel_list.blockSignals(False)

        # Wire channel single-select enforcement
        try:
            self._channel_list.itemChanged.disconnect(self._on_channel_item_changed)
        except TypeError:
            pass
        if not self._is_multi_channel_mode():
            self._channel_list.itemChanged.connect(self._on_channel_item_changed)

        # Update channel picker in backgating options panel — removed (back-gating chart removed)

    def _on_pop_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        """Radio-button: when a population is checked, uncheck all others in same sample."""
        if item.checkState(column) != Qt.CheckState.Checked:
            return
        sid = item.data(0, Qt.ItemDataRole.UserRole)
        if sid is None:
            return
        self._pop_tree.blockSignals(True)
        it = QTreeWidgetItemIterator(self._pop_tree)
        while it.value():
            other = it.value()
            if other and other is not item:
                other_sid = other.data(0, Qt.ItemDataRole.UserRole)
                other_nid = other.data(0, Qt.ItemDataRole.UserRole + 1)
                if other_sid == sid and other_nid is not False:
                    other.setCheckState(0, Qt.CheckState.Unchecked)
            it += 1
        self._pop_tree.blockSignals(False)

    def _on_channel_item_changed(self, item: QListWidgetItem) -> None:
        """Single-channel enforcement: when a channel is checked, uncheck all others."""
        if item.checkState() != Qt.CheckState.Checked:
            return
        self._channel_list.blockSignals(True)
        for i in range(self._channel_list.count()):
            ch_item = self._channel_list.item(i)
            if ch_item and ch_item is not item:
                ch_item.setCheckState(Qt.CheckState.Unchecked)
        self._channel_list.blockSignals(False)

    def _refresh_fmo_options(self) -> None:
        """Update the FMO options panel with the current sample list."""
        fmo_panel = self._options_panels.get("📈  FMO Overlay")
        if fmo_panel and hasattr(fmo_panel, "populate_samples"):
            samples = [
                (s.display_name, sid) for sid, s in self._state.data.experiment.samples.items()
            ]
            fmo_panel.populate_samples(samples)

    # ── Theme ────────────────────────────────────────────────────────────────

    def _apply_theme_styles(self) -> None:  # noqa: PLR0912
        self.setStyleSheet(f"background-color: {Colors.BG_DARKEST};")

        sidebar = self.findChild(QWidget, "cmp_sidebar")
        if sidebar:
            sidebar.setStyleSheet(
                f"background-color: {Colors.BG_DARKEST}; border-right: 1px solid {Colors.BORDER};"
            )
        right = self.findChild(QWidget, "cmp_right")
        if right:
            right.setStyleSheet(f"background-color: {Colors.BG_DARK};")

        if hasattr(self, "_plot_type_combo") and hasattr(
            self._plot_type_combo, "_apply_theme_styles"
        ):
            self._plot_type_combo._apply_theme_styles()

        from PyQt6.QtGui import QColor

        fg_color = QColor(Colors.FG_PRIMARY)

        for list_w in (
            getattr(self, "_sample_list", None),
            getattr(self, "_channel_list", None),
        ):
            if list_w:
                list_w.setStyleSheet(
                    f"QListWidget {{ background: {Colors.BG_DARKEST}; border: 1px solid {Colors.BORDER};"
                    f" border-radius: 4px; color: {Colors.FG_PRIMARY}; }}"
                    f"QListWidget::item {{ color: {Colors.FG_PRIMARY}; padding: 2px 4px; }}"
                    f"QListWidget::item:hover {{ background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; }}"
                    f"QListWidget::item:selected {{ background: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY}; }}"
                )
                for i in range(list_w.count()):
                    list_w.item(i).setForeground(fg_color)

        self._status_lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: 12px;")
        self._ph_lbl.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: 14px;")

        self._pop_tree.setStyleSheet(
            f"QTreeWidget {{ background: {Colors.BG_DARKEST}; border: 1px solid {Colors.BORDER};"
            f" border-radius: 4px; color: {Colors.FG_PRIMARY}; }}"
            f"QTreeWidget::item {{ color: {Colors.FG_PRIMARY}; padding: 2px 4px; }}"
            f"QTreeWidget::item:hover {{ background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; }}"
            f"QTreeWidget::item:selected {{ background: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY}; }}"
        )

        def _recolor_tree(item):
            item.setForeground(0, fg_color)
            for c in range(item.childCount()):
                _recolor_tree(item.child(c))

        for i in range(self._pop_tree.topLevelItemCount()):
            _recolor_tree(self._pop_tree.topLevelItem(i))

        # Re-theme all options panels and their dropdowns
        color_dict = {
            "fg_primary": Colors.FG_PRIMARY,
            "fg_secondary": Colors.FG_SECONDARY,
            "bg_dark": Colors.BG_DARK,
            "bg_darkest": Colors.BG_DARKEST,
            "border": Colors.BORDER,
            "accent": Colors.ACCENT_PRIMARY,
        }
        for panel in self._options_panels.values():
            if hasattr(panel, "apply_theme"):
                panel.apply_theme(color_dict)
            if hasattr(panel, "_apply_theme_styles"):
                panel._apply_theme_styles()
            for combo in panel.findChildren(QWidget):  # type: ignore
                if hasattr(combo, "_apply_theme_styles"):
                    combo._apply_theme_styles()

        # Re-render current plot with new theme colours
        if self._current_figure is not None:
            self._on_generate()
