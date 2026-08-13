from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


class GateDeletionDialog(QDialog):
    """Dialog to confirm gate deletion and select scope (single sample vs group)."""

    def __init__(
        self,
        gate_name: str,
        sample_name: str,
        groups: list[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Gate Deletion")
        self.setModal(True)
        self.resize(400, 150)

        self.groups = groups

        layout = QVBoxLayout(self)

        lbl_msg = QLabel(f"Are you sure you want to delete the gate '<b>{gate_name}</b>'?")
        lbl_msg.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl_msg)

        layout.addSpacing(10)

        self.radio_sample = QRadioButton(f"Delete for this sample only ({sample_name})")
        self.radio_sample.setChecked(True)
        layout.addWidget(self.radio_sample)

        # Group scope
        h_layout = QHBoxLayout()
        self.radio_group = QRadioButton("Delete across group:")
        h_layout.addWidget(self.radio_group)

        self.combo_group = QComboBox()
        for group_id, group_name in groups:
            self.combo_group.addItem(group_name, group_id)

        if not groups:
            self.radio_group.setEnabled(False)
            self.combo_group.setEnabled(False)
        else:
            self.combo_group.setEnabled(False)  # Disabled by default since sample radio is checked
            self.radio_group.toggled.connect(self.combo_group.setEnabled)

        h_layout.addWidget(self.combo_group)
        h_layout.addStretch()
        layout.addLayout(h_layout)

        layout.addSpacing(15)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_deletion_scope(self) -> tuple[str, str | None]:
        """Returns ('sample', None) or ('group', selected_group_id)."""
        if self.radio_group.isChecked() and self.groups:
            return "group", self.combo_group.currentData()
        return "sample", None
