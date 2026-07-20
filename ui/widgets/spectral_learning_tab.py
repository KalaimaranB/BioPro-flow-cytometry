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
)


class SpectralLearningTab(QWidget):
    """Educational tab for teaching compensation interactively."""

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self._viewer = viewer  # Reference to the main viewer to get active fluors
        self._current_step = 0
        self._max_steps = 8

        self._setup_ui()
        self._apply_theme_styles()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # Header with step indicator and buttons
        header = QHBoxLayout()
        self._step_label = BioCaptionLabel("Step 1: Unstained Control")
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

        # Left side: Explanation text
        self._explanation = QTextBrowser()
        self._explanation.setMinimumWidth(350)
        self._explanation.setMaximumWidth(450)
        content.addWidget(self._explanation)

        self._figure = Figure(facecolor=Colors.BG_DARK)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._ax = self._figure.add_subplot(111)
        self._style_axes()

        self._canvas_wrapper = QWidget()
        canvas_layout = QVBoxLayout(self._canvas_wrapper)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.addWidget(self._canvas)

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
        self._ax.set_xlabel(
            f"{x_label} Fluorescence Intensity (Brightness)",
            color=Colors.FG_SECONDARY,
            fontsize=10,
        )
        self._ax.set_ylabel(
            f"{y_label} Fluorescence Intensity (Brightness)",
            color=Colors.FG_SECONDARY,
            fontsize=10,
        )

    def update_view(self):
        fluors = self._viewer._active_fluors

        self._btn_prev.setEnabled(self._current_step > 0)
        self._btn_next.setEnabled(self._current_step < self._max_steps - 1)

        self._ax.clear()
        self._style_axes()

        if not fluors:
            self._step_label.setText("Waiting for Selection...")
            self._explanation.setHtml(
                "<h3>No Colors Selected</h3><p>Please go back to the <b>Spectral Analysis</b> tab and search or double-click to add at least one fluorophore.</p>"
            )
            self._ax.text(
                0.5,
                0.5,
                "Add fluorophores in the Analysis Tab to begin",
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
        ]

        if self._current_step in [2, 3, 4, 5, 6, 7]:
            step_funcs[self._current_step](fluors)
        else:
            step_funcs[self._current_step]()

        self._figure.tight_layout(pad=1.0)
        self._canvas.draw()

    def _render_step_1(self):
        self._step_label.setText("Step 1: The Basics (What is a Detector?)")

        html = """
        <h3 style="color: #58a6ff;">Understanding the Axes</h3>
        <p>A flow cytometer uses detectors to measure how bright a cell is glowing.</p>
        <p>In the graphs on the right, the <b>X-axis</b> represents how bright the cell glows in Detector 1. The <b>Y-axis</b> represents how bright it glows in Detector 2.</p>
        <p>Each dot is a single cell.</p>
        """
        self._explanation.setHtml(html)
        self._ax.set_title("Understanding Brightness", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Detector 1", "Detector 2")

        self._ax.scatter(
            [200], [200], color=Colors.FG_SECONDARY, s=50, label="Dim Cell"
        )
        self._ax.scatter(
            [800], [200], color="#58a6ff", s=50, label="Bright in Detector 1"
        )
        self._ax.scatter(
            [200], [800], color="#d2a8ff", s=50, label="Bright in Detector 2"
        )

        self._ax.annotate(
            "Brighter →",
            xy=(500, 150),
            xytext=(300, 150),
            arrowprops=dict(arrowstyle="->", color=Colors.FG_PRIMARY),
            color=Colors.FG_PRIMARY,
        )
        self._ax.annotate(
            "Brighter ↑",
            xy=(150, 500),
            xytext=(150, 300),
            arrowprops=dict(arrowstyle="->", color=Colors.FG_PRIMARY),
            color=Colors.FG_PRIMARY,
            rotation=90,
        )

        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)
        self._ax.legend(
            facecolor=Colors.BG_DARKEST,
            edgecolor=Colors.BORDER,
            labelcolor=Colors.FG_PRIMARY,
        )

    def _render_step_2(self):
        self._step_label.setText("Step 2: Unstained Control (Finding Zero)")

        html = """
        <h3 style="color: #58a6ff;">Finding "Zero"</h3>
        <p>Cells are naturally slightly fluorescent (called <b>autofluorescence</b>). If we don't measure this baseline first, our math will be wrong.</p>
        <p>An <b>Unstained Control</b> is a tube of cells with NO dye added. We run this to see the natural glow.</p>
        <br>
        <p><i>The dashed lines represent the <b>Thresholds</b> (Gates). Anything below the line is considered "Negative". Anything above is considered "Positive".</i></p>
        <p>Notice how we place the gate just above the natural glow? We set it so ~99.9% of unstained cells are Negative. A few natural outliers might still cross the line.</p>
        """
        self._explanation.setHtml(html)
        self._ax.set_title(
            "Unstained Cells (Autofluorescence)", color=Colors.FG_PRIMARY, pad=15
        )
        self._set_axes_labels("Detector 1", "Detector 2")

        np.random.seed(42)
        x = np.random.normal(100, 30, 500)
        y = np.random.normal(100, 30, 500)
        self._ax.scatter(x, y, color=Colors.FG_SECONDARY, alpha=0.5, s=10)

        self._ax.axhline(200, color=Colors.BORDER, ls="--")
        self._ax.axvline(200, color=Colors.BORDER, ls="--")
        self._ax.text(800, 100, "Negative", color=Colors.FG_SECONDARY)
        self._ax.text(100, 800, "Negative", color=Colors.FG_SECONDARY)

        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    def _render_step_3(self, fluors):
        self._step_label.setText("Step 3: The Ideal Dye vs Reality (Leakage)")
        fluors_list = list(fluors.keys())
        first_fluor = fluors_list[0].upper()
        color = fluors[fluors_list[0]].get("color", "#aaaaaa")

        html = f"""
        <h3 style="color: {color};">The Reality of Dyes</h3>
        <p>We now run a <b>Single Stain Control</b>—a tube with ONLY the {first_fluor} dye.</p>
        <p><b>The Ideal:</b> We want {first_fluor} to ONLY light up Detector 1. The white dots stay <i>below</i> the horizontal threshold, meaning they are properly "Negative" for Detector 2.</p>
        <p><b>The Reality:</b> Dyes aren't perfect. Their light spills over into other detectors. The real <span style="color: {color}; font-weight: bold;">colored</span> cells slant diagonally upward and <i>cross the horizontal threshold</i>. Detector 2 is being tricked into thinking these cells have a second dye on them! This is a <b>False Positive</b>.</p>
        """
        self._explanation.setHtml(html)
        self._ax.set_title("Ideal vs Real Spillover", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels(f"Primary Detector ({first_fluor})", "Secondary Detector")

        np.random.seed(42)
        # Background cells
        x0 = np.random.normal(100, 30, 200)
        y0 = np.random.normal(100, 30, 200)
        self._ax.scatter(x0, y0, color=Colors.FG_SECONDARY, alpha=0.3, s=10)

        # Ideal cells
        x_ideal = np.random.normal(700, 80, 200)
        y_ideal = np.random.normal(100, 20, 200)
        self._ax.scatter(
            x_ideal,
            y_ideal,
            color="white",
            alpha=0.3,
            s=10,
            label="What we WANT (No Spillover)",
        )

        # Real cells
        y_real = x_ideal * 0.25 + np.random.normal(0, 20, 200)
        self._ax.scatter(
            x_ideal,
            y_real,
            color=color,
            alpha=0.7,
            s=15,
            label="What we GET (Spillover)",
        )

        self._ax.axhline(200, color=Colors.BORDER, ls="--")
        self._ax.axvline(200, color=Colors.BORDER, ls="--")

        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)
        self._ax.legend(
            facecolor=Colors.BG_DARKEST,
            edgecolor=Colors.BORDER,
            labelcolor=Colors.FG_PRIMARY,
        )

    def _render_step_4(self, fluors):
        self._step_label.setText("Step 4: Calculating Spillover (The Math)")
        fluors_list = list(fluors.keys())
        first_fluor = fluors_list[0].upper()
        color = fluors[fluors_list[0]].get("color", "#aaaaaa")

        html = f"""
        <h3 style="color: #3fb950;">Doing the Math</h3>
        <p>How do we fix the leakage from Step 3? We calculate a ratio.</p>
        <p>We look at the center of the slanted population. Let's say its brightness is <b>800</b> in the Primary Detector, but it accidentally measures <b>200</b> in the Secondary Detector.</p>
        <p><i>(Note: Brightness is measured in Arbitrary Units or AU)</i></p>
        <p><b>Math:</b> <code>200 AU / 800 AU = 0.25 (or 25%)</code></p>
        <p>This tells the machine: <i>"For every 100 AU of {first_fluor} I see, exactly 25 AU will accidentally leak into Detector 2."</i></p>
        """
        self._explanation.setHtml(html)
        self._ax.set_title("Calculating the Ratio", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels(f"Primary Detector ({first_fluor})", "Secondary Detector")

        np.random.seed(42)
        x_ideal = np.random.normal(800, 80, 200)
        y_real = x_ideal * 0.25 + np.random.normal(0, 20, 200)
        self._ax.scatter(x_ideal, y_real, color=color, alpha=0.4, s=15)

        # Highlight center
        self._ax.scatter(
            [800], [200], color="white", s=100, edgecolor="#3fb950", lw=2, zorder=5
        )

        # Draw lines to axes
        self._ax.plot([800, 800], [0, 200], color="#3fb950", ls=":")
        self._ax.plot([0, 800], [200, 200], color="#3fb950", ls=":")

        self._ax.text(820, 50, "Primary: 800", color="#3fb950", fontsize=11)
        self._ax.text(50, 220, "Leaked: 200", color="#3fb950", fontsize=11)

        # Big text for ratio
        self._ax.text(
            300,
            600,
            "200 / 800 = 25%",
            color="#3fb950",
            fontsize=16,
            fontweight="bold",
            bbox=dict(facecolor=Colors.BG_DARKEST, edgecolor="#3fb950", pad=10.0),
        )

        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    def _render_step_5(self, fluors):
        self._step_label.setText("Step 5: The Compensation Matrix")

        display_names = [
            fluors[k].get("display_label", k.upper()) for k in list(fluors.keys())[:6]
        ]
        num_fluors = len(display_names)
        first_fluor = display_names[0]

        html = f"""
        <h3 style="color: #d2a8ff;">The Spillover Grid</h3>
        <p>The machine repeats Step 4 for <b>every single color</b> in your panel to build the <b>Compensation Matrix</b>.</p>
        <p><i>Notice the <span style="background:#3fb950; color:#161b22; padding: 2px;">25.0%</span> we just calculated for {first_fluor}!</i></p>
        <br>
        <div style="border-left: 3px solid #d29922; padding-left: 10px; margin-top: 10px; margin-bottom: 10px;">
        <p style="color: #d29922; margin-top: 0; font-weight: bold;">⚠️ The Golden Rule of Panel Design</p>
        <p style="margin-bottom: 10px;">If two curves overlap heavily, the math in this matrix will still work out perfectly to center the populations. <b>BUT</b>, heavy overlap carries noise over during the subtraction, causing "Spreading Error" that makes your negative populations widen into a smear, destroying your ability to detect dim cells!</p>
        <p style="margin-bottom: 0;"><i>Exception:</i> It is perfectly fine to put heavily overlapping dyes on <b>mutually exclusive markers</b> (e.g., CD4 and CD8 on T-cells), because a single cell will never have both dyes at the same time!</p>
        </div>
        <br>
        """

        # Build HTML table for the matrix
        html += f"""<table style="width:100%; border-collapse: collapse; text-align: center; color: {Colors.FG_PRIMARY}; font-size: 11px;">"""
        html += f"<tr><th style='border-bottom: 1px solid {Colors.BORDER}; padding: 4px;'></th>"
        for name in display_names:
            html += f"<th style='border-bottom: 1px solid {Colors.BORDER}; padding: 4px;'>{name[:4]} Det</th>"
        html += "</tr>"

        np.random.seed(len(fluors))
        for i, row_name in enumerate(display_names):
            html += f"<tr><td style='border-right: 1px solid {Colors.BORDER}; padding: 4px; font-weight: bold;'>{row_name[:6]}</td>"
            for j in range(num_fluors):
                if i == j:
                    val = "100.0"
                    color = "#58a6ff"
                    bg = "transparent"
                elif i == 0 and j == 1:
                    val = "25.0"
                    color = Colors.BG_DARK
                    bg = "#3fb950"
                else:
                    val = f"{np.random.uniform(0, 25):.1f}"
                    color = Colors.FG_PRIMARY if float(val) < 5 else "#d29922"
                    bg = "transparent"
                html += f"<td style='padding: 4px; color: {color}; background-color: {bg}; font-weight: bold;'>{val}%</td>"
            html += "</tr>"

        html += "</table>"
        self._explanation.setHtml(html)

        self._ax.set_title("Emission Curve Overlap", color=Colors.FG_PRIMARY, pad=15)
        self._ax.set_xlabel("Wavelength (nm)", color=Colors.FG_SECONDARY, fontsize=10)
        self._ax.set_ylabel(
            "Normalised Intensity", color=Colors.FG_SECONDARY, fontsize=10
        )

        for name, data in fluors.items():
            if "em_data" in data:
                color = data.get("color", "#aaaaaa")
                arr = np.array(data["em_data"], dtype=float)
                x, y = arr[:, 0], arr[:, 1]
                peak = np.max(y)
                if peak > 0:
                    y = y / peak
                disp_name = data.get("display_label", name.upper())
                self._ax.plot(x, y, color=color, lw=2, alpha=0.8, label=disp_name)
                self._ax.fill_between(x, y, alpha=0.15, color=color)

        self._ax.legend(
            facecolor=Colors.BG_DARKEST,
            edgecolor=Colors.BORDER,
            labelcolor=Colors.FG_PRIMARY,
            loc="upper right",
        )
        self._ax.set_xlim(350, 800)
        self._ax.set_ylim(0, 1.1)

    def _render_step_6(self, fluors):
        self._step_label.setText("Step 6: The Mixed Soup (Before)")

        html = """
        <h3 style="color: #d29922;">The Problem in Real Samples</h3>
        <p>Now we run your actual experiment with all colors mixed together.</p>
        <p>We are looking for a <b>Double Positive</b> cell—a cell that has BOTH dyes physically attached to it.</p>
        <p>But because the single dyes are leaking (slanting upward), the populations smear together. It's almost impossible to draw a clear box around the true Double Positive cells!</p>
        """
        self._explanation.setHtml(html)

        self._ax.set_title("Uncompensated Sample", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Detector 1", "Detector 2")

        np.random.seed(99)
        # Background
        self._ax.scatter(
            np.random.normal(100, 30, 200),
            np.random.normal(100, 30, 200),
            color=Colors.FG_SECONDARY,
            alpha=0.3,
            s=10,
        )

        # Single Pos 1 (smeared)
        x1 = np.random.normal(600, 80, 200)
        y1 = x1 * 0.4 + np.random.normal(0, 30, 200)
        self._ax.scatter(
            x1, y1, color="#d29922", alpha=0.5, s=15, label="Single Pos 1 (Leaking)"
        )

        # Single Pos 2 (smeared)
        y2 = np.random.normal(600, 80, 200)
        x2 = y2 * 0.4 + np.random.normal(0, 30, 200)
        self._ax.scatter(
            x2, y2, color="#d29922", alpha=0.5, s=15, label="Single Pos 2 (Leaking)"
        )

        # Double positive (mixed in)
        xdp = np.random.normal(750, 80, 100)
        ydp = np.random.normal(750, 80, 100)
        self._ax.scatter(
            xdp, ydp, color="#58a6ff", alpha=0.8, s=15, label="True Double Positive"
        )

        self._ax.axhline(200, color=Colors.BORDER, ls="--")
        self._ax.axvline(200, color=Colors.BORDER, ls="--")

        self._ax.legend(
            facecolor=Colors.BG_DARKEST,
            edgecolor=Colors.BORDER,
            labelcolor=Colors.FG_PRIMARY,
        )
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    def _render_step_7(self, fluors):
        self._step_label.setText("Step 7: Subtracting the Matrix")

        html = """
        <h3 style="color: #3fb950;">Applying the Math</h3>
        <p>Let's look at one single cell from the leaked population.</p>
        <p>This cell has a brightness of <b>800 AU</b> in Detector 1, and <b>300 AU</b> in Detector 2.</p>
        <p>The Matrix tells the machine: <i>"Detector 1 leaks 25% into Detector 2."</i></p>
        <p><b>Step 1:</b> Calculate the leakage. <code>25% of 800 AU = 200 AU</code>.</p>
        <p><b>Step 2:</b> Subtract the leakage from Detector 2. <code>300 AU - 200 AU = 100 AU</code>.</p>
        <p>The true Detector 2 signal is 100 AU. The machine literally moves the dot down to 100 on the Y-axis!</p>
        """
        self._explanation.setHtml(html)

        self._ax.set_title(
            "Subtracting Leakage for One Cell", color=Colors.FG_PRIMARY, pad=15
        )
        self._set_axes_labels("Detector 1", "Detector 2")

        # The single cell before
        self._ax.scatter(
            [800],
            [300],
            color="#d29922",
            s=100,
            edgecolor="white",
            zorder=5,
            label="Before (False Positive)",
        )

        # The single cell after
        self._ax.scatter(
            [800],
            [100],
            color="#3fb950",
            s=100,
            edgecolor="white",
            zorder=5,
            label="After (True Negative)",
        )

        # Arrow pointing down
        self._ax.annotate(
            "Subtract 200 AU Leakage",
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

        self._ax.legend(
            facecolor=Colors.BG_DARKEST,
            edgecolor=Colors.BORDER,
            labelcolor=Colors.FG_PRIMARY,
        )
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)

    def _render_step_8(self, fluors):
        self._step_label.setText("Step 8: Why We Care (The Double Positive)")

        html = """
        <h3 style="color: #58a6ff;">The Final Result</h3>
        <p>The machine applies that subtraction to <b>every cell</b> simultaneously for all colors.</p>
        <p>The smear vanishes. The single positive populations are pulled back <i>below</i> the threshold, snapping into perfect rectangles.</p>
        <p><b>Why do we care?</b> Double Positive cells often represent critical biological states (e.g., a T-cell that is both activated AND producing a cytokine). Without compensation, false positives smear into this zone, ruining your biological conclusions!</p>
        """
        self._explanation.setHtml(html)

        self._ax.set_title("Compensated Sample", color=Colors.FG_PRIMARY, pad=15)
        self._set_axes_labels("Detector 1", "Detector 2")

        np.random.seed(99)
        # Background
        self._ax.scatter(
            np.random.normal(100, 30, 200),
            np.random.normal(100, 30, 200),
            color=Colors.FG_SECONDARY,
            alpha=0.3,
            s=10,
        )

        # Single Pos 1 (corrected)
        x1 = np.random.normal(600, 80, 200)
        y1 = np.random.normal(100, 30, 200)
        self._ax.scatter(
            x1, y1, color="#3fb950", alpha=0.6, s=15, label="Compensated Pos 1"
        )

        # Single Pos 2 (corrected)
        y2 = np.random.normal(600, 80, 200)
        x2 = np.random.normal(100, 30, 200)
        self._ax.scatter(
            x2, y2, color="#3fb950", alpha=0.6, s=15, label="Compensated Pos 2"
        )

        # Double positive (isolated)
        xdp = np.random.normal(600, 80, 100)
        ydp = np.random.normal(600, 80, 100)
        self._ax.scatter(
            xdp, ydp, color="#58a6ff", alpha=0.9, s=15, label="True Double Positive"
        )

        # Draw gates to show how easy it is now
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

        self._ax.legend(
            facecolor=Colors.BG_DARKEST,
            edgecolor=Colors.BORDER,
            labelcolor=Colors.FG_PRIMARY,
            loc="lower left",
        )
        self._ax.set_xlim(0, 1000)
        self._ax.set_ylim(0, 1000)
