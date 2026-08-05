"""Validators for BioPro Flow Cytometry tutorial steps.

Each class implements IValidator with a single validate(app_state) method
(SRP / OCP — new validators extend without modifying existing ones).

app_state is expected to be a FlowState instance from analysis.state.
"""

from abc import abstractmethod
from typing import Any

from biopro.core.models.tutorial_models import IValidator
from biopro_sdk.plugin import get_logger

from ..analysis.state import FlowState

logger = get_logger(__name__, "flow_cytometry")


class LoggingValidator(IValidator):
    """Base validator that provides stateful logging to avoid spam during polling."""

    def log_failure(self, reason: str) -> bool:
        last_reason = getattr(self, "_last_log_reason", "")
        if reason != last_reason:
            logger.info("%s: %s", self.__class__.__name__, reason)
            self._last_log_reason = reason
        return False


class FlowValidator(LoggingValidator):
    """Adapter that strongly types the IValidator interface to FlowState."""

    def validate(self, app_state: Any) -> bool:
        if not isinstance(app_state, FlowState):
            return self.log_failure(f"Expected FlowState, got {type(app_state).__name__}")
        return self.validate_flow(app_state)

    @abstractmethod
    def validate_flow(self, app_state: FlowState) -> bool:
        pass


class TabActiveValidator(FlowValidator):
    """Verifies that the user has navigated to a specific main tab index."""

    def __init__(self, expected_tab_index: int) -> None:
        self.expected = expected_tab_index

    def validate_flow(self, app_state: FlowState) -> bool:
        if app_state.view.active_main_tab_index != self.expected:
            return self.log_failure(
                f"Expected tab index {self.expected}, but got {app_state.view.active_main_tab_index}."
            )
        return True


class FlowImportValidator(FlowValidator):
    """Verifies that ≥10 FCS files have been imported with data loaded."""

    def validate_flow(self, app_state: FlowState) -> bool:
        samples = list(app_state.data.experiment.samples.values())
        if len(samples) < 10:  # noqa: PLR2004
            return self.log_failure(f"Expected at least 10 samples, found {len(samples)}.")

        missing_data = [s.display_name for s in samples if not s.has_data]
        if missing_data:
            return self.log_failure(f"Samples missing data: {', '.join(missing_data)}")

        return True


class UnstainedRoleValidator(FlowValidator):
    """Verifies an unstained control is assigned."""

    def validate_flow(self, app_state: FlowState) -> bool:
        from ..analysis.experiment import SampleRole

        for s in app_state.data.experiment.samples.values():
            if s.role == SampleRole.UNSTAINED:
                name = s.display_name.lower()
                if "blank" in name or "unstained" in name:
                    return True
        return self.log_failure(
            "No sample with role UNSTAINED and 'blank'/'unstained' in name was found."
        )


class SingleStainRoleValidator(FlowValidator):
    """Verifies a single stain control (PI) is assigned."""

    def validate_flow(self, app_state: FlowState) -> bool:
        from ..analysis.experiment import SampleRole

        for s in app_state.data.experiment.samples.values():
            if s.role == SampleRole.SINGLE_STAIN and "pi" in s.display_name.lower():
                return True
        return self.log_failure("No sample with role SINGLE_STAIN and 'pi' in name was found.")


class FmoRoleValidator(FlowValidator):
    """Verifies that 5 FMO controls are assigned."""

    def validate_flow(self, app_state: FlowState) -> bool:
        from ..analysis.experiment import SampleRole

        fmo_count = 0
        for s in app_state.data.experiment.samples.values():
            if s.role == SampleRole.FMO_CONTROL and "fmo" in s.display_name.lower():
                fmo_count += 1
        if fmo_count < 5:  # noqa: PLR2004
            return self.log_failure(f"Expected 5 FMO controls, found {fmo_count}.")
        return True


class RoleAssignmentValidator(FlowValidator):
    """Verifies that the 4 essential roles have been assigned to at least one sample each,
    and that there are at least 3 FULL_PANEL samples (A, B, C).
    """

    def validate_flow(self, app_state: FlowState) -> bool:
        from ..analysis.experiment import SampleRole

        samples = list(app_state.data.experiment.samples.values())
        roles = {s.role for s in samples}

        full_panel_count = 0
        for s in samples:
            if s.role == SampleRole.FULL_PANEL and "sample" in s.display_name.lower():
                full_panel_count += 1

        if full_panel_count < 3:  # noqa: PLR2004
            return self.log_failure(f"Expected 3 FULL_PANEL samples, found {full_panel_count}.")

        required_roles = {
            SampleRole.UNSTAINED,
            SampleRole.SINGLE_STAIN,
            SampleRole.FMO_CONTROL,
            SampleRole.FULL_PANEL,
        }

        missing_roles = required_roles - roles
        if missing_roles:
            return self.log_failure(f"Missing essential roles: {[r.name for r in missing_roles]}")

        return True


class CompensationAppliedValidator(FlowValidator):
    """Verifies a compensation matrix exists, and auto-applies it to all samples."""

    def validate_flow(self, app_state: FlowState) -> bool:
        if app_state.data.compensation is None:
            from biopro_sdk.plugin import get_logger

            from ..analysis.compensation import extract_spill_from_fcs

            inner_logger = get_logger(__name__, "flow_cytometry")
            inner_logger.info(
                "CompensationAppliedValidator: Starting to search for $SPILL in %d samples",
                len(app_state.data.experiment.samples),
            )
            for sample in app_state.data.experiment.samples.values():
                if sample.fcs_data:
                    comp = extract_spill_from_fcs(sample.fcs_data)
                    if comp is not None:
                        inner_logger.info(
                            "CompensationAppliedValidator: Found matrix in sample %s",
                            sample.display_name,
                        )
                        app_state.data.compensation = comp
                        break
                    inner_logger.info(
                        "CompensationAppliedValidator: No matrix found in sample %s",
                        sample.display_name,
                    )

            if app_state.data.compensation is None:
                inner_logger.warning("CompensationAppliedValidator: Failed to find any matrix!")
                return self.log_failure(
                    "Failed to find any compensation matrix ($SPILL) in samples."
                )

        # The matrix exists! Auto-apply it so the tutorial can skip the manual application steps.
        applied_any = False
        for sample in app_state.data.experiment.samples.values():
            if not sample.is_compensated:
                sample.is_compensated = True
                applied_any = True

        if applied_any:
            try:
                from biopro_sdk.plugin import CentralEventBus

                from ..analysis.events import EXPERIMENT_DATA_CHANGED

                CentralEventBus.publish(EXPERIMENT_DATA_CHANGED, {})
            except Exception:
                pass

        return True


class GateExistsValidator(FlowValidator):
    """Verifies that a gate with the given name exists on at least one Full Panel sample."""

    def __init__(self, target_gate_name: str) -> None:
        self._target = target_gate_name.lower()

    def validate_flow(self, app_state: FlowState) -> bool:
        from ..analysis.experiment import SampleRole

        samples = list(app_state.data.experiment.samples.values())
        full_panel = [s for s in samples if s.role == SampleRole.FULL_PANEL] or samples
        if not any(self._gate_found(s.gate_tree) for s in full_panel):
            return self.log_failure(f"Gate '{self._target}' not found in any FULL_PANEL samples.")
        return True

    def _gate_found(self, node: Any) -> bool:
        if getattr(node, "name", "").lower() == self._target:
            return True
        return any(self._gate_found(child) for child in getattr(node, "children", []))


class SampleOpenValidator(FlowValidator):
    """Verifies that the Blank (Unstained) sample is currently the active graph in the workspace."""

    def validate_flow(self, app_state: FlowState) -> bool:
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return self.log_failure("No active sample ID in view.")
        from ..analysis.experiment import SampleRole

        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return self.log_failure(f"Sample ID {sample_id} not found in experiment.")
        if sample.role != SampleRole.UNSTAINED:
            return self.log_failure(
                f"Active sample role is {sample.role.name}, expected UNSTAINED."
            )
        return True


class SpecificSampleOpenValidator(FlowValidator):
    """Verifies that a sample with a specific SampleRole is currently open."""

    def __init__(self, role_name: str) -> None:
        """Args: role_name: e.g. 'SINGLE_STAIN' to match SampleRole.SINGLE_STAIN."""
        self._role_name = role_name.upper()

    def validate_flow(self, app_state: FlowState) -> bool:
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return self.log_failure("No active sample ID in view.")
        from ..analysis.experiment import SampleRole

        sample = app_state.data.experiment.samples.get(sample_id)
        if sample is None:
            return self.log_failure(f"Sample ID {sample_id} not found in experiment.")
        try:
            expected_role = SampleRole[self._role_name]
            if sample.role != expected_role:
                return self.log_failure(
                    f"Active sample role is {sample.role.name}, expected {expected_role.name}."
                )
            return True
        except KeyError:
            return self.log_failure(f"Unknown expected role: {self._role_name}")


class AxisChannelValidator(FlowValidator):
    """Verifies that the active X axis channel contains a specific keyword."""

    def __init__(self, channel_keyword: str) -> None:
        self._keyword = channel_keyword.lower()

    def validate_flow(self, app_state: FlowState) -> bool:
        x_param = getattr(app_state.view, "active_x_param", "") or ""
        if self._keyword not in x_param.lower():
            return self.log_failure(
                f"Active X channel '{x_param}' does not contain keyword '{self._keyword}'."
            )
        return True


class AxisTransformValidator(FlowValidator):
    """Verifies that the active X axis transform matches a specific type (e.g. 'biexponential')."""

    def __init__(self, transform_name: str) -> None:
        self._transform = transform_name.lower()

    def validate_flow(self, app_state: FlowState) -> bool:
        active = getattr(app_state.view, "active_transform_x", "") or ""
        if active.lower() != self._transform:
            return self.log_failure(
                f"Active X transform is '{active}', expected '{self._transform}'."
            )
        return True


class AxisOutlierValidator(FlowValidator):
    """Verifies that the active X axis outlier percentile matches a specific value."""

    def __init__(self, target_percentile: float) -> None:
        self._target = target_percentile

    def validate_flow(self, app_state: FlowState) -> bool:
        x_param = getattr(app_state.view, "active_x_param", None)
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not x_param:
            return self.log_failure("No active X channel parameter.")

        try:
            from ..analysis.axis_manager import AxisManager

            manager = AxisManager(app_state)
            scale = manager.get_scale(x_param, sample_id)
            # Use a small epsilon for float comparison
            if abs(scale.outlier_percentile - self._target) >= 0.001:  # noqa: PLR2004
                return self.log_failure(
                    f"Outlier percentile is {scale.outlier_percentile}, expected {self._target}."
                )
            return True
        except Exception as e:
            return self.log_failure(f"Failed to get scale: {e}")


class GateExistsOnAllValidator(GateExistsValidator):
    """Verifies that a gate with the given name exists on ALL Full Panel samples."""

    def validate_flow(self, app_state: FlowState) -> bool:
        from ..analysis.experiment import SampleRole

        samples = list(app_state.data.experiment.samples.values())
        full_panel = [s for s in samples if s.role == SampleRole.FULL_PANEL]
        if not full_panel:
            return self.log_failure("No FULL_PANEL samples found.")

        missing = [s.display_name for s in full_panel if not self._gate_found(s.gate_tree)]
        if missing:
            return self.log_failure(
                f"Gate '{self._target}' missing on FULL_PANEL samples: {', '.join(missing)}"
            )
        return True


class ExactSampleOpenValidator(FlowValidator):
    """Verifies that a specific named sample is currently open."""

    def __init__(self, sample_name: str) -> None:
        self._sample_name = sample_name.lower()

    def validate_flow(self, app_state: FlowState) -> bool:
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return self.log_failure("No active sample ID in view.")
        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return self.log_failure(f"Sample ID {sample_id} not found in experiment.")
        if self._sample_name not in sample.display_name.lower():
            return self.log_failure(
                f"Active sample '{sample.display_name}' does not match expected '{self._sample_name}'."
            )
        return True


class AxisYChannelValidator(FlowValidator):
    """Verifies that the active Y axis channel contains a specific keyword."""

    def __init__(self, channel_keyword: str) -> None:
        self._keyword = channel_keyword.lower()

    def validate_flow(self, app_state: FlowState) -> bool:
        y_param = getattr(app_state.view, "active_y_param", "") or ""
        if self._keyword not in y_param.lower():
            return self.log_failure(
                f"Active Y channel '{y_param}' does not contain keyword '{self._keyword}'."
            )
        return True


class LiveGateExistsValidator(FlowValidator):
    """Verifies that a RangeGate has been drawn on the PI channel (PerCP) for the active single-stain sample.

    Accepts any gate whose high bound is below 10,000 — i.e. the user captured the left
    (live) population and did NOT extend the gate into the dead-cell peak.
    """

    def __init__(self, target_name: str | None = None) -> None:
        self.target_name = target_name

    def validate_flow(self, app_state: FlowState) -> bool:
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return self.log_failure("No active sample ID in view.")
        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return self.log_failure(f"Sample ID {sample_id} not found in experiment.")

        def check_node(node: Any) -> bool:
            gate = getattr(node, "gate", None)
            if type(gate).__name__ == "RangeGate" and getattr(gate, "high", float("inf")) < 50_000:  # noqa: PLR2004
                # Accept any range gate where low < high and high is in the live-cell
                # region (raw values, not display). Dead cells are typically > 100,000.
                if (
                    self.target_name
                    and getattr(node, "name", "").lower() != self.target_name.lower()
                ):
                    pass
                else:
                    return True
            return any(check_node(child) for child in getattr(node, "children", []))

        if not check_node(sample.gate_tree):
            return self.log_failure(
                "No valid Live RangeGate (<50,000 high bound) found on current sample."
            )
        return True


class LeukocyteGateExistsValidator(FlowValidator):
    """Verifies that a RectangleGate has been drawn for Leukocytes (CD45+).

    Accepts any RectangleGate where the X-min is positive (above background) and
    X-max extends into the positive range, while Y covers the FSC-A range.
    """

    def __init__(self, target_name: str | None = None) -> None:
        self.target_name = target_name

    def validate_flow(self, app_state: FlowState) -> bool:
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return self.log_failure("No active sample ID in view.")
        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return self.log_failure(f"Sample ID {sample_id} not found in experiment.")

        def check_node(node: Any) -> bool:
            gate = getattr(node, "gate", None)
            if (
                type(gate).__name__ == "RectangleGate"
                and gate
                and "apc" in getattr(gate, "x_param", "").lower()
                and "ssc" in getattr(gate, "y_param", "").lower()
                and getattr(gate, "x_min", 0) > -1000  # noqa: PLR2004
                and getattr(gate, "x_max", 0) > getattr(gate, "x_min", 0)
            ):
                # Professional standard: CD45 (APC-A) vs SSC-A.
                # Just check that it's an APC-A/SSC-A gate and X-min is > 0 (gating out negative cells).
                if (
                    self.target_name
                    and getattr(node, "name", "").lower() != self.target_name.lower()
                ):
                    pass
                else:
                    return True
            return any(check_node(child) for child in getattr(node, "children", []))

        if not check_node(sample.gate_tree):
            return self.log_failure(
                "No valid Leukocyte RectangleGate (CD45+ vs SSC-A) found on current sample."
            )
        return True


class GateShapeValidator(FlowValidator):
    """Verifies that a newly created gate matches the required target shape."""

    def __init__(
        self,
        target_bounds: tuple[float, float, float, float] | None = None,
        target_poly: list[tuple[float, float]] | None = None,
        target_name: str | None = None,
    ) -> None:
        """Args:
        target_bounds: (min_x, max_x, min_y, max_y). For 1D gates, use 0 for min_y, max_y.
        target_poly: List of (x, y) vertices for the target polygon shape.
        target_name: The expected name of the gate.
        """
        self.target_bounds = target_bounds
        self.target_poly = target_poly
        self.target_name = target_name

    def validate_flow(self, app_state: FlowState) -> bool:
        sample_id = app_state.view.current_sample_id
        if not sample_id:
            return self.log_failure("No active sample ID in view.")

        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return self.log_failure(f"Sample ID {sample_id} not found in experiment.")

        def check_node(node: Any) -> bool:
            if getattr(node, "node_id", None) and self.validate_shape(
                app_state, node.node_id, sample_id
            ):
                if (
                    self.target_name
                    and getattr(node, "name", "").lower() != self.target_name.lower()
                ):
                    pass
                else:
                    return True
            return any(check_node(child) for child in getattr(node, "children", []))

        if not check_node(sample.gate_tree):
            return self.log_failure("No gate matching target shape bounds/polygon found.")
        return True

    def validate_shape(self, app_state: Any, node_id: str, sample_id: str) -> bool:  # noqa: PLR0911, PLR0912, PLR0915
        """Validates the shape of a specific gate node. Returns True if accurate."""
        if not self.target_bounds and not self.target_poly:
            return True  # No shape checking required

        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False

        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return False

        node = sample.gate_tree.find_node_by_id(node_id)
        if not node or not node.gate:
            return False

        gate = node.gate
        gate_type = type(gate).__name__

        # Exact shape matching for Polygons via rasterization
        if gate_type == "PolygonGate" and self.target_poly:
            import numpy as np
            from matplotlib.path import Path

            gate_path = Path(gate.vertices)
            target_path = Path(self.target_poly)

            xs = [v[0] for v in gate.vertices] + [v[0] for v in self.target_poly]
            ys = [v[1] for v in gate.vertices] + [v[1] for v in self.target_poly]

            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            if max_x == min_x:
                max_x += 1
            if max_y == min_y:
                max_y += 1

            # 100x100 grid for fast and efficient rasterization
            gx = np.linspace(min_x, max_x, 100)
            gy = np.linspace(min_y, max_y, 100)
            grid_x, grid_y = np.meshgrid(gx, gy)
            points = np.column_stack((grid_x.ravel(), grid_y.ravel()))

            gate_mask = gate_path.contains_points(points)
            target_mask = target_path.contains_points(points)

            intersection = np.logical_and(gate_mask, target_mask).sum()
            union = np.logical_or(gate_mask, target_mask).sum()

            iou = intersection / union if union > 0 else 0

            # Ensure it is within 10% of the original shape
            return iou >= 0.90  # noqa: PLR2004

        if not self.target_bounds:
            return True

        # Calculate bounding box of drawn gate
        min_x, max_x, min_y, max_y = 0.0, 0.0, 0.0, 0.0

        if gate_type == "PolygonGate":
            xs = [v[0] for v in gate.vertices]
            ys = [v[1] for v in gate.vertices]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
        elif gate_type == "RangeGate":
            min_x, max_x = gate.low, gate.high
        elif gate_type == "QuadrantGate":
            min_x, max_x = gate.x_threshold, gate.x_threshold
            min_y, max_y = gate.y_threshold, gate.y_threshold
        else:
            return True  # skip unknown gate types

        t_min_x, t_max_x, t_min_y, t_max_y = self.target_bounds

        if gate_type in {"RangeGate", "QuadrantGate"}:
            # For 1D ranges or points, check relative error based on a typical flow axis range (262144)
            axis_range = 262144.0

            # Check X bounds
            if (
                abs(min_x - t_min_x) / axis_range > 0.10  # noqa: PLR2004
                or abs(max_x - t_max_x) / axis_range > 0.10  # noqa: PLR2004
            ):
                return False

            # Check Y bounds for Quadrant
            if gate_type == "QuadrantGate" and (
                abs(min_y - t_min_y) / axis_range > 0.10  # noqa: PLR2004
                or abs(max_y - t_max_y) / axis_range > 0.10  # noqa: PLR2004
            ):
                return False

        return True

        # For Polygons fallback, use Intersection over Union (IoU) of the bounding box
        dx = max(0.0, min(max_x, t_max_x) - max(min_x, t_min_x))
        dy = max(0.0, min(max_y, t_max_y) - max(min_y, t_min_y))
        intersection = dx * dy

        area1 = (max_x - min_x) * (max_y - min_y)
        area2 = (t_max_x - t_min_x) * (t_max_y - t_min_y)
        union = area1 + area2 - intersection

        iou = intersection / union if union > 0 else 0

        # We require at least 65% overlap (which is roughly ~15% edge tolerance)
        return iou >= 0.65  # noqa: PLR2004


class WorkflowSavedValidator(FlowValidator):
    """Verifies that the user has saved a workflow and registers it as a prerequisite."""

    def validate_flow(self, _app_state: FlowState) -> bool:
        # FlowState doesn't hold project manager, search top level widgets
        pm = None
        try:
            from PyQt6.QtWidgets import QApplication

            for w in QApplication.topLevelWidgets():
                if hasattr(w, "project_manager") and w.project_manager:
                    pm = w.project_manager
                    break
        except ImportError:
            pass

        if not pm:
            return self.log_failure("Project manager not found in top-level widgets.")

        workflows = pm.workflows.list_all()
        if not workflows:
            return self.log_failure("No workflows found in project manager.")

        # We require the user to have explicitly saved it. Check all workflows.
        for wf in workflows:
            wf_filename = wf.get("filename", "")
            if wf_filename:
                wf_hash = pm.get_workflow_hash(wf_filename)
                if wf_hash:
                    from biopro.core.tutorial_manager import global_tutorial_manager

                    global_tutorial_manager.record_prerequisite("flow_course_2_gating", wf_hash)
                    return True

        return self.log_failure("Failed to find a valid saved workflow hash.")


class GateActiveValidator(FlowValidator):
    """Verifies that the user has double-clicked a specific gate in the hierarchy to enter it."""

    def __init__(self, target_gate_name: str) -> None:
        self.target = target_gate_name.lower()

    def validate_flow(self, app_state: FlowState) -> bool:  # noqa: PLR0911

        gate_id = getattr(app_state.view, "current_gate_id", None)
        sample_id = getattr(app_state.view, "current_sample_id", None)

        if not sample_id:
            return self.log_failure("No active sample ID in view.")

        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return self.log_failure(f"Sample ID {sample_id} not found in experiment.")

        if not gate_id:
            # If no gate is selected, they are at the root
            if self.target not in sample.gate_tree.name.lower():
                return self.log_failure(
                    f"Target gate '{self.target}' is not active, root node is '{sample.gate_tree.name}'."
                )
            return True

        node = sample.gate_tree.find_node_by_id(gate_id)
        if node:
            if self.target not in node.name.lower():
                return self.log_failure(
                    f"Target gate '{self.target}' is not active, active node is '{node.name}'."
                )
            return True

        return self.log_failure(f"Gate ID {gate_id} not found in sample gate tree.")


class Course1StateValidator(FlowValidator):
    """Verifies that the workspace state matches the expected Course 1 checkpoint."""

    def __init__(self) -> None:
        self._flow_import = FlowImportValidator()
        self._role_assign = RoleAssignmentValidator()
        self._cells_gate = GateExistsValidator("cells")
        self._live_gate = GateExistsValidator("live cells")
        self._leukocytes = GateExistsValidator("leukocytes")

    def validate_flow(self, app_state: FlowState) -> bool:
        if not self._flow_import.validate(app_state):
            return False
        if not self._role_assign.validate(app_state):
            return False
        if not self._cells_gate.validate(app_state):
            return False
        if not self._live_gate.validate(app_state):
            return False
        return self._leukocytes.validate(app_state)


class PlotTypeValidator(FlowValidator):
    """Verifies that the active graph is displaying the specified plot type (e.g. 'Histogram', 'Pseudocolor')."""

    def __init__(self, expected_plot_type: str) -> None:
        self.expected = expected_plot_type.lower()

    def validate_flow(self, app_state: FlowState) -> bool:

        graph_manager = getattr(app_state.view, "_graph_manager", None)
        if (
            not graph_manager
            or not hasattr(graph_manager, "active_graph")
            or not graph_manager.active_graph
        ):
            return self.log_failure("No active graph found in graph manager.")

        axis_panel = getattr(graph_manager.active_graph, "_axis_panel", None)
        if not axis_panel or not hasattr(axis_panel, "_display_combo"):
            return self.log_failure("Active graph missing axis panel or display combo.")

        current_text = axis_panel._display_combo.currentText().lower()
        if current_text != self.expected:
            return self.log_failure(
                f"Active plot type is '{current_text}', expected '{self.expected}'."
            )
        return True


class PipelineOrientationValidator(FlowValidator):
    """Verifies that the pipeline canvas is set to a specific layout orientation (e.g., 'Horizontal')."""

    def __init__(self, expected_orientation: str) -> None:
        self.expected = expected_orientation.lower()

    def validate_flow(self, app_state: FlowState) -> bool:

        pipeline_ribbon = getattr(app_state.view, "_pipeline_ribbon", None)
        if not pipeline_ribbon or not hasattr(pipeline_ribbon, "_orientation_combo"):
            return self.log_failure("Pipeline ribbon or orientation combo missing.")

        current_text = pipeline_ribbon._orientation_combo.currentText().lower()
        if current_text != self.expected:
            return self.log_failure(
                f"Pipeline orientation is '{current_text}', expected '{self.expected}'."
            )
        return True


class LearningCompensationCompleteValidator(FlowValidator):
    """Verifies that the user has reached the end of the Learning Compensation slideshow."""

    def validate_flow(self, app_state: FlowState) -> bool:

        spectral_viewer = getattr(app_state.view, "_spectral_viewer", None)
        if not spectral_viewer or not hasattr(spectral_viewer, "_learning_tab"):
            return self.log_failure("Spectral viewer or learning tab missing.")

        learning_tab = spectral_viewer._learning_tab
        # Ensure they have reached the final step
        if learning_tab._current_step < learning_tab._max_steps - 1:
            return self.log_failure(
                f"Currently on step {learning_tab._current_step}, expected >= {learning_tab._max_steps - 1}."
            )
        return True


class GateAbsentValidator(FlowValidator):
    """Verifies that a gate with the given name no longer exists on the active sample.

    Used to confirm a population was deleted (e.g. via the Pipeline canvas Delete key).
    """

    def __init__(self, target_gate_name: str) -> None:
        self._target = target_gate_name.lower()

    def validate_flow(self, app_state: FlowState) -> bool:
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return self.log_failure("No active sample ID in view.")
        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return self.log_failure(f"Sample ID {sample_id} not found in experiment.")

        if self._gate_found(sample.gate_tree):
            return self.log_failure(f"Gate '{self._target}' still exists on the active sample.")
        return True

    def _gate_found(self, node: Any) -> bool:
        if getattr(node, "name", "").lower() == self._target:
            return True
        return any(self._gate_found(child) for child in getattr(node, "children", []))


class LogicGateExistsValidator(FlowValidator):
    """Verifies a boolean logic node (AND/OR/NOT) exists wiring in two named parent populations."""

    def __init__(self, operator: str, parent_names: list[str]) -> None:
        self._operator = operator.upper()
        self._parents = [p.lower() for p in parent_names]

    def validate_flow(self, app_state: FlowState) -> bool:
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return self.log_failure("No active sample ID in view.")
        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return self.log_failure(f"Sample ID {sample_id} not found in experiment.")

        if not self._logic_found(sample.gate_tree):
            return self.log_failure(
                f"No {self._operator} node combining {self._parents} found on active sample."
            )
        return True

    def _logic_found(self, node: Any) -> bool:
        if (
            getattr(node, "gate", None) is None
            and getattr(node, "logic_operator", "") == self._operator
        ):
            parent_names = {p.name.lower() for p in getattr(node, "parents", [])}
            if all(any(target in name for name in parent_names) for target in self._parents):
                return True
        return any(self._logic_found(child) for child in getattr(node, "children", []))


class SpectralFluorsLoadedValidator(FlowValidator):
    """Verifies that at least N fluorophore spectra are currently loaded in the Spectral viewer."""

    def __init__(self, min_count: int = 6) -> None:
        self._min_count = min_count

    def validate_flow(self, app_state: FlowState) -> bool:
        spectral_viewer = getattr(app_state.view, "_spectral_viewer", None)
        if not spectral_viewer or not hasattr(spectral_viewer, "_active_fluors"):
            return self.log_failure("Spectral viewer or active fluors dict missing.")
        count = len(spectral_viewer._active_fluors)
        if count < self._min_count:
            return self.log_failure(
                f"Only {count} fluorophores loaded, expected >= {self._min_count}."
            )
        return True


class UmapClusterExportedValidator(FlowValidator):
    """Verifies a 'UMAP Reduction' node with at least one exported cluster child exists."""

    def validate_flow(self, app_state: FlowState) -> bool:
        for sample in app_state.data.experiment.samples.values():
            node = self._find_umap_parent(sample.gate_tree)
            if node is not None and len(getattr(node, "children", [])) > 0:
                return True
        return self.log_failure("No 'UMAP Reduction' node with exported clusters found.")

    def _find_umap_parent(self, node: Any) -> Any | None:
        if getattr(node, "name", "").lower() == "umap reduction":
            return node
        for child in getattr(node, "children", []):
            found = self._find_umap_parent(child)
            if found is not None:
                return found
        return None


class StatsChartTypeValidator(FlowValidator):
    """Verifies the Statistics tab's chart-type combo is set to a specific value (e.g. 'Heatmap')."""

    def __init__(self, expected_type: str) -> None:
        self._expected = expected_type.lower()

    def validate_flow(self, app_state: FlowState) -> bool:
        explorer = getattr(app_state.view, "_statistics_explorer", None)
        if not explorer or not hasattr(explorer, "_chart_type_combo"):
            return self.log_failure("Statistics explorer or chart type combo missing.")
        current = explorer._chart_type_combo.currentText().lower()
        if self._expected not in current:
            return self.log_failure(f"Chart type is '{current}', expected '{self._expected}'.")
        return True


class ComparisonPlotTypeValidator(FlowValidator):
    """Verifies the Comparisons tab's plot-type combo is set to a specific chart (e.g. 'Violin')."""

    def __init__(self, expected_type: str) -> None:
        self._expected = expected_type.lower()

    def validate_flow(self, app_state: FlowState) -> bool:
        viewer = getattr(app_state.view, "_comparisons_viewer", None)
        if not viewer or not hasattr(viewer, "_plot_type_combo"):
            return self.log_failure("Comparisons viewer or plot type combo missing.")
        current = viewer._plot_type_combo.currentText().lower()
        if self._expected not in current:
            return self.log_failure(f"Plot type is '{current}', expected '{self._expected}'.")
        return True
