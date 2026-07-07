import math
import random

from PyQt6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from biopro.ui.theme import Colors, Fonts
except ImportError:

    class Colors:
        BG_DARKEST = "#0d1117"
        BG_DARK = "#161b22"
        FG_PRIMARY = "#e6edf3"
        FG_SECONDARY = "#8b949e"
        BORDER = "#30363d"
        ACCENT_PRIMARY = "#00bcd4"

    class Fonts:
        SIZE_SMALL = 11
        SIZE_NORMAL = 13
        SIZE_LARGE = 18
        SIZE_XLARGE = 24
        FAMILY_UI = "Inter, sans-serif"


class HexagonBadge(QWidget):
    """Draws a sleek, glowing tech/biology hexagon badge."""

    def __init__(self, size=80):
        super().__init__()
        self.setFixedSize(size, size)
        self._glow = 0.0

        # Simple breathing animation for the badge
        self._anim = QPropertyAnimation(self, b"glow")
        self._anim.setDuration(2000)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.setLoopCount(-1)  # Infinite loop
        self._anim.start()

    def _get_glow(self):
        return self._glow

    def _set_glow(self, value):
        self._glow = value
        self.update()

    glow = pyqtProperty(float, _get_glow, _set_glow)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2.2

        # Hexagon path
        path = QPainterPath()
        for i in range(6):
            angle_deg = 60 * i - 30
            angle_rad = math.pi / 180 * angle_deg
            x = cx + radius * math.cos(angle_rad)
            y = cy + radius * math.sin(angle_rad)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()

        # Outer glow
        glow_radius = radius + 2 + (self._glow * 4)
        glow_path = QPainterPath()
        for i in range(6):
            angle_deg = 60 * i - 30
            angle_rad = math.pi / 180 * angle_deg
            x = cx + glow_radius * math.cos(angle_rad)
            y = cy + glow_radius * math.sin(angle_rad)
            if i == 0:
                glow_path.moveTo(x, y)
            else:
                glow_path.lineTo(x, y)
        glow_path.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        base_color = QColor(Colors.ACCENT_PRIMARY)
        glow_color = QColor(
            base_color.red(),
            base_color.green(),
            base_color.blue(),
            int(40 + self._glow * 40),
        )
        painter.setBrush(glow_color)
        painter.drawPath(glow_path)

        # Inner Hexagon
        pen = QPen(base_color, 2)
        painter.setPen(pen)

        # Gradient fill
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(Colors.BG_DARK))
        grad.setColorAt(
            1, QColor(base_color.red(), base_color.green(), base_color.blue(), 30)
        )
        painter.setBrush(grad)

        painter.drawPath(path)

        # Center core (like a cell nucleus or node)
        painter.setBrush(base_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy), radius * 0.25, radius * 0.25)

        # Lines connecting to vertices (tech network feel)
        painter.setPen(
            QPen(
                QColor(base_color.red(), base_color.green(), base_color.blue(), 100), 1
            )
        )
        for i in range(6):
            angle_deg = 60 * i - 30
            angle_rad = math.pi / 180 * angle_deg
            x = cx + radius * math.cos(angle_rad)
            y = cy + radius * math.sin(angle_rad)
            painter.drawLine(QPointF(cx, cy), QPointF(x, y))


class CourseCompleteOverlay(QWidget):
    """A full-screen overlay congratulating the user for completing a course."""

    dismissed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.hide()

        self._badge_name = ""
        self._course_name = ""

        # Background nodes for tech effect
        self._nodes = []
        for _ in range(40):
            self._nodes.append(
                {
                    "x": random.uniform(0, 1),
                    "y": random.uniform(0, 1),
                    "vx": random.uniform(-0.001, 0.001),
                    "vy": random.uniform(-0.001, 0.001),
                }
            )

        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self._update_bg)
        self._bg_timer.setInterval(50)

        self._setup_ui()

    def _setup_ui(self) -> None:
        # Full screen layout
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Central card
        self._card = QFrame()
        self._card.setObjectName("CompleteCard")
        self._card.setStyleSheet(f"""
            QFrame#CompleteCard {{
                background-color: {Colors.BG_DARK};
                border: 1px solid {Colors.ACCENT_PRIMARY};
                border-radius: 12px;
            }}
        """)

        # Add shadow to card
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setColor(QColor(Colors.ACCENT_PRIMARY).darker(200))
        shadow.setOffset(0, 0)
        self._card.setGraphicsEffect(shadow)

        self._card.setFixedSize(550, 420)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(40, 40, 40, 40)
        card_layout.setSpacing(15)
        card_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )

        # Tech Badge
        self._badge_icon = HexagonBadge(90)
        card_layout.addWidget(self._badge_icon, 0, Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("MODULE COMPLETED")
        title.setStyleSheet(f"""
            font-family: {Fonts.FAMILY_UI};
            font-size: {Fonts.SIZE_LARGE}px;
            font-weight: 800;
            letter-spacing: 2px;
            color: {Colors.ACCENT_PRIMARY};
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title)

        # Subtitle / Message
        self._message_label = QLabel("Course module executed successfully.")
        self._message_label.setStyleSheet(f"""
            font-family: {Fonts.FAMILY_UI};
            font-size: {Fonts.SIZE_NORMAL}px;
            color: {Colors.FG_PRIMARY};
            line-height: 1.4;
        """)
        self._message_label.setWordWrap(True)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._message_label)

        # Separation line
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {Colors.BORDER}; margin: 10px 0px;")
        card_layout.addWidget(sep)

        # Badge display container
        badge_layout = QHBoxLayout()
        badge_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_layout.setSpacing(10)

        cert_label = QLabel("CERTIFICATION ACQUIRED:")
        cert_label.setStyleSheet(f"""
            font-family: {Fonts.FAMILY_UI};
            font-size: 10px;
            font-weight: bold;
            color: {Colors.FG_SECONDARY};
            letter-spacing: 1px;
        """)

        self._badge_label = QLabel("Badge Name")
        self._badge_label.setStyleSheet(f"""
            font-family: {Fonts.FAMILY_UI};
            font-size: {Fonts.SIZE_NORMAL}px;
            font-weight: bold;
            color: #ffffff;
            background-color: {Colors.BG_DARKEST};
            padding: 8px 16px;
            border-radius: 4px;
            border: 1px solid {Colors.BORDER};
        """)

        badge_info_layout = QVBoxLayout()
        badge_info_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_info_layout.addWidget(cert_label, 0, Qt.AlignmentFlag.AlignCenter)
        badge_info_layout.addWidget(self._badge_label, 0, Qt.AlignmentFlag.AlignCenter)

        card_layout.addLayout(badge_info_layout)

        card_layout.addStretch()

        # Continue Button
        self._continue_btn = QPushButton("RETURN TO WORKSPACE")
        self._continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._continue_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Colors.ACCENT_PRIMARY};
                border: 2px solid {Colors.ACCENT_PRIMARY};
                border-radius: 4px;
                padding: 12px 24px;
                font-family: {Fonts.FAMILY_UI};
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background-color: {Colors.ACCENT_PRIMARY};
                color: {Colors.BG_DARKEST};
            }}
            QPushButton:pressed {{
                background-color: #00acc1;
                border-color: #00acc1;
            }}
        """)
        self._continue_btn.clicked.connect(self._on_continue)
        card_layout.addWidget(self._continue_btn, 0, Qt.AlignmentFlag.AlignCenter)

        main_layout.addWidget(self._card)

    def _update_bg(self):
        # Update node positions
        for n in self._nodes:
            n["x"] += n["vx"]
            n["y"] += n["vy"]
            if n["x"] < 0 or n["x"] > 1:
                n["vx"] *= -1
            if n["y"] < 0 or n["y"] > 1:
                n["vy"] *= -1
        self.update()

    def paintEvent(self, event) -> None:
        """Draw a sleek, dark tech overlay background with floating network nodes."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Base overlay
        painter.fillRect(self.rect(), QColor(13, 17, 23, 220))

        w, h = self.width(), self.height()

        # Draw network nodes
        accent = QColor(Colors.ACCENT_PRIMARY)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 50))

        for n in self._nodes:
            painter.drawEllipse(QPointF(n["x"] * w, n["y"] * h), 3, 3)

        # Draw connections
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 20), 1))
        for i, n1 in enumerate(self._nodes):
            for n2 in self._nodes[i + 1 :]:
                dx = (n1["x"] - n2["x"]) * w
                dy = (n1["y"] - n2["y"]) * h
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 150:
                    alpha = int(20 * (1 - dist / 150))
                    painter.setPen(
                        QPen(
                            QColor(accent.red(), accent.green(), accent.blue(), alpha),
                            1,
                        )
                    )
                    painter.drawLine(
                        QPointF(n1["x"] * w, n1["y"] * h),
                        QPointF(n2["x"] * w, n2["y"] * h),
                    )

    def show_completion(self, course_id: str, badge_name: str) -> None:
        """Display the overlay with specific course data."""
        self._course_name = course_id.replace("_", " ").title()
        self._badge_name = badge_name

        msg = f"<span style='color:{Colors.FG_SECONDARY}'>You have successfully completed the </span><b>{self._course_name}</b><span style='color:{Colors.FG_SECONDARY}'> module.</span>"
        self._message_label.setText(msg)
        self._badge_label.setText(badge_name)

        self.show()
        self.raise_()
        self._bg_timer.start()

        # Simple pop animation for the card
        self._anim = QPropertyAnimation(self._card, b"geometry")
        self._anim.setDuration(500)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)

        # Calculate target geometry
        parent_rect = self.parent().rect() if self.parent() else QRect(0, 0, 1024, 768)
        cx = parent_rect.width() // 2
        cy = parent_rect.height() // 2

        start_rect = QRect(cx, cy, 0, 0)
        end_rect = QRect(cx - 275, cy - 210, 550, 420)

        self._anim.setStartValue(start_rect)
        self._anim.setEndValue(end_rect)
        self._anim.start()

    def _on_continue(self) -> None:
        self._bg_timer.stop()
        self.hide()
        self.dismissed.emit()
