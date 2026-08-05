"""ComparisonsDataExtractor — pulls gated event arrays from FlowState.

SRP: knows only how to extract data from FlowState; does not render or build Qt.
DIP: depends on FlowState interface, not on internal FCS structures directly.
"""

from __future__ import annotations

import numpy as np

from biopro_plugins.flow_cytometry.analysis.fcs_io import get_channel_marker_label
from biopro_plugins.flow_cytometry.analysis.state import FlowState
from biopro_plugins.flow_cytometry.analysis.statistics import StatType


class ComparisonsDataExtractor:
    """Extracts data from FlowState for the comparison renderers.

    Each public method takes a config dict (from IOptionsPanel.get_config())
    and the current FlowState, and returns a plain Python / numpy dict that
    can be passed directly to IPlotRenderer.render().

    No Qt, no matplotlib — purely data manipulation.
    """

    def get_events_for_population(
        self,
        state: FlowState,
        sample_id: str,
        node_id: str | None,
        channel: str,
    ) -> np.ndarray:
        """Return 1-D array of channel values for a gated population."""
        sample = state.data.experiment.samples.get(sample_id)
        if sample is None or sample.fcs_data is None:
            return np.array([])

        df = sample.fcs_data.events
        if node_id and sample.gate_tree:
            node = sample.gate_tree.find_node_by_id(node_id)
            if node:
                df = node.apply_hierarchy(df)

        assert df is not None
        if channel not in df.columns:
            return np.array([])

        vals = df[channel].to_numpy(dtype=float)
        return vals[np.isfinite(vals)]

    def get_2d_events_for_population(
        self,
        state: FlowState,
        sample_id: str,
        node_id: str | None,
        x_channel: str,
        y_channel: str,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return (x_vals, y_vals) arrays for a gated population."""
        sample = state.data.experiment.samples.get(sample_id)
        if sample is None or sample.fcs_data is None:
            return np.array([]), np.array([])

        df = sample.fcs_data.events
        if node_id and sample.gate_tree:
            node = sample.gate_tree.find_node_by_id(node_id)
            if node:
                df = node.apply_hierarchy(df)

        x = (
            df[x_channel].to_numpy(dtype=float)  # type: ignore
            #             assert df is not None
            if x_channel in df.columns  # type: ignore
            else np.array([])
        )
        y = (
            df[y_channel].to_numpy(dtype=float)  # type: ignore
            #             assert df is not None
            if y_channel in df.columns  # type: ignore
            else np.array([])
        )

        # Filter to valid (finite) pairs
        valid = np.isfinite(x) & np.isfinite(y)
        return x[valid], y[valid]

    def get_statistic_matrix(  # noqa: PLR0912
        self,
        state: FlowState,
        pop_pairs: list[tuple[str, str | None, str]],
        channels: list[str],
        stat_type: StatType = StatType.MEDIAN,
    ) -> tuple[np.ndarray, list[str], list[str]]:
        """Build a (n_pop_pairs × n_channels) matrix of statistics.

        Args:
            pop_pairs: list of (sample_id, node_id_or_None, label) — one row per pair.
            channels:  list of FCS channel keys.
            stat_type: which statistic to compute per cell.

        Returns:
            matrix:     ndarray shape (n_pairs, n_channels)
            row_labels: display label per row
            col_labels: display label per channel column
        """
        if not pop_pairs:
            return np.empty((0, len(channels))), [], channels[:]

        # Build channel display labels from the first available sample
        col_labels: list[str] = []
        ref_sample = None
        for sid, _, _ in pop_pairs:
            s = state.data.experiment.samples.get(sid)
            if s and s.fcs_data:
                ref_sample = s
                break
        if ref_sample:
            for ch in channels:
                col_labels.append(get_channel_marker_label(ref_sample.fcs_data, ch))  # type: ignore
        else:
            col_labels = channels[:]

        n_rows = len(pop_pairs)
        matrix = np.full((n_rows, len(channels)), np.nan)
        row_labels: list[str] = []

        for row, (sid, nid, plabel) in enumerate(pop_pairs):
            sample = state.data.experiment.samples.get(sid)
            if not sample or sample.fcs_data is None:
                row_labels.append(plabel)
                continue

            df = sample.fcs_data.events
            if nid and sample.gate_tree:
                node = sample.gate_tree.find_node_by_id(nid)
                if node:
                    df = node.apply_hierarchy(df)

            row_labels.append(f"{sample.display_name} / {plabel}")
            for col, ch in enumerate(channels):
                assert df is not None
                if ch in df.columns:
                    vals = df[ch].to_numpy(dtype=float)
                    vals = vals[np.isfinite(vals)]
                    if len(vals) > 0:
                        if stat_type == StatType.GEOMETRIC_MEAN:
                            pos = vals[vals > 0]
                            matrix[row, col] = (
                                float(np.exp(np.mean(np.log(pos)))) if len(pos) > 0 else 0.0
                            )
                        elif stat_type == StatType.MEAN:
                            matrix[row, col] = float(np.mean(vals))
                        else:  # MEDIAN default
                            matrix[row, col] = float(np.median(vals))

        return matrix, row_labels, col_labels

    def get_channel_list(self, state: FlowState, sample_id: str) -> list[tuple[str, str]]:
        """Return [(display_label, channel_key), ...] for a sample."""
        sample = state.data.experiment.samples.get(sample_id)
        if not sample or sample.fcs_data is None:
            return []
        result = []
        for ch in sample.fcs_data.channels:
            label = get_channel_marker_label(sample.fcs_data, ch)
            result.append((label, ch))
        return result
