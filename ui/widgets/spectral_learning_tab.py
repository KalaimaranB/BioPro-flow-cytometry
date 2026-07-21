import numpy as np
from biopro.ui.theme import Colors
from biopro_sdk.plugin.components import BioCaptionLabel, PrimaryButton, SecondaryButton
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.patches as patches
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QTextBrowser,
    QLineEdit,
    QPushButton,
    QLabel,
)
from PyQt6.QtCore import QTimer


class SpectralLearningTab(QWidget):
    """Educational tab for teaching compensation interactively."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer
        self._current_step = 0
        self._max_steps = 11
        self._completed_steps = set()
        self._drag_state = None

        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._animate_step)
        self._anim_progress = 0.0
        self._is_animating = False

        self._setup_ui()
        self._apply_theme_styles()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # Header
        header = QHBoxLayout()
        self._step_label = BioCaptionLabel("Step 1")
        header.addWidget(self._step_label)
        header.addStretch()

        self._btn_prev = SecondaryButton("← Previous")
        self._btn_prev.clicked.connect(self._prev_step)
        header.addWidget(self._btn_prev)

        self._btn_next = PrimaryButton("Next Step →")
        self._btn_next.clicked.connect(self._next_step)
        header.addWidget(self._btn_next)

        root.addLayout(header)

        # Main content area
        content = QHBoxLayout()

        # Left side: Explanation & Inputs
        left_panel = QVBoxLayout()
        self._explanation = QTextBrowser()
        self._explanation.setMinimumWidth(350)
        self._explanation.setMaximumWidth(450)
        self._explanation.setOpenLinks(False)
        self._explanation.anchorClicked.connect(self._on_html_link_clicked)
        left_panel.addWidget(self._explanation, stretch=1)

        # Interactive container for widgets (like QLineEdit)
        self._interactive_container = QWidget()
        self._interactive_layout = QHBoxLayout(self._interactive_container)
        self._interactive_layout.setContentsMargins(0, 0, 0, 0)
        left_panel.addWidget(self._interactive_container)

        content.addLayout(left_panel)

        self._figure = Figure(facecolor=Colors.BG_DARK)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._ax = self._figure.add_subplot(111)
        self._style_axes()

        self._canvas_wrapper = QWidget()
        canvas_layout = QVBoxLayout(self._canvas_wrapper)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.addWidget(self._canvas)

        self._canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self._canvas.mpl_connect("motion_notify_event", self._on_canvas_mouse_move)
        self._canvas.mpl_connect("button_release_event", self._on_canvas_mouse_release)

        content.addWidget(self._canvas_wrapper, stretch=1)
        root.addLayout(content, stretch=1)

    def _style_axes(self):
        self._figure.patch.set_facecolor(Colors.BG_DARK)
        self._ax.set_facecolor(Colors.BG_DARK)
        self._ax.tick_params(colors=Colors.FG_SECONDARY, labelsize=9)
        for spine in ("bottom", "left"):
            self._ax.spines[spine].set_color(Colors.BORDER)
        for spine in ("top", "right"):
            self._ax.spines[spine].set_visible(False)

    def _apply_theme_styles(self):
        self._step_label.setStyleSheet(
            f"color: {Colors.FG_PRIMARY}; font-size: 16px; font-weight: bold;"
        )
        self._explanation.setStyleSheet(
            f"background: {Colors.BG_DARK}; color: {Colors.FG_PRIMARY}; border: 1px solid {Colors.BORDER}; border-radius: 6px; padding: 12px; font-size: 14px;"
        )
        if hasattr(self, "_canvas_wrapper"):
            self._canvas_wrapper.setStyleSheet(
                f"border: 1px solid {Colors.BORDER}; border-radius: 6px;"
            )
        self.update_view()

    def _clear_interactive_widgets(self):
        for i in reversed(range(self._interactive_layout.count())):
            widget = self._interactive_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

    def _prev_step(self):
        if self._current_step > 0:
            self._current_step -= 1
            self.update_view()

    def _next_step(self):
        if self._current_step < self._max_steps - 1:
            self._current_step += 1
            self.update_view()

    def showEvent(self, event):
        super().showEvent(event)
        self.update_view()

    def _set_axes_labels(self, x_label, y_label):
        self._ax.set_xlabel(f"{x_label}", color=Colors.FG_SECONDARY, fontsize=10)
        self._ax.set_ylabel(f"{y_label}", color=Colors.FG_SECONDARY, fontsize=10)

    def update_view(self, from_animation=False):
        fluors = self._viewer._active_fluors
        self._btn_prev.setEnabled(self._current_step > 0)
        can_advance = (self._current_step in self._completed_steps) and (
            self._current_step < self._max_steps - 1
        )
        self._btn_next.setEnabled(can_advance)
        self._clear_interactive_widgets()
        self._ax.clear()
        self._style_axes()
        if not from_animation:
            self._animation_timer.stop()
            self._is_animating = False

        if not fluors:
            self._step_label.setText("Waiting for Selection...")
            self._explanation.setHtml(
                "<h3>No Colors Selected</h3><p>Please add a fluorophore in the Analysis tab.</p>"
            )
            self._ax.text(
                0.5,
                0.5,
                "Add fluorophores to begin",
                ha="center",
                va="center",
                color=Colors.FG_DISABLED,
                transform=self._ax.transAxes,
                fontsize=12,
            )
            self._ax.set_xlim(0, 1)
            self._ax.set_ylim(0, 1)
            self._canvas.draw()
            return

        step_funcs = [
            self._render_step_1,
            self._render_step_2,
            self._render_step_3,
            self._render_step_4,
            self._render_step_5,
            self._render_step_6,
            self._render_step_7,
            self._render_step_8,
            self._render_step_9,
            self._render_step_10,
            self._render_step_11,
        ]

        step_funcs[self._current_step](fluors)
        self._figure.tight_layout(pad=1.0)
        self._canvas.draw()

    # ==========================
    # STEP 1: The Physics
    # ==========================
    def _render_step_1(self, fluors):
        self._step_label.setText("Step 1: The Physics of Light")
        html = """
        <h3 style="color: #58a6ff;">Detectors and Filters</h3>
        <p>A flow cytometer uses detectors covered by colored glass filters to "see" light. Each filter only allows a specific range of light wavelengths to pass through to the detector.</p>
        <p>This graph shows the actual light emitted by your fluorescent dyes across different wavelengths. Notice how the light spreads out like a bell curve.</p>
        """
        if 0 not in self._completed_steps:
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: To detect this dye efficiently, we need to place our filter where the light is brightest. Drag the gray vertical band (the Detector Filter) over the peak of the emission curve.</p>"
            init_val = 400
        else:
            init_val = 520

        self._explanation.setHtml(html)
        self._ax.set_title("Emission Spectra", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Wavelength (nm)", "Intensity")

        peak_x = 500
        for name, data in fluors.items():
            if "em_data" in data:
                color = data.get("color", "#aaaaaa")
                arr = np.array(data["em_data"], dtype=float)
                x, y = arr[:, 0], arr[:, 1]
                peak = np.max(y)
                if peak > 0:
                    y = y / peak
                self._ax.plot(x, y, color=color, lw=2, alpha=0.8)
                self._ax.fill_between(x, y, alpha=0.15, color=color)
                peak_x = x[np.argmax(y)]
                break  # Just use first fluor for this demo

        self._filter_center = init_val
        self._filter_width = 30
        self._filter_patch = patches.Rectangle(
            (self._filter_center - self._filter_width / 2, 0),
            self._filter_width,
            1.1,
            facecolor="gray",
            alpha=0.3,
            picker=5,
        )
        self._ax.add_patch(self._filter_patch)
        self._target_peak_x = peak_x

        self._ax.set_xlim(350, 800)
        self._ax.set_ylim(0, 1.1)

    # ==========================
    # STEP 2: Identifying Leakage
    # ==========================
    def _render_step_2(self, fluors):
        self._step_label.setText("Step 2: Identifying Leakage")
        html = """
        <h3 style="color: #d2a8ff;">Spillover</h3>
        <p>Spillover is the fundamental problem in flow cytometry. When we use multiple dyes, their emission curves overlap. The light from one dye spreads out so much that a portion of it enters the detector meant for a completely different dye!</p>
        <p>The gray band represents the <b>Detector Filter</b> for the second dye. Notice how the first dye's curve extends into this area.</p>
        """
        if 1 not in self._completed_steps:
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: Identify the interference. Click inside the gray detector band where the FIRST dye's curve spills over.</p>"

        self._explanation.setHtml(html)
        self._ax.set_title("Emission Curve Overlap", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Wavelength (nm)", "Intensity")

        peaks = []
        selected_fluors = []

        # Try to find PE and PerCP first
        pe_key = None
        percp_key = None
        for k, data in fluors.items():
            label = data.get("display_label", k).lower()
            if "pe" in label and "cy" not in label and "percp" not in label:
                pe_key = k
            elif "percp" in label:
                percp_key = k

        if pe_key and percp_key:
            selected_fluors = [pe_key, percp_key]
        else:
            selected_fluors = list(fluors.keys())[:2]

        for name in selected_fluors:
            data = fluors[name]
            if "em_data" in data:
                color = data.get("color", "#aaaaaa")
                arr = np.array(data["em_data"], dtype=float)
                x, y = arr[:, 0], arr[:, 1]
                peak = np.max(y)
                if peak > 0:
                    y = y / peak
                self._ax.plot(
                    x,
                    y,
                    color=color,
                    lw=2,
                    alpha=0.8,
                    label=data.get("display_label", name),
                )
                self._ax.fill_between(x, y, alpha=0.15, color=color)
                peaks.append(x[np.argmax(y)])

        if len(peaks) == 2:
            self._overlap_x = peaks[1]
            filter_width = 30
            self._filter_patch = patches.Rectangle(
                (peaks[1] - filter_width / 2, 0),
                filter_width,
                1.1,
                facecolor="gray",
                alpha=0.3,
            )
            self._ax.add_patch(self._filter_patch)
            self._ax.text(
                peaks[1], 0.8, "Detector 2", color=Colors.FG_SECONDARY, ha="center"
            )

        self._ax.legend(
            facecolor=Colors.BG_DARKEST,
            edgecolor=Colors.BORDER,
            labelcolor=Colors.FG_PRIMARY,
        )
        self._ax.set_xlim(350, 800)
        self._ax.set_ylim(0, 1.1)

    # ==========================
    # STEP 3: Reading the Plot
    # ==========================
    def _render_step_3(self, fluors):
        self._step_label.setText("Step 3: Reading the Scatter Plot")
        html = """
        <h3 style="color: #58a6ff;">Translating to Scatter</h3>
        <p>While emission curves explain the physics, we don't look at curves when analyzing data. We look at 2D scatter plots where every single dot represents one cell passing through the lasers.</p>
        <p>Let's see what happens to a cell when its light leaks into the wrong detector. If a cell only has Dye 1, it should only be bright in Detector 1. But because of the spillover we just saw, it will also appear falsely bright in Detector 2.</p>
        """
        if 2 not in self._completed_steps:
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: Click the cell that is bright in Detector 1 to drop it into the plot and see how spillover affects its position.</p>"

        self._explanation.setHtml(html)
        self._ax.set_title("Single Cell Analysis", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Detector 1", "Detector 2")

        self._ax.scatter(
            [200], [200], color=Colors.FG_SECONDARY, s=50, label="Dim Cell"
        )
        if 2 in self._completed_steps:
            self._ax.scatter(
                [800], [200], color="#58a6ff", s=50, label="Bright Cell (No Leak)"
            )
            self._ax.scatter(
                [800], [400], color="#d2a8ff", s=50, label="Bright Cell (With Leak!)"
            )
            self._ax.annotate(
                "Leakage pushes it UP",
                xy=(800, 380),
                xytext=(600, 600),
                arrowprops=dict(arrowstyle="->", color=Colors.FG_PRIMARY),
                color=Colors.FG_PRIMARY,
            )
        else:
            self._step3_target = self._ax.scatter(
                [800], [200], color="#58a6ff", s=50, picker=10
            )

        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    # ==========================
    # STEP 4: Unstained Control
    # ==========================
    def _render_step_4(self, fluors):
        self._step_label.setText("Step 4: Unstained Control")
        html = """
        <h3 style="color: #58a6ff;">Finding "Zero"</h3>
        <p>Before we can fix spillover, we need to know what 'zero' looks like. Cells have a natural background glow called autofluorescence. Even with absolutely no dye, they will produce a signal.</p>
        <p>We run an <b>Unstained Control</b> (a sample with no fluorescent dyes) to measure this baseline. Any signal above this baseline is considered a true positive.</p>
        """
        if 3 not in self._completed_steps:
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: Drag the crosshair to set the baseline threshold. Move it so that all the unstained cells are contained in the bottom-left 'Negative' quadrant.</p>"
            init_val = 800
        else:
            init_val = 200

        self._explanation.setHtml(html)
        self._ax.set_title("Unstained Cells", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Detector 1", "Detector 2")

        np.random.seed(42)
        self._ax.scatter(
            np.random.normal(100, 30, 500),
            np.random.normal(100, 30, 500),
            color=Colors.FG_SECONDARY,
            alpha=0.5,
            s=10,
        )

        self._step4_hline = self._ax.axhline(init_val, color=Colors.BORDER, ls="--")
        self._step4_vline = self._ax.axvline(init_val, color=Colors.BORDER, ls="--")
        self._step4_crosshair = self._ax.plot(
            [init_val],
            [init_val],
            marker="+",
            color="white",
            markersize=20,
            markeredgewidth=2,
            picker=10,
        )[0]

        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    # ==========================
    # STEP 5: Ideal vs Reality
    # ==========================
    def _render_step_5(self, fluors):
        self._step_label.setText("Step 5: Ideal vs Reality")
        first_fluor = list(fluors.keys())[0].upper()
        color = fluors[list(fluors.keys())[0]].get("color", "#aaaaaa")
        html = f"""
        <h3 style="color: {color};">The Single Stain Control</h3>
        <p>To measure exactly how much spillover is happening, we run a <b>Single Stain Control</b>: a sample stained with ONLY {first_fluor}.</p>
        <p>If there were no spillover, these cells would form a perfectly flat horizontal line (the white dots). Because of the leakage we saw in Step 2, the population slants upwards! Some of these cells cross our baseline threshold and appear as false positives.</p>
        """
        if 4 not in self._completed_steps:
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: Identify the cells causing problems. Click on the False Positive cells (the ones that crossed the horizontal threshold into the top-right quadrant).</p>"

        self._explanation.setHtml(html)
        self._ax.set_title("Ideal vs Real Spillover", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels(f"Primary ({first_fluor})", "Secondary")

        np.random.seed(42)
        x_ideal = np.random.normal(700, 80, 200)
        y_ideal = np.random.normal(100, 20, 200)
        y_real = x_ideal * 0.25 + np.random.normal(0, 20, 200)

        self._ax.scatter(
            np.random.normal(100, 30, 200),
            np.random.normal(100, 30, 200),
            color=Colors.FG_SECONDARY,
            alpha=0.3,
            s=10,
        )
        self._ax.scatter(
            x_ideal, y_ideal, color="white", alpha=0.3, s=10, label="Ideal"
        )
        self._ax.scatter(
            x_ideal, y_real, color=color, alpha=0.7, s=15, label="Real (Leaking)"
        )

        self._ax.axhline(200, color=Colors.BORDER, ls="--")
        self._ax.axvline(200, color=Colors.BORDER, ls="--")
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    # ==========================
    # STEP 6: Calculating the Ratio
    # ==========================
    def _render_step_6(self, fluors):
        self._step_label.setText("Step 6: Calculating the Ratio")
        html = """
        <h3 style="color: #3fb950;">Doing the Math</h3>
        <p>To correct the data, we need to figure out exactly how severe the leakage is. We do this by calculating the <b>slope</b> of the slanted population.</p>
        <p>We need to ask: For every unit of true brightness in the Primary detector (the Run), how much false brightness appears in the Secondary detector (the Rise)?</p>
        """
        if 5 not in self._completed_steps:
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: We need a measurement. Click on the population near the far right (around X=800) to drop a ruler and measure the exact Rise and Run.</p>"

        self._explanation.setHtml(html)
        self._ax.set_title("Finding the Ratio", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Primary Detector", "Secondary Detector")

        np.random.seed(42)
        x_ideal = np.random.normal(800, 80, 200)
        y_real = x_ideal * 0.25 + np.random.normal(0, 20, 200)
        self._ax.scatter(x_ideal, y_real, color="#d2a8ff", alpha=0.4, s=15)

        if 5 in self._completed_steps:
            self._ax.plot([0, 800], [0, 200], color="#3fb950", lw=2, ls="-")
            self._ax.text(
                300,
                600,
                "Rise = 200, Run = 800",
                color="#3fb950",
                fontsize=16,
                fontweight="bold",
                bbox=dict(facecolor=Colors.BG_DARKEST, edgecolor="#3fb950", pad=10.0),
            )

        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    # ==========================
    # STEP 7: The Matrix
    # ==========================
    def _render_step_7(self, fluors):
        self._step_label.setText("Step 7: The Compensation Matrix")
        html = """
        <h3 style="color: #d2a8ff;">The Spillover Grid</h3>
        <p>In a real experiment, the software measures this slope for every possible combination of dyes and builds a <b>Compensation Matrix</b> (a grid of all the spillover ratios).</p>
        <p>Based on our calculation in Step 6 (Rise = 200, Run = 800), what percentage of the Primary signal leaks into the Secondary detector? (Hint: Rise divided by Run).</p>
        """
        if 6 not in self._completed_steps:
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: Calculate the percentage and type it into the box below, then click Submit.</p>"
        else:
            html += "<p style='color: #3fb950; font-weight: bold;'>Correct! 25% is the matrix value.</p>"

        self._explanation.setHtml(html)
        self._ax.set_title("The Matrix", color=Colors.FG_PRIMARY, pad=15)
        self._ax.axis("off")

        val_str = "25.0%" if 6 in self._completed_steps else "? %"
        self._ax.text(
            0.3,
            0.7,
            "Primary",
            ha="center",
            va="center",
            color=Colors.FG_SECONDARY,
            fontsize=12,
        )
        self._ax.text(
            0.7,
            0.7,
            "Secondary",
            ha="center",
            va="center",
            color=Colors.FG_SECONDARY,
            fontsize=12,
        )

        self._ax.text(
            0.1,
            0.5,
            "Primary",
            ha="right",
            va="center",
            color=Colors.FG_SECONDARY,
            fontsize=12,
        )
        self._ax.text(
            0.3, 0.5, "100.0%", ha="center", va="center", color="#3fb950", fontsize=16
        )
        self._ax.text(
            0.7,
            0.5,
            val_str,
            ha="center",
            va="center",
            color="#ff7b72" if 6 not in self._completed_steps else "#3fb950",
            fontsize=16,
        )

        self._ax.text(
            0.1,
            0.3,
            "Secondary",
            ha="right",
            va="center",
            color=Colors.FG_SECONDARY,
            fontsize=12,
        )
        self._ax.text(
            0.3, 0.3, "0.0%", ha="center", va="center", color="#58a6ff", fontsize=16
        )
        self._ax.text(
            0.7, 0.3, "100.0%", ha="center", va="center", color="#3fb950", fontsize=16
        )

        if 6 not in self._completed_steps:
            self._input = QLineEdit()
            self._input.setPlaceholderText("Enter % (e.g. 15)")
            self._input.setStyleSheet(
                f"background: {Colors.BG_DARKEST}; color: {Colors.FG_PRIMARY}; border: 1px solid {Colors.BORDER}; padding: 5px;"
            )

            btn = QPushButton("Submit")
            btn.setStyleSheet(
                "background: #3fb950; color: #ffffff; border-radius: 4px; padding: 5px 10px;"
            )
            btn.clicked.connect(self._check_step_7_input)

            self._step7_error = QLabel()
            self._step7_error.setStyleSheet("color: #ff7b72;")
            self._step7_error.hide()

            row = QHBoxLayout()
            row.addWidget(self._input)
            row.addWidget(btn)

            self._interactive_layout.addLayout(row)
            self._interactive_layout.addWidget(self._step7_error)

    def _check_step_7_input(self):
        val = self._input.text().strip()
        if val == "25" or val == "25%" or val == "25.0" or val == "25.0%":
            self._complete_step()
            self.update_view()
        else:
            self._step7_error.setText("Incorrect! Hint: 200 ÷ 800")
            self._step7_error.show()

    # ==========================
    # STEP 8: The Mixed Soup
    # ==========================
    def _render_step_8(self, fluors):
        self._step_label.setText("Step 8: The Mixed Soup")
        html = """
        <h3 style="color: #d29922;">The Problem</h3>
        <p>This is what a real, uncompensated sample looks like. All the cells are mixed together: negatives, single positives, and double positives.</p>
        <p>Because the single-positive populations are slanting diagonally, they contaminate the double-positive space. It's impossible to draw a clean rectangular gate around the true Double Positive cells without accidentally including false positives.</p>
        """
        if 7 not in self._completed_steps:
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: It's very difficult to tell them apart visually. Try to click where you think the True Double Positives are hiding in this mess.</p>"

        self._explanation.setHtml(html)
        self._ax.set_title("Uncompensated Sample", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Detector 1", "Detector 2")

        np.random.seed(99)
        self._ax.scatter(
            np.random.normal(100, 30, 200),
            np.random.normal(100, 30, 200),
            color=Colors.FG_SECONDARY,
            alpha=0.3,
            s=10,
        )

        x1 = np.random.normal(600, 80, 200)
        self._ax.scatter(
            x1,
            x1 * 0.4 + np.random.normal(0, 30, 200),
            color="#d29922",
            alpha=0.5,
            s=15,
        )
        y2 = np.random.normal(600, 80, 200)
        self._ax.scatter(
            y2 * 0.4 + np.random.normal(0, 30, 200),
            y2,
            color="#d29922",
            alpha=0.5,
            s=15,
        )
        self._ax.scatter(
            np.random.normal(750, 80, 100),
            np.random.normal(750, 80, 100),
            color="#58a6ff",
            alpha=0.8,
            s=15,
        )

        self._ax.axhline(200, color=Colors.BORDER, ls="--")
        self._ax.axvline(200, color=Colors.BORDER, ls="--")
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    # ==========================
    # STEP 9: Subtracting
    # ==========================
    def _render_step_9(self, fluors):
        self._step_label.setText("Step 9: Subtracting the Matrix")
        html = """
        <h3 style="color: #3fb950;">Applying the Math</h3>
        <p>Now it's time to fix the data using the Compensation Matrix we built. This process is essentially subtraction based on the percentages.</p>
        <p>Let's manually compensate one cell. This cell measures <b>800 AU</b> in Detector 1, and <b>300 AU</b> in Detector 2.</p>
        <p>We know from our Matrix that Detector 1 leaks <b>25%</b> of its signal into Detector 2. That means 25% of the 800 AU in Detector 1 is fake signal showing up in Detector 2.</p>
        <p>How many AU of fake signal should we subtract from Detector 2 to reveal the cell's true brightness?</p>
        """
        if 8 not in self._completed_steps:
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: Choose the correct subtraction amount.</p>"
            html += "<p><a href='step9_wrong1' style='color:#58a6ff;'>A) 50 AU</a><br><a href='step9_correct' style='color:#58a6ff;'>B) 200 AU</a><br><a href='step9_wrong2' style='color:#58a6ff;'>C) 800 AU</a></p>"
        else:
            html += "<p style='color: #3fb950; font-weight: bold;'>Correct! We subtract 200 AU.</p>"

        self._explanation.setHtml(html)
        self._ax.set_title(
            "Subtracting Leakage for One Cell", color=Colors.FG_PRIMARY, pad=15
        )
        self._set_axes_labels("Detector 1", "Detector 2")

        if 8 not in self._completed_steps:
            self._ax.scatter(
                [800], [300], color="#d29922", s=100, edgecolor="white", zorder=5
            )
        else:
            self._ax.scatter(
                [800], [100], color="#3fb950", s=100, edgecolor="white", zorder=5
            )
            self._ax.annotate(
                "Subtract 200 AU",
                xy=(800, 120),
                xytext=(800, 280),
                arrowprops=dict(
                    facecolor="#3fb950", edgecolor="none", width=3, headwidth=10
                ),
                color="#3fb950",
                ha="center",
                va="center",
                rotation=-90,
            )

        self._ax.axhline(200, color=Colors.BORDER, ls="--")
        self._ax.axvline(200, color=Colors.BORDER, ls="--")
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    # ==========================
    # STEP 10: Pulling the Lever
    # ==========================
    def _render_step_10(self, fluors):
        self._step_label.setText("Step 10: Pulling the Lever")
        html = """
        <h3 style="color: #58a6ff;">Compensate All</h3>
        <p>Of course, we don't manually subtract values cell-by-cell! The flow cytometry software uses linear algebra (specifically matrix inversion) to apply this subtraction to millions of cells instantly.</p>
        <p>This process mathematically 'straightens out' the populations, pulling the false signal down out of the adjacent detectors.</p>
        """
        if 9 not in self._completed_steps and not getattr(self, "_is_animating", False):
            html += "<p style='color: #3fb950; font-weight: bold;'>Action Required: Click 'Compensate All' below to watch the software apply the matrix and correct the entire sample.</p>"
            btn = QPushButton("⚙️ Compensate All")
            btn.setStyleSheet(
                "background: #58a6ff; color: #ffffff; border-radius: 4px; padding: 10px; font-weight: bold;"
            )
            btn.clicked.connect(self._start_animation)
            self._interactive_layout.addWidget(btn)
        elif getattr(self, "_is_animating", False):
            html += "<p style='color: #3fb950; font-weight: bold;'>Compensating...</p>"
        else:
            html += "<p style='color: #3fb950; font-weight: bold;'>Compensation complete!</p>"

        self._explanation.setHtml(html)
        self._ax.set_title("Applying Compensation", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Detector 1", "Detector 2")

        np.random.seed(99)
        self._bg_x = np.random.normal(100, 30, 200)
        self._bg_y = np.random.normal(100, 30, 200)

        self._p1_x = np.random.normal(600, 80, 200)
        self._p1_y_start = self._p1_x * 0.4 + np.random.normal(0, 30, 200)
        self._p1_y_end = np.random.normal(100, 30, 200)

        self._p2_y = np.random.normal(600, 80, 200)
        self._p2_x_start = self._p2_y * 0.4 + np.random.normal(0, 30, 200)
        self._p2_x_end = np.random.normal(100, 30, 200)

        self._dp_x_start = np.random.normal(750, 80, 100)
        self._dp_y_start = np.random.normal(750, 80, 100)
        self._dp_x_end = np.random.normal(600, 80, 100)
        self._dp_y_end = np.random.normal(600, 80, 100)

        # Plot current state based on anim_progress
        p = self._anim_progress
        self._ax.scatter(
            self._bg_x, self._bg_y, color=Colors.FG_SECONDARY, alpha=0.3, s=10
        )
        self._ax.scatter(
            self._p1_x,
            self._p1_y_start * (1 - p) + self._p1_y_end * p,
            color="#3fb950",
            alpha=0.6,
            s=15,
        )
        self._ax.scatter(
            self._p2_x_start * (1 - p) + self._p2_x_end * p,
            self._p2_y,
            color="#3fb950",
            alpha=0.6,
            s=15,
        )
        self._ax.scatter(
            self._dp_x_start * (1 - p) + self._dp_x_end * p,
            self._dp_y_start * (1 - p) + self._dp_y_end * p,
            color="#58a6ff",
            alpha=0.9,
            s=15,
        )

        self._ax.axhline(200, color=Colors.BORDER, ls="--")
        self._ax.axvline(200, color=Colors.BORDER, ls="--")
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    def _start_animation(self):
        self._is_animating = True
        self._clear_interactive_widgets()
        self._anim_progress = 0.0
        self._animation_timer.start(30)

    def _animate_step(self):
        self._anim_progress += 0.015
        if self._anim_progress >= 1.0:
            self._anim_progress = 1.0
            self._animation_timer.stop()
            self._is_animating = False
            self._complete_step()
        self.update_view(from_animation=True)

    # ==========================
    # STEP 11: The Final Truth
    # ==========================
    def _render_step_11(self, fluors):
        self._step_label.setText("Step 11: The Final Truth")
        html = """
        <h3 style="color: #58a6ff;">The Final Result</h3>
        <p>This is the final, properly compensated data! Notice how the single positive populations have been mathematically pulled back below the baseline thresholds, snapping them into clean orthogonal lines.</p>
        <p>Because the false positives have been removed, the true Double Positives (in blue) are now clearly visible and separated from the noise. We can now easily draw a clean gate around them.</p>
        <p>You now understand the fundamental physics and mathematics of fluorescence compensation!</p>
        <p style='color: #3fb950; font-weight: bold;'>Masterclass Complete!</p>
        """
        if 10 not in self._completed_steps:
            self._completed_steps.add(10)

        self._explanation.setHtml(html)
        self._ax.set_title("Compensated Sample", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Detector 1", "Detector 2")

        np.random.seed(99)
        self._ax.scatter(
            np.random.normal(100, 30, 200),
            np.random.normal(100, 30, 200),
            color=Colors.FG_SECONDARY,
            alpha=0.3,
            s=10,
        )
        self._ax.scatter(
            np.random.normal(600, 80, 200),
            np.random.normal(100, 30, 200),
            color="#3fb950",
            alpha=0.6,
            s=15,
        )
        self._ax.scatter(
            np.random.normal(100, 30, 200),
            np.random.normal(600, 80, 200),
            color="#3fb950",
            alpha=0.6,
            s=15,
        )
        self._ax.scatter(
            np.random.normal(600, 80, 100),
            np.random.normal(600, 80, 100),
            color="#58a6ff",
            alpha=0.9,
            s=15,
        )

        rect = patches.Rectangle(
            (200, 200),
            800,
            800,
            linewidth=2,
            edgecolor="#58a6ff",
            facecolor="none",
            ls=":",
        )
        self._ax.add_patch(rect)
        self._ax.text(
            250, 900, "Clean Double Positive Gate", color="#58a6ff", fontsize=11
        )

        self._ax.axhline(200, color=Colors.BORDER, ls="--")
        self._ax.axvline(200, color=Colors.BORDER, ls="--")
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    # ==========================
    # EVENT HANDLERS
    # ==========================
    def _complete_step(self):
        if self._current_step not in self._completed_steps:
            self._completed_steps.add(self._current_step)
            if self._current_step < self._max_steps - 1:
                self._btn_next.setEnabled(True)
            self._canvas.draw()

    def _on_html_link_clicked(self, url):
        link = url.toString()
        if self._current_step == 8:
            if link == "step9_correct":
                self._complete_step()
                self.update_view()
            elif link.startswith("step9_wrong"):
                self._ax.text(
                    500,
                    500,
                    "Incorrect! Hint: 0.25 × 800",
                    color="#ff7b72",
                    fontsize=16,
                    ha="center",
                    va="center",
                    bbox=dict(
                        facecolor=Colors.BG_DARKEST, edgecolor="#ff7b72", pad=10.0
                    ),
                )
                self._canvas.draw()

    def _on_canvas_click(self, event):
        if not event.inaxes:
            return
        cs = self._current_step
        if cs == 0:
            if 0 not in self._completed_steps:
                self._drag_state = "filter"
        elif cs == 1:
            if 1 not in self._completed_steps and hasattr(self, "_overlap_x"):
                if abs(event.xdata - self._overlap_x) < 30 and event.ydata < 0.7:
                    self._ax.scatter(
                        [self._overlap_x],
                        [0.5],
                        color="none",
                        s=300,
                        edgecolors="#3fb950",
                        lw=3,
                    )
                    self._complete_step()
                else:
                    self._ax.text(
                        event.xdata,
                        event.ydata,
                        "Not quite! Click inside the gray band.",
                        color="#ff7b72",
                        fontsize=10,
                        ha="center",
                    )
                    self._canvas.draw()
        elif cs == 2:
            if 2 not in self._completed_steps:
                if abs(event.xdata - 800) < 50 and abs(event.ydata - 200) < 50:
                    self._complete_step()
                    self.update_view()
        elif cs == 3:
            if 3 not in self._completed_steps:
                x = self._step4_crosshair.get_xdata()[0]
                y = self._step4_crosshair.get_ydata()[0]
                if abs(event.xdata - x) < 50 and abs(event.ydata - y) < 50:
                    self._drag_state = "crosshair"
        elif cs == 4:
            if 4 not in self._completed_steps:
                if event.xdata > 500 and event.ydata > 180:
                    self._ax.scatter(
                        [event.xdata],
                        [event.ydata],
                        color="none",
                        s=150,
                        edgecolors="#3fb950",
                        lw=2,
                    )
                    self._ax.text(
                        event.xdata + 30,
                        event.ydata,
                        "False Positives!",
                        color="#3fb950",
                        fontweight="bold",
                    )
                    self._complete_step()
        elif cs == 5:
            if 5 not in self._completed_steps:
                if event.xdata > 700:
                    self._complete_step()
                    self.update_view()
        elif cs == 7:
            if 7 not in self._completed_steps:
                if event.xdata > 650 and event.ydata > 650:
                    self._ax.plot(
                        [event.xdata],
                        [event.ydata],
                        marker="+",
                        color="#3fb950",
                        markersize=20,
                        markeredgewidth=2,
                    )
                    self._complete_step()
                else:
                    self._ax.text(
                        event.xdata,
                        event.ydata,
                        "Not quite! Look for the Double Positives (high on both axes).",
                        color="#ff7b72",
                        fontsize=10,
                        ha="center",
                    )
                    self._canvas.draw()

    def _on_canvas_mouse_move(self, event):
        if not event.inaxes:
            return
        cs = self._current_step
        if cs == 0 and self._drag_state == "filter":
            self._filter_center = event.xdata
            self._filter_patch.set_x(self._filter_center - self._filter_width / 2)
            self._canvas.draw()
        elif cs == 3 and self._drag_state == "crosshair":
            self._step4_crosshair.set_data([event.xdata], [event.ydata])
            self._step4_hline.set_ydata([event.ydata, event.ydata])
            self._step4_vline.set_xdata([event.xdata, event.xdata])
            self._canvas.draw()

    def _on_canvas_mouse_release(self, event):
        cs = self._current_step
        if cs == 0 and self._drag_state == "filter":
            self._drag_state = None
            if abs(self._filter_center - self._target_peak_x) < 30:
                self._filter_patch.set_facecolor("#3fb950")
                self._canvas.draw()
                self._complete_step()
        elif cs == 3 and self._drag_state == "crosshair":
            self._drag_state = None
            x = self._step4_crosshair.get_xdata()[0]
            y = self._step4_crosshair.get_ydata()[0]
            if 150 < x < 250 and 150 < y < 250:
                self._step4_crosshair.set_color("#3fb950")
                self._step4_hline.set_color("#3fb950")
                self._step4_vline.set_color("#3fb950")
                self._canvas.draw()
                self._complete_step()
