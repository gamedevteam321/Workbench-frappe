import frappe
import uuid
from frappe import whitelist

@whitelist(allow_guest=True)
def create_block(page_id: str, block_type: str = 'text', prev_block_id: str | None = None):
    """Create a new block on a page.

    Args:
        page_id (str): The ID of the workbench page.
        block_type (str): Type of the block (default 'text').
        prev_block_id (str | None): ID of the block after which the new block should be inserted.
            Use 'HEAD' to insert at the beginning, or None to append at the end.

    Returns:
        dict: The newly created block as a dict.
    """
    # Verify the page exists
    try:
        frappe.get_doc('workbench_page', page_id)
    except frappe.DoesNotExistError:
        frappe.throw('Page not found', frappe.DoesNotExistError)

    # Generate a UUID for the block name (assuming the DocType uses autoname='UUID')
    new_id = str(uuid.uuid4())

    # Determine the position for the new block
    # Fetch sibling blocks (root level) for the page
    siblings = frappe.get_all(
        'workbench_block',
        filters={'workbench_page': page_id, 'parent_block': None},
        fields=['name', 'position'],
        order_by='position asc'
    )

    if prev_block_id == 'HEAD':
        # Insert at the beginning
        position = 0
    elif prev_block_id:
        # Find the previous block's position
        prev = next((b for b in siblings if b['name'] == prev_block_id), None)
        if prev:
            position = prev['position'] + 1000
        else:
            # If not found, append at end
            max_pos = max([b['position'] for b in siblings], default=0)
            position = max_pos + 1000
    else:
        # Append at end
        max_pos = max([b['position'] for b in siblings], default=0)
        position = max_pos + 1000

    # Create the block document
    doc = frappe.get_doc({
        'doctype': 'workbench_block',
        'name': new_id,
        'workbench_page': page_id,
        'block_type': block_type,
        'parent_block': None,
        'position': position,
        # Initialize empty JSON fields if they exist
        'content': [],
        'properties': {}
    })
    doc.insert(ignore_permissions=True)

    # Return the block as a dict (including the generated ID)
    return doc.as_dict()
