"""
Operation handlers for block and page operations
Separated from main websocket.py for cleaner organization
"""

from typing import Dict
import json
import logging
import frappe

from workbench_react.api.errors import (
    WorkbenchError,
    ValidationError,
    NotFoundError,
    OwnershipError,
    TransactionError,
    ERROR_MESSAGES,
)
from workbench_react.api.validators import PayloadValidator, PermissionValidator

logger = logging.getLogger("workbench.handlers")


class BlockHandler:
    """Handles block CRUD operations"""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def create(self, page_id: str, payload: Dict) -> Dict:
        try:
            PayloadValidator.validate_block_create(payload)
            PermissionValidator.check_page_exists(page_id)

            block_id = payload["id"]
            block_type = payload.get("type", "paragraph")

            logger.info(f"[Block] Creating {block_id} of type {block_type}")

            if frappe.db.exists("Workbench Block", block_id):
                raise ValidationError(f"Block {block_id} already exists")

            block = frappe.new_doc("Workbench Block")
            block.name = block_id
            block.workbench_page = page_id
            block.block_type = block_type
            block.position = int(payload.get("position", 0))
            block.parent_block = payload.get("parent_block")
            block.prev_id = payload.get("prev_id")
            block.properties = json.dumps(payload.get("properties", {}))
            block.content = json.dumps(payload.get("content", []))
            block.owner = self.user_id
            block.insert(ignore_permissions=False)

            logger.info(f"[Block] ✅ Created: {block_id}")
            return block.as_dict()

        except (ValidationError, NotFoundError) as e:
            logger.warning(f"[Block] Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[Block] 🔥 Creation error: {str(e)}", exc_info=True)
            raise

    def update(self, page_id: str, payload: Dict) -> Dict:
        try:
            PayloadValidator.validate_block_update(payload)
            block_id = payload.get("id")
            PermissionValidator.check_block_exists(block_id)

            logger.info(f"[Block] Updating {block_id}")

            block = frappe.get_doc("Workbench Block", block_id)
            PermissionValidator.check_ownership(block, self.user_id, "Block")

            if "position" in payload:
                block.position = int(payload["position"])
            if "parent_block" in payload:
                block.parent_block = payload["parent_block"]
            if "prev_id" in payload:
                block.prev_id = payload["prev_id"]
            if "properties" in payload:
                block.properties = json.dumps(payload["properties"])
            if "content" in payload:
                block.content = json.dumps(payload["content"])
            if "type" in payload:
                block.block_type = payload["type"]

            block.save(ignore_permissions=False)

            logger.info(f"[Block] ✅ Updated: {block_id}")
            return block.as_dict()

        except (ValidationError, NotFoundError, OwnershipError) as e:
            logger.warning(f"[Block] Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[Block] 🔥 Update error: {str(e)}", exc_info=True)
            raise

    def delete(self, page_id: str, payload: Dict) -> Dict:
        try:
            PayloadValidator.validate_block_delete(payload)
            block_id = payload.get("id")
            PermissionValidator.check_block_exists(block_id)

            logger.info(f"[Block] Deleting {block_id}")

            block = frappe.get_doc("Workbench Block", block_id)
            PermissionValidator.check_ownership(block, self.user_id, "Block")

            frappe.delete_doc("Workbench Block", block_id, ignore_permissions=False)

            logger.info(f"[Block] ✅ Deleted: {block_id}")
            return {"id": block_id, "status": "deleted"}

        except (ValidationError, NotFoundError, OwnershipError) as e:
            logger.warning(f"[Block] Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[Block] 🔥 Delete error: {str(e)}", exc_info=True)
            raise


class PageHandler:
    """Handles page CRUD operations"""

    def __init__(self, user_id: str):
        self.user_id = user_id

    def create(self, payload: Dict) -> Dict:
        try:
            PayloadValidator.validate_page_create(payload)

            logger.info(f"[Page] Creating page: {payload['title']}")

            page = frappe.new_doc("Workbench Page")
            page.title = payload["title"]
            page.workbench = payload.get("workbench")
            page.icon = payload.get("icon")
            page.cover_image = payload.get("cover_image")
            page.owner = self.user_id
            page.insert(ignore_permissions=False)

            logger.info(f"[Page] ✅ Created: {page.name}")
            return page.as_dict()

        except ValidationError as e:
            logger.warning(f"[Page] Validation error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[Page] 🔥 Creation error: {str(e)}", exc_info=True)
            raise

    def clear(self, page_id: str, payload: Dict) -> Dict:
        try:
            PayloadValidator.validate_page_clear(payload)
            PermissionValidator.check_page_exists(page_id)

            logger.info(f"[Page] Clearing page: {page_id}")

            page = frappe.get_doc("Workbench Page", page_id)
            PermissionValidator.check_ownership(page, self.user_id, "Page")

            blocks = frappe.db.get_list(
                "Workbench Block", filters={"workbench_page": page_id}
            )
            for block in blocks:
                try:
                    frappe.delete_doc(
                        "Workbench Block", block.name, ignore_permissions=False
                    )
                    logger.info(f"[Page] Cleared block: {block.name}")
                except Exception as e:
                    logger.warning(f"[Page] Failed to clear block {block.name}: {str(e)}")

            page.title = ""
            if hasattr(page, "is_saved"):
                page.is_saved = 0
            page.save(ignore_permissions=False)

            logger.info(f"[Page] ✅ Cleared: {page_id}")
            return {"id": page_id, "status": "cleared", "title": "", "is_saved": 0}

        except (ValidationError, NotFoundError, OwnershipError) as e:
            logger.warning(f"[Page] Error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"[Page] 🔥 Clear error: {str(e)}", exc_info=True)
            raise
