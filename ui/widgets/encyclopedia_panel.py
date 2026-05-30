"""Encyclopedia Panel - View biological marker information."""

from __future__ import annotations

from typing import TYPE_CHECKING

from biopro.shared.ui.ui_components import PrimaryButton
from biopro.ui.theme import Colors, Fonts
from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QTextEdit, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from analysis.biology_services import MarkerService


class EncyclopediaPanel(QWidget):
    """A central workspace panel to search and view marker details."""

    def __init__(self, marker_service: MarkerService, parent=None):
        super().__init__(parent)
        self._marker_service = marker_service
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Search Bar
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Enter marker (e.g., CD4, CD8, CD25)...")
        self._search_input.setStyleSheet(
            f"background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY};"
            f" padding: 8px; border: 1px solid {Colors.BORDER}; border-radius: 4px;"
        )
        self._search_input.returnPressed.connect(self._perform_search)

        self._search_btn = PrimaryButton("Search")
        self._search_btn.clicked.connect(self._perform_search)

        search_layout.addWidget(self._search_input)
        search_layout.addWidget(self._search_btn)
        layout.addLayout(search_layout)

        # Content Area
        self._content_display = QTextEdit()
        self._content_display.setReadOnly(True)
        self._content_display.setStyleSheet(
            f"background: {Colors.BG_DARKER}; color: {Colors.FG_PRIMARY};"
            f" padding: 12px; border: 1px solid {Colors.BORDER}; border-radius: 4px;"
            f" font-size: {Fonts.SIZE_NORMAL}px;"
        )
        self._content_display.setHtml(f"<h3 style='color: {Colors.FG_SECONDARY};'>Search for a marker to begin</h3>")
        layout.addWidget(self._content_display)

    def _perform_search(self):
        query = self._search_input.text().strip()
        if not query:
            return

        self._content_display.setHtml(f"<p style='color: {Colors.FG_SECONDARY};'>Searching {query}...</p>")

        # In a real app, this should be off-thread to not block the UI,
        # but for demonstration we'll block briefly since we have caching and short timeouts.
        result = self._marker_service.get_marker_info(query)

        if result:
            html = f"""
            <h2 style='color: #58a6ff;'>{result.get('name', query)}</h2>
            <h4 style='color: {Colors.FG_SECONDARY};'>Name: {result.get('label', '')}</h4>
            <hr style='border: 1px solid {Colors.BORDER};'>
            <h4 style='color: #c9d1d9;'>Biological Function:</h4>
            <p style='line-height: 1.6; font-size: {Fonts.SIZE_NORMAL}px;'>{result.get('description', '')}</p>
            <br>
            <p style='color: {Colors.FG_SECONDARY}; font-size: {Fonts.SIZE_SMALL}px;'>
            <i>Source: {result.get('ontology', 'Local Fallback')}</i><br>
            <i><a href="{result.get('iri', '#')}" style="color: #58a6ff;">View Entry</a></i>
            </p>
            """
            self._content_display.setHtml(html)
        else:
            self._content_display.setHtml(f"<h3 style='color: #f85149;'>No results found for '{query}'</h3>")
