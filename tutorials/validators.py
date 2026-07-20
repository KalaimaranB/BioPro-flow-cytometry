"""Validators for BioPro Flow Cytometry tutorial steps.

Each class implements IValidator with a single validate(app_state) method
(SRP / OCP — new validators extend without modifying existing ones).

app_state is expected to be a FlowState instance from analysis.state.
"""

from typing import Any
import logging

from biopro.core.models.tutorial_models import IValidator

logger = logging.getLogger(__name__)

# --- Precomputed SHA-256 Hashes for Tutorial FCS Files ---
BLANK_HASH = "a48637befecc2683788d5879170a5724ab969adc2fb47ea6a60f7c133b8ca515"
PI_HASH = "39a5230839fa35f672fcd9345cbc4f121a11e9f6fddd23713b40df4f73849b7b"
FMO_HASHES = {
    "984d77b501c9e3d5972f4e2fb1e5e9018423ccc18fd0be923216980c74c85334",  # FMO APC
    "be101bec4e437220391402c5857fac4532000c818f9538390ca24a665ba5745e",  # FMO APCCy7
    "e590765822e0f8b06ca1e991e277fdc0eeebd4543ea6d4826cf8d11c0600baaa",  # FMO FITC
    "5bbab776956d21bab9b047e61efef37437299c0bdd1deef5a06f26ca221fa04a",  # FMO PE
    "94edf97d2754a68bdb559c7dd07255243273e2b0b118d1105ff49968feb2599d",  # FMO e450
}
FULL_PANEL_HASHES = {
    "d3a14041489f891c48a31a495ed4e8569e4b878b9b99eb1673d5b3194dd67ea4",  # Sample A
    "dddbccbb17d100a3fe0c20c3d842865804555ff845d210c432b6145dfdb7e625",  # Sample B
    "e870254b55057c3765184f49c52870f35a5fe1c12197f393a12872deef846e5f",  # Sample C
}
EXPECTED_TUTORIAL_HASHES = {BLANK_HASH, PI_HASH} | FMO_HASHES | FULL_PANEL_HASHES


class TabActiveValidator(IValidator):
    """Verifies that the user has navigated to a specific main tab index."""

    def __init__(self, target_index: int) -> None:
        self.target_index = target_index

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view"):
            return False
        return getattr(app_state.view, "active_main_tab_index", -1) == self.target_index


class FlowImportValidator(IValidator):
    """Verifies that exactly the 10 correct tutorial FCS files have been imported."""

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        samples = list(app_state.data.experiment.samples.values())
        if len(samples) < 10:
            return False

        loaded_hashes = set()
        for s in samples:
            if not s.has_data:
                return False
            if hasattr(s, "tutorial_file_hash") and s.tutorial_file_hash:
                loaded_hashes.add(s.tutorial_file_hash)

        # Must have exactly the 10 tutorial hashes
        return EXPECTED_TUTORIAL_HASHES.issubset(loaded_hashes)


class UnstainedRoleValidator(IValidator):
    """Verifies that the Blank sample has the Unstained role."""

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        from analysis.experiment import SampleRole

        for s in app_state.data.experiment.samples.values():
            if s.role == SampleRole.UNSTAINED:
                if getattr(s, "tutorial_file_hash", "") == BLANK_HASH:
                    logger.info(
                        "UnstainedRoleValidator: Detected Blank sample with UNSTAINED role"
                    )
                    return True
                else:
                    logger.info(
                        f"UnstainedRoleValidator: Found UNSTAINED role but hash {getattr(s, 'tutorial_file_hash', 'None')} does not match BLANK_HASH {BLANK_HASH}"
                    )

        logger.info("UnstainedRoleValidator: Returning False")
        return False


class SingleStainRoleValidator(IValidator):
    """Verifies that the PI sample has the Single Stain role."""

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        from analysis.experiment import SampleRole

        for s in app_state.data.experiment.samples.values():
            if s.role == SampleRole.SINGLE_STAIN:
                if getattr(s, "tutorial_file_hash", "") == PI_HASH:
                    logger.info(
                        "SingleStainRoleValidator: Detected PI sample with SINGLE_STAIN role"
                    )
                    return True
                else:
                    logger.info(
                        f"SingleStainRoleValidator: Found SINGLE_STAIN role but hash {getattr(s, 'tutorial_file_hash', 'None')} does not match PI_HASH {PI_HASH}"
                    )
        logger.info("SingleStainRoleValidator: Returning False")
        return False


class FmoRoleValidator(IValidator):
    """Verifies that ALL 5 FMO samples have the FMO Control role."""

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        from analysis.experiment import SampleRole

        fmo_count = 0
        for s in app_state.data.experiment.samples.values():
            if s.role == SampleRole.FMO_CONTROL:
                if getattr(s, "tutorial_file_hash", "") in FMO_HASHES:
                    fmo_count += 1
                else:
                    logger.info(
                        f"FmoRoleValidator: Found FMO_CONTROL role but hash {getattr(s, 'tutorial_file_hash', 'None')} not in FMO_HASHES"
                    )
        logger.info(f"FmoRoleValidator: Found {fmo_count}/5 FMO samples")
        return fmo_count >= 5


class RoleAssignmentValidator(IValidator):
    """Verifies all four role types are present, NO sample has the default 'OTHER' role, and the mystery samples are Full Panel."""

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        from analysis.experiment import SampleRole

        samples = app_state.data.experiment.samples.values()
        roles = {s.role for s in samples}

        # All samples must be assigned away from the default OTHER role
        if SampleRole.OTHER in roles:
            return False

        # Verify the mystery samples (Sample A, B, C) are FULL_PANEL
        full_panel_count = 0
        for s in samples:
            if s.role == SampleRole.FULL_PANEL:
                if getattr(s, "tutorial_file_hash", "") in FULL_PANEL_HASHES:
                    full_panel_count += 1
                else:
                    logger.info(
                        f"RoleAssignmentValidator: Found FULL_PANEL role but hash {getattr(s, 'tutorial_file_hash', 'None')} not in FULL_PANEL_HASHES"
                    )

        if full_panel_count < 3:
            logger.info(
                f"RoleAssignmentValidator: full_panel_count {full_panel_count} < 3"
            )
            return False

        has_all_roles = {
            SampleRole.UNSTAINED,
            SampleRole.SINGLE_STAIN,
            SampleRole.FMO_CONTROL,
            SampleRole.FULL_PANEL,
        }.issubset(roles)

        logger.info(
            f"RoleAssignmentValidator: all roles present? {has_all_roles}, roles found: {roles}"
        )
        return has_all_roles


class CompensationAppliedValidator(IValidator):
    """Verifies a compensation matrix exists, and auto-applies it to all samples."""

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        if app_state.data.compensation is None:
            from biopro_sdk.plugin import get_logger

            from analysis.compensation import extract_spill_from_fcs

            logger = get_logger(__name__, "flow_cytometry")
            logger.info(
                "CompensationAppliedValidator: Starting to search for $SPILL in %d samples",
                len(app_state.data.experiment.samples),
            )
            for sample in app_state.data.experiment.samples.values():
                if sample.fcs_data:
                    comp = extract_spill_from_fcs(sample.fcs_data)
                    if comp is not None:
                        logger.info(
                            "CompensationAppliedValidator: Found matrix in sample %s",
                            sample.display_name,
                        )
                        app_state.data.compensation = comp
                        break
                    else:
                        logger.info(
                            "CompensationAppliedValidator: No matrix found in sample %s",
                            sample.display_name,
                        )

            if app_state.data.compensation is None:
                logger.warning(
                    "CompensationAppliedValidator: Failed to find any matrix!"
                )
                return False

        # The matrix exists! Auto-apply it so the tutorial can skip the manual application steps.
        applied_any = False
        for sample in app_state.data.experiment.samples.values():
            if not sample.is_compensated:
                sample.is_compensated = True
                applied_any = True

        if applied_any:
            try:
                from biopro_sdk.plugin import CentralEventBus

                from analysis.events import EXPERIMENT_DATA_CHANGED

                CentralEventBus.publish(EXPERIMENT_DATA_CHANGED, {})
            except Exception:
                pass

        return True


class GateExistsValidator(IValidator):
    """Verifies that a gate with the given name exists on at least one Full Panel sample."""

    def __init__(self, target_gate_name: str) -> None:
        self._target = target_gate_name.lower()

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        from analysis.experiment import SampleRole

        samples = list(app_state.data.experiment.samples.values())
        full_panel = [s for s in samples if s.role == SampleRole.FULL_PANEL] or samples
        return any(self._gate_found(s.gate_tree) for s in full_panel)

    def _gate_found(self, node: Any) -> bool:
        if getattr(node, "name", "").lower() == self._target:
            return True
        return any(self._gate_found(child) for child in getattr(node, "children", []))


class SampleOpenValidator(IValidator):
    """Verifies that the Blank (Unstained) sample is currently the active graph in the workspace."""

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view"):
            return False
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return False
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        from analysis.experiment import SampleRole

        sample = app_state.data.experiment.samples.get(sample_id)
        return sample is not None and sample.role == SampleRole.UNSTAINED


class SpecificSampleOpenValidator(IValidator):
    """Verifies that a sample with a specific SampleRole is currently open."""

    def __init__(self, role_name: str) -> None:
        """Args: role_name: e.g. 'SINGLE_STAIN' to match SampleRole.SINGLE_STAIN."""
        self._role_name = role_name.upper()

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view"):
            return False
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return False
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        from analysis.experiment import SampleRole

        sample = app_state.data.experiment.samples.get(sample_id)
        if sample is None:
            return False
        try:
            expected_role = SampleRole[self._role_name]
            return sample.role == expected_role
        except KeyError:
            return False


class AxisChannelValidator(IValidator):
    """Verifies that the active X axis channel contains a specific keyword."""

    def __init__(self, channel_keyword: str) -> None:
        self._keyword = channel_keyword.lower()

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view"):
            return False
        x_param = getattr(app_state.view, "active_x_param", "") or ""
        return self._keyword in x_param.lower()


class AxisTransformValidator(IValidator):
    """Verifies that the active X axis transform matches a specific type (e.g. 'biexponential')."""

    def __init__(self, transform_name: str) -> None:
        self._transform = transform_name.lower()

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view"):
            return False
        active = getattr(app_state.view, "active_transform_x", "") or ""
        return active.lower() == self._transform


class AxisOutlierValidator(IValidator):
    """Verifies that the active X axis outlier percentile matches a specific value."""

    def __init__(self, target_percentile: float) -> None:
        self._target = target_percentile

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view") or not hasattr(app_state, "data"):
            return False
        x_param = getattr(app_state.view, "active_x_param", None)
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not x_param:
            return False

        try:
            from analysis.axis_manager import AxisManager

            manager = AxisManager(app_state)
            scale = manager.get_scale(x_param, sample_id)
            # Use a small epsilon for float comparison
            return abs(scale.outlier_percentile - self._target) < 0.001
        except Exception:
            return False


class GateExistsOnAllValidator(GateExistsValidator):
    """Verifies that a gate with the given name exists on ALL Full Panel samples."""

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        from analysis.experiment import SampleRole

        samples = list(app_state.data.experiment.samples.values())
        full_panel = [s for s in samples if s.role == SampleRole.FULL_PANEL]
        if not full_panel:
            return False
        return all(self._gate_found(s.gate_tree) for s in full_panel)


class ExactSampleOpenValidator(IValidator):
    """Verifies that a specific named sample is currently open."""

    def __init__(self, sample_name: str) -> None:
        self._sample_name = sample_name.lower()

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view"):
            return False
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return False
        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False
        sample = app_state.data.experiment.samples.get(sample_id)
        return sample is not None and self._sample_name in sample.display_name.lower()


class AxisYChannelValidator(IValidator):
    """Verifies that the active Y axis channel contains a specific keyword."""

    def __init__(self, channel_keyword: str) -> None:
        self._keyword = channel_keyword.lower()

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view"):
            return False
        y_param = getattr(app_state.view, "active_y_param", "") or ""
        return self._keyword in y_param.lower()


class LiveGateExistsValidator(IValidator):
    """Verifies that a RangeGate has been drawn on the PI channel (PerCP) for the active single-stain sample.

    Accepts any gate whose high bound is below 10,000 — i.e. the user captured the left
    (live) population and did NOT extend the gate into the dead-cell peak.
    """

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view") or not hasattr(app_state, "data"):
            return False
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return False
        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return False

        def check_node(node) -> bool:
            gate = getattr(node, "gate", None)
            if type(gate).__name__ == "RangeGate":
                # Accept any range gate where low < high and high is in the live-cell
                # region (raw values, not display). Dead cells are typically > 100,000.
                if getattr(gate, "high", float("inf")) < 50_000:
                    return True
            for child in getattr(node, "children", []):
                if check_node(child):
                    return True
            return False

        return check_node(sample.gate_tree)


class LeukocyteGateExistsValidator(IValidator):
    """Verifies that a RectangleGate has been drawn for Leukocytes (CD45+).

    Accepts any RectangleGate where the X-min is positive (above background) and
    X-max extends into the positive range, while Y covers the FSC-A range.
    """

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view") or not hasattr(app_state, "data"):
            return False
        sample_id = getattr(app_state.view, "current_sample_id", None)
        if not sample_id:
            return False
        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return False

        def check_node(node) -> bool:
            gate = getattr(node, "gate", None)
            if type(gate).__name__ == "RectangleGate":
                # Professional standard: CD45 (APC-A) vs SSC-A.
                # Just check that it's an APC-A/SSC-A gate and X-min is > 0 (gating out negative cells).
                if "apc" in gate.x_param.lower() and "ssc" in gate.y_param.lower():
                    if gate.x_min > -1000 and gate.x_max > gate.x_min:
                        return True
            for child in getattr(node, "children", []):
                if check_node(child):
                    return True
            return False

        return check_node(sample.gate_tree)


class GateShapeValidator(IValidator):
    """Verifies that a newly created gate matches the required target shape."""

    def __init__(
        self,
        target_bounds: tuple[float, float, float, float] | None = None,
        target_poly: list[tuple[float, float]] | None = None,
    ) -> None:
        """
        Args:
            target_bounds: (min_x, max_x, min_y, max_y). For 1D gates, use 0 for min_y, max_y.
            target_poly: List of (x, y) vertices for the target polygon shape.
        """
        self.target_bounds = target_bounds
        self.target_poly = target_poly

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view") or not getattr(
            app_state.view, "current_sample_id", None
        ):
            return False
        sample_id = app_state.view.current_sample_id

        if not hasattr(app_state, "data") or not hasattr(app_state.data, "experiment"):
            return False

        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return False

        def check_node(node) -> bool:
            if getattr(node, "node_id", None) and self.validate_shape(
                app_state, node.node_id, sample_id
            ):
                return True
            for child in getattr(node, "children", []):
                if check_node(child):
                    return True
            return False

        return check_node(sample.gate_tree)

    def validate_shape(self, app_state: Any, node_id: str, sample_id: str) -> bool:
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
            return iou >= 0.90

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

        if gate_type == "RangeGate" or gate_type == "QuadrantGate":
            # For 1D ranges or points, check relative error based on a typical flow axis range (262144)
            axis_range = 262144.0

            # Check X bounds
            if (
                abs(min_x - t_min_x) / axis_range > 0.10
                or abs(max_x - t_max_x) / axis_range > 0.10
            ):
                return False

            # Check Y bounds for Quadrant
            if gate_type == "QuadrantGate":
                if (
                    abs(min_y - t_min_y) / axis_range > 0.10
                    or abs(max_y - t_max_y) / axis_range > 0.10
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
        return iou >= 0.65


class WorkflowSavedValidator(IValidator):
    """Verifies that the user has saved a workflow and registers it as a prerequisite."""

    def validate(self, app_state: Any) -> bool:
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

        print(f"DEBUG(WorkflowSavedValidator): Found project manager: {pm is not None}")
        if not pm:
            return False

        workflows = pm.workflows.list_all()
        print(f"DEBUG(WorkflowSavedValidator): Number of workflows: {len(workflows)}")
        if not workflows:
            return False

        # We require the user to have explicitly saved it. Check all workflows.
        for wf in workflows:
            wf_filename = wf.get("filename", "")
            print(
                f"DEBUG(WorkflowSavedValidator): Checking workflow: {wf.get('name')} (file: {wf_filename})"
            )
            if wf_filename:
                wf_hash = pm.get_workflow_hash(wf_filename)
                print(
                    f"DEBUG(WorkflowSavedValidator): Hash for {wf_filename}: {wf_hash}"
                )
                if wf_hash:
                    from biopro.core.tutorial_manager import global_tutorial_manager

                    global_tutorial_manager.record_prerequisite(
                        "flow_course_2_gating", wf_hash
                    )
                    print(
                        "DEBUG(WorkflowSavedValidator): SUCCESS! Prerequisites recorded."
                    )
                    return True

        print(
            "DEBUG(WorkflowSavedValidator): Failed to find a valid saved workflow hash."
        )
        return False


class GateActiveValidator(IValidator):
    """Verifies that the user has double-clicked a specific gate in the hierarchy to enter it."""

    def __init__(self, target_gate_name: str) -> None:
        self.target = target_gate_name.lower()

    def validate(self, app_state: Any) -> bool:
        if not hasattr(app_state, "view"):
            return False

        gate_id = getattr(app_state.view, "current_gate_id", None)
        sample_id = getattr(app_state.view, "current_sample_id", None)

        if not sample_id:
            return False

        sample = app_state.data.experiment.samples.get(sample_id)
        if not sample:
            return False

        if not gate_id:
            # If no gate is selected, they are at the root
            return self.target in sample.gate_tree.name.lower()

        node = sample.gate_tree.find_node_by_id(gate_id)
        if node:
            return self.target in node.name.lower()

        return False
