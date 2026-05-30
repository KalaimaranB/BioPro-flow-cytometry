"""Cluster Results Panel — Dedicated UI for analyzing HDBSCAN UMAP clusters."""

from __future__ import annotations

from typing import Any

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from biopro.ui.theme import Colors, Fonts
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class CopyableCanvas(FigureCanvasQTAgg):
    """A Matplotlib canvas that supports right-click to copy to clipboard."""

    def __init__(self, figure):
        super().__init__(figure)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        copy_action = QAction("Copy Image to Clipboard", self)
        copy_action.triggered.connect(self._copy_to_clipboard)
        menu.addAction(copy_action)
        menu.exec(self.mapToGlobal(pos))

    def _copy_to_clipboard(self):
        pixmap = self.grab()
        QApplication.clipboard().setPixmap(pixmap)


class ClusterResultsPanel(QWidget):
    """A multi-tabbed panel displaying UMAP plot gallery and statistical tables."""

    def __init__(
        self, results: dict[str, Any], state=None, gate_coordinator=None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._results = results
        self._state = state
        self._gate_coordinator = gate_coordinator
        self._poly_selector = None
        self._custom_cluster_masks = []  # List of tuples (mask, row_widget_references)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid {Colors.BORDER}; border-radius: 4px; background: {Colors.BG_DARK}; }}
            QTabBar::tab {{ background: {Colors.BG_MEDIUM}; color: {Colors.FG_SECONDARY}; padding: 8px 16px; border: 1px solid {Colors.BORDER}; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; font-weight: bold; border-bottom: 1px solid {Colors.BG_DARK}; }}
            QTabBar::tab:hover:!selected {{ background: {Colors.BG_LIGHT}; }}
        """)

        layout.addWidget(self._tabs)

        self._build_plot_gallery()

        if "clusters" in self._results:
            self._build_stats_tab()
            self._build_heatmap_tab()
            self._build_populations_tab()

    def _create_plot(
        self,
        embedding: np.ndarray,
        color_data: np.ndarray,
        title: str,
        cmap: str,
        norm=None,
        is_discrete=False,
        min_c=0,
        max_c=0,
    ) -> CopyableCanvas:
        fig = Figure(facecolor=Colors.BG_DARK, figsize=(5, 4))
        ax = fig.add_subplot(111)
        ax.set_facecolor("#0d1117")
        ax.tick_params(colors=Colors.FG_SECONDARY, labelsize=7)
        for spine in ("bottom", "left"):
            ax.spines[spine].set_color(Colors.BORDER)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

        ax.set_title(title, color=Colors.FG_PRIMARY, fontsize=10, fontweight="bold", pad=8)
        ax.set_aspect("equal", "datalim")

        scatter = ax.scatter(
            embedding[:, 0], embedding[:, 1], c=color_data, cmap=cmap, norm=norm, s=1.0, alpha=0.75, edgecolors="none"
        )

        cbar = fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04)
        cbar.ax.yaxis.set_tick_params(colors=Colors.FG_SECONDARY, labelsize=7)
        cbar.outline.set_color(Colors.BORDER)

        if is_discrete:
            cbar.set_ticks(np.arange(min_c, max_c + 1))
            cbar.set_label("Cluster ID", color=Colors.FG_SECONDARY, fontsize=8)
        else:
            cbar.set_label("Intensity", color=Colors.FG_SECONDARY, fontsize=8)

        fig.tight_layout()
        canvas = CopyableCanvas(fig)
        canvas.setMinimumHeight(350)
        return canvas

    def _create_cluster_plot(self) -> CopyableCanvas | None:
        if "clusters" not in self._results:
            return None

        embedding = self._results["embedding"]
        clusters = self._results["clusters"]
        min_c = int(clusters.min())
        max_c = int(clusters.max())
        n_clusters = max_c - min_c + 1

        base_cmap = plt.get_cmap("tab20")
        colors = [base_cmap(i % 20) for i in range(n_clusters)]
        cmap = mcolors.ListedColormap(colors)
        bounds = np.arange(min_c, max_c + 2) - 0.5
        norm = mcolors.BoundaryNorm(bounds, cmap.N)

        return self._create_plot(embedding, clusters, "Auto-Cluster ID", cmap, norm, True, min_c, max_c)

    def _build_plot_gallery(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid = QGridLayout(container)
        grid.setSpacing(16)

        embedding = self._results["embedding"]
        channels = self._results["channels"]
        intensities = self._results["intensities"]

        row, col = 0, 0
        max_cols = 2

        # 1. Plot Auto-Cluster ID first (if available)
        cluster_canvas = self._create_cluster_plot()
        if cluster_canvas:
            grid.addWidget(cluster_canvas, row, col)
            col += 1

        # 2. Plot all markers
        for i, ch in enumerate(channels):
            if col >= max_cols:
                col = 0
                row += 1

            canvas = self._create_plot(embedding, intensities[:, i], ch, "viridis")
            grid.addWidget(canvas, row, col)
            col += 1

        scroll.setWidget(container)
        self._tabs.addTab(scroll, "Plot Gallery")

    def _build_stats_tab(self) -> None:
        stats_df = self._results.get("cluster_stats")
        if stats_df is None:
            return

        table = QTableWidget(len(stats_df), len(stats_df.columns))
        table.setHorizontalHeaderLabels(stats_df.columns)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setStyleSheet(f"""
            QTableWidget {{ background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; gridline-color: {Colors.BORDER}; }}
            QHeaderView::section {{ background: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY}; font-weight: bold; border: 1px solid {Colors.BORDER}; padding: 4px; }}
        """)

        for i in range(len(stats_df)):
            cluster_id = int(stats_df.iloc[i, 0])
            base_cmap = plt.get_cmap("tab20")
            c = base_cmap(cluster_id % 20)
            cluster_color = QColor(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))

            for j, col_name in enumerate(stats_df.columns):
                val = stats_df.iloc[i, j]
                if col_name == "% of Total":
                    item = QTableWidgetItem(f"{val:.2f}%")
                else:
                    item = QTableWidgetItem(str(val))

                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col_name == "Cluster ID":
                    item.setBackground(cluster_color)
                    item.setForeground(
                        QColor(255, 255, 255) if (c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114) < 0.5 else QColor(0, 0, 0)
                    )

                table.setItem(i, j, item)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(16)

        cluster_plot = self._create_cluster_plot()
        if cluster_plot:
            cluster_plot.setMinimumWidth(350)
            layout.addWidget(cluster_plot, stretch=1)

        layout.addWidget(table, stretch=2)

        self._tabs.addTab(container, "Cluster Statistics")

    def _build_heatmap_tab(self) -> None:
        heatmap_df = self._results.get("marker_heatmap")
        if heatmap_df is None:
            return

        table = QTableWidget(len(heatmap_df), len(heatmap_df.columns) + 1)
        headers = ["Cluster ID"] + list(heatmap_df.columns)
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setStyleSheet(f"""
            QTableWidget {{ background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; gridline-color: {Colors.BORDER}; }}
            QHeaderView::section {{ background: {Colors.BG_MEDIUM}; color: {Colors.FG_PRIMARY}; font-weight: bold; border: 1px solid {Colors.BORDER}; padding: 4px; }}
        """)

        # Find global min/max for color scaling
        global_min = heatmap_df.values.min()
        global_max = heatmap_df.values.max()
        val_range = global_max - global_min if global_max > global_min else 1.0

        for i in range(len(heatmap_df)):
            cluster_id = int(heatmap_df.index[i])

            base_cmap = plt.get_cmap("tab20")
            c = base_cmap(cluster_id % 20)
            cluster_color = QColor(int(c[0] * 255), int(c[1] * 255), int(c[2] * 255))

            id_item = QTableWidgetItem(str(cluster_id))
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            id_item.setBackground(cluster_color)
            id_item.setForeground(
                QColor(255, 255, 255) if (c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114) < 0.5 else QColor(0, 0, 0)
            )
            table.setItem(i, 0, id_item)

            for j, col_name in enumerate(heatmap_df.columns):
                val = heatmap_df.iloc[i, j]
                norm = (val - global_min) / val_range

                if norm < 0.5:
                    intensity = int((1.0 - (norm * 2)) * 150)
                    bg_color = QColor(0, 0, intensity)
                else:
                    intensity = int(((norm - 0.5) * 2) * 200)
                    bg_color = QColor(intensity, 0, 0)

                item = QTableWidgetItem(f"{val:.2f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setBackground(bg_color)
                item.setForeground(QColor(255, 255, 255))

                table.setItem(i, j + 1, item)

        table.resizeColumnsToContents()

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(16)

        cluster_plot = self._create_cluster_plot()
        cluster_plot = self._create_cluster_plot()
        if cluster_plot:
            cluster_plot.setMinimumWidth(350)
            layout.addWidget(cluster_plot, stretch=1)

        layout.addWidget(table, stretch=3)

        self._tabs.addTab(container, "Marker Heatmap")

    def _build_populations_tab(self) -> None:
        from biopro_sdk.plugin.components import BioLineEdit, PrimaryButton, SecondaryButton
        from PyQt6.QtWidgets import QCheckBox, QLabel, QScrollArea, QVBoxLayout, QWidget

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(16)

        cluster_plot = self._create_cluster_plot()
        if cluster_plot:
            cluster_plot.setMinimumWidth(350)
            layout.addWidget(cluster_plot, stretch=1)

        # Right panel for list of clusters
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Select Auto-Clusters to export as Populations:")
        title.setStyleSheet(f"color: {Colors.FG_PRIMARY}; font-weight: bold;")
        right_layout.addWidget(title)

        btn_draw = SecondaryButton("✏️ Draw Custom Cluster")
        btn_draw.clicked.connect(self._activate_polygon_drawer)
        right_layout.addWidget(btn_draw)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        list_container = QWidget()
        self._list_layout = QVBoxLayout(list_container)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        stats_df = self._results.get("cluster_stats")
        self._cluster_ui_elements = {}
        if stats_df is not None:
            for i in range(len(stats_df)):
                cluster_id = int(stats_df.iloc[i, 0])
                count = int(stats_df.iloc[i, 1])
                pct = float(stats_df.iloc[i, 2])

                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(0, 0, 0, 0)

                checkbox = QCheckBox(f"Cluster {cluster_id}")
                checkbox.setStyleSheet(f"color: {Colors.FG_SECONDARY};")
                checkbox.setChecked(True)

                name_edit = BioLineEdit()
                name_edit.setText(f"UMAP Cluster {cluster_id}")
                name_edit.setPlaceholderText("Population Name")

                info = QLabel(f"{count} events ({pct:.1f}%)")
                info.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")

                row_layout.addWidget(checkbox)
                row_layout.addWidget(name_edit, stretch=1)
                row_layout.addWidget(info)

                self._list_layout.addWidget(row_widget)
                self._cluster_ui_elements[cluster_id] = (checkbox, name_edit)

        scroll.setWidget(list_container)
        right_layout.addWidget(scroll, stretch=1)

        self._cluster_canvas = cluster_plot

        btn_create = PrimaryButton("➕ Create Populations")
        btn_create.clicked.connect(self._create_populations)
        right_layout.addWidget(btn_create)

        layout.addWidget(right_panel, stretch=2)

        self._tabs.addTab(container, "Populations")

    def _create_populations(self) -> None:
        if not self._state:
            return

        sample_id = self._results.get("sample_id")
        target_node_id = self._results.get("target_node_id")
        if not sample_id:
            return

        sample = self._state.data.experiment.samples.get(sample_id)
        if not sample or not sample.gate_tree:
            return

        target_node = sample.gate_tree.find_node_by_id(target_node_id) if target_node_id else sample.gate_tree
        if not target_node:
            return

        indices = self._results.get("indices", [])
        if len(indices) == 0:
            return

        from analysis.gating.subset import SubsetGate

        # Create UMAP parent node — mark it as a subset node, not a geometric gate node
        umap_parent = target_node.add_child(gate=SubsetGate(indices=indices), name="UMAP Reduction")
        # Flag that this is a UMAP container — pipeline view will skip thumbnail
        umap_parent.is_umap_parent = True

        clusters = self._results.get("clusters")
        created_count = 0

        if clusters is not None:
            for cluster_id, (checkbox, name_edit) in self._cluster_ui_elements.items():
                if checkbox.isChecked():
                    name = name_edit.text() or f"Cluster {cluster_id}"
                    mask = clusters == cluster_id
                    cluster_indices = indices[mask]

                    umap_parent.add_child(gate=SubsetGate(indices=cluster_indices), name=name)
                    created_count += 1

        for mask, (checkbox, name_edit) in self._custom_cluster_masks:
            if checkbox.isChecked():
                name = name_edit.text() or "Custom Cluster"
                cluster_indices = indices[mask]
                umap_parent.add_child(gate=SubsetGate(indices=cluster_indices), name=name)
                created_count += 1

        # Trigger stats recomputation so event/percentage counts appear correctly
        if self._gate_coordinator:
            self._gate_coordinator.recompute_all_stats(sample_id)

        from biopro_sdk.plugin import CentralEventBus

        from analysis import events

        CentralEventBus.publish(events.GATE_CREATED, {"sample_id": sample_id})

        from biopro_sdk.plugin.dialogs import show_info

        show_info(self, "Populations Created", f"Successfully exported {created_count} UMAP clusters to the Pipeline.")

    def _activate_polygon_drawer(self) -> None:
        if not hasattr(self, "_cluster_canvas") or not self._cluster_canvas:
            return

        from matplotlib.widgets import PolygonSelector

        ax = self._cluster_canvas.figure.axes[0]

        from biopro_sdk.plugin.dialogs import show_info

        show_info(
            self,
            "Draw Cluster",
            "Click on the UMAP plot to draw a polygon.\nDouble-click or press Enter to complete the shape.",
        )

        self._poly_selector = PolygonSelector(
            ax,
            self._on_polygon_drawn,
            useblit=True,
            props=dict(color=Colors.ACCENT_PRIMARY, linestyle="-", linewidth=2, alpha=0.8),
        )

    def _on_polygon_drawn(self, verts) -> None:
        from biopro_sdk.plugin.components import BioLineEdit
        from matplotlib.path import Path
        from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QWidget

        if self._poly_selector:
            self._poly_selector.disconnect_events()
            self._poly_selector.set_visible(False)
            self._poly_selector = None

        path = Path(verts)
        embedding = self._results["embedding"]
        mask = path.contains_points(embedding)

        count = int(np.sum(mask))
        if count == 0:
            return

        pct = (count / len(embedding)) * 100
        custom_idx = len(self._custom_cluster_masks) + 1

        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        checkbox = QCheckBox(f"Custom {custom_idx}")
        checkbox.setStyleSheet(f"color: {Colors.FG_SECONDARY};")
        checkbox.setChecked(True)

        name_edit = BioLineEdit()
        name_edit.setText(f"Custom Cluster {custom_idx}")
        name_edit.setPlaceholderText("Population Name")

        info = QLabel(f"{count} events ({pct:.1f}%)")
        info.setStyleSheet(f"color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;")

        row_layout.addWidget(checkbox)
        row_layout.addWidget(name_edit, stretch=1)
        row_layout.addWidget(info)

        self._list_layout.addWidget(row_widget)
        self._custom_cluster_masks.append((mask, (checkbox, name_edit)))
