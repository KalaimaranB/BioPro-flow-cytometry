import os
import re

file_path = "/Users/kalaimaranbalasothy/GitHub Projects/BioPro-flow-cytometry/ui/graph/gate_drawing_fsm.py"
with open(file_path, "r") as f:
    content = f.read()

# Replace _draw_polygon_progress
old_draw = """    def _draw_polygon_progress(self, current_mouse=None):
        self._clear_polygon_progress(blit=False)
        ax = self.canvas._ax

        if not self._polygon_vertices:
            return

        # Draw existing edges
        pts = list(self._polygon_vertices)
        if current_mouse:
            pts.append(current_mouse)

        if len(pts) > 1:
            line = Line2D(
                [p[0] for p in pts], [p[1] for p in pts], color="#FF3333", linestyle="--", linewidth=2.0, alpha=0.8, zorder=100, animated=True
            )
            
            cb = self.canvas._fig.stale_callback
            self.canvas._fig.stale_callback = None
            try:
                ax.add_line(line)
                self._polygon_artists.append(line)
                
                # Draw vertices
                for x, y in self._polygon_vertices:
                    dot = ax.plot(x, y, "ro", markersize=5, alpha=0.8, zorder=101, animated=True)[0]
                    self._polygon_artists.append(dot)
            finally:
                self.canvas._fig.stale_callback = cb
                self.canvas._fig.stale = False
                ax.stale = False

        if getattr(self.canvas, "_use_cache", False) and getattr(self.canvas, "_canvas_bitmap_cache", None) is not None:
            self.canvas._fig.canvas.restore_region(self.canvas._canvas_bitmap_cache)
            for artist in self._polygon_artists:
                ax.draw_artist(artist)
            self.canvas._fig.canvas.blit(ax.bbox)
            self.canvas._fig.canvas.flush_events()
        else:
            self.canvas.draw_idle()"""

new_draw = """    def _draw_polygon_progress(self, current_mouse=None):
        ax = self.canvas._ax

        if not self._polygon_vertices:
            return

        pts = list(self._polygon_vertices)
        if current_mouse:
            pts.append(current_mouse)
            
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        
        vx = [p[0] for p in self._polygon_vertices]
        vy = [p[1] for p in self._polygon_vertices]

        cb = self.canvas._fig.stale_callback
        self.canvas._fig.stale_callback = None
        try:
            if not self._polygon_artists:
                # Create artists once
                line = Line2D([], [], color="#FF3333", linestyle="--", linewidth=2.0, alpha=0.8, zorder=100, animated=True)
                dots = Line2D([], [], color="#FF3333", marker="o", linestyle="None", markersize=5, alpha=0.8, zorder=101, animated=True)
                ax.add_line(line)
                ax.add_line(dots)
                self._polygon_artists = [line, dots]
            
            line, dots = self._polygon_artists
            
            if len(pts) > 1:
                line.set_data(xs, ys)
                line.set_visible(True)
            else:
                line.set_visible(False)
                
            if len(self._polygon_vertices) > 0:
                dots.set_data(vx, vy)
                dots.set_visible(True)
            else:
                dots.set_visible(False)
        finally:
            self.canvas._fig.stale_callback = cb
            self.canvas._fig.stale = False
            ax.stale = False

        if getattr(self.canvas, "_use_cache", False) and getattr(self.canvas, "_canvas_bitmap_cache", None) is not None:
            self.canvas._fig.canvas.restore_region(self.canvas._canvas_bitmap_cache)
            for artist in self._polygon_artists:
                if artist.get_visible():
                    ax.draw_artist(artist)
            self.canvas._fig.canvas.blit(ax.bbox)
            self.canvas._fig.canvas.flush_events()
        else:
            self.canvas.draw_idle()"""

content = content.replace(old_draw, new_draw)

with open(file_path, "w") as f:
    f.write(content)
print("Done updating _draw_polygon_progress")
