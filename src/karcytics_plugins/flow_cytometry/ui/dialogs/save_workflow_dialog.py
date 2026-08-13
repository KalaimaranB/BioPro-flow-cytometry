"""Dialog to capture metadata before saving a workflow."""

from datetime import datetime

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
)


class SaveWorkflowDialog(QDialog):
    """Dialog to capture metadata before saving a workflow."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save Workflow")
        self.setMinimumWidth(400)
        self.layout = QVBoxLayout(self)

        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., WT vs KO Replicate 1")

        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Briefly describe the analysis...")
        self.desc_input.setMaximumHeight(80)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("e.g., ponceau, ko_mice, week_4")

        form.addRow("Workflow Name:", self.name_input)
        form.addRow("Description:", self.desc_input)
        form.addRow("Tags (comma separated):", self.tags_input)

        self.layout.addLayout(form)

        # Standard Save/Cancel buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # Disable save if name is empty
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
        self.name_input.textChanged.connect(
            lambda text: self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(
                bool(text.strip())
            )
        )

        self.layout.addWidget(self.buttons)

    def get_metadata(self) -> dict:
        """Extracts and formats the user input."""
        tags = [t.strip().lower() for t in self.tags_input.text().split(",") if t.strip()]
        return {
            "name": self.name_input.text().strip(),
            "description": self.desc_input.toPlainText().strip(),
            "tags": tags,
            "timestamp": datetime.now().isoformat(),
        }
