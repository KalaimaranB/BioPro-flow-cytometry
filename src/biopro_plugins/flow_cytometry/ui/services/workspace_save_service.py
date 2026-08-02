"""Workspace Save Service.

Handles interactions with the central ProjectManager for saving and
loading workflows.
"""

from typing import Any

from biopro_sdk.plugin import get_logger
from biopro_sdk.plugin.workflow import WorkflowContext

logger = get_logger(__name__, "flow_cytometry")


class WorkspaceSaveService:
    """Delegates persistence to the BioPro SDK ProjectManager."""

    @staticmethod
    def save_to_pm(
        pm: Any,
        workflow_service: Any,
        filename: str,
        metadata: dict[str, Any],
        module_id: str,
    ) -> str:
        """Save a new or existing workflow to the ProjectManager."""
        context = WorkflowContext()
        payload = workflow_service.export_workflow(context=context)

        # 1. Save initially to establish the workflow file and get the generated filename
        new_filename = pm.save_workflow(
            module_id=module_id,
            payload=payload,
            metadata=metadata,
            filename=filename,
            attachments=[],
        )

        # 2. Process attachments now that we have a filename
        attachments = pm.workflows.load_attachments(new_filename) or []
        existing_keys = {a.get("key") for a in attachments}

        for key, att_info in context.pending_attachments.items():
            if "source_path" in att_info:
                try:
                    att_record = pm.attach_workflow_file(
                        wf_filename=new_filename,
                        source_path=att_info["source_path"],
                        key=key,
                        description=att_info.get("description", ""),
                        mime_hint=att_info.get("mime_hint", "application/octet-stream"),
                    )
                    if key in existing_keys:
                        attachments = [
                            a if a.get("key") != key else att_record
                            for a in attachments
                        ]
                    else:
                        attachments.append(att_record)
                except Exception as e:
                    logger.warning(f"Failed to attach {key}: {e}")

        # 3. Finalize workflow with complete attachment records
        pm.save_workflow(
            module_id=module_id,
            payload=payload,
            metadata=metadata,
            filename=new_filename,
            attachments=attachments,
        )
        return new_filename

    @staticmethod
    def load_from_pm(
        pm: Any, workflow_service: Any, filename: str
    ) -> tuple[bool, dict[str, Any]]:
        """Load a workflow from the ProjectManager.

        Returns:
            Tuple of (success_bool, metadata_dict).
        """
        payload = pm.load_workflow_payload(filename)
        atts = pm.workflows.load_attachments(filename)
        context = WorkflowContext.from_attachment_dicts(atts, pm.project_dir)

        # We need to extract metadata from the payload or PM itself.
        # However, metadata is usually in the PM record.
        # The original code loaded it from the JSON directly if it existed,
        # but PM.load_workflow_payload already gets the payload.
        # We'll just return the metadata from the payload if present,
        # otherwise rely on the caller reading it beforehand.
        metadata = payload.get("metadata", {})

        success = workflow_service.load_workflow(payload, context=context)
        return success, metadata
