import frappe
from frappe import whitelist
import json


@whitelist(allow_guest=True)  # ← Add this
def create_workbench_page(title, workbench, icon=None, cover_image=None, owner_id=None):
    """Create a new page"""
    if not owner_id:
        owner_id = frappe.session.user
    
    page = frappe.get_doc({
        'doctype': 'workbench_page',
        'title': title,
        'icon': icon or '📄',
        'cover_image': cover_image,
        'workbench': workbench,
        'owner_id': owner_id
    })
    page.insert(ignore_permissions=True)
    return page.as_dict()


@whitelist(allow_guest=True)  # ← Add this
def get_workbench_page(page_id):
    """Get a page by ID"""
    return frappe.get_doc('workbench_page', page_id).as_dict()


@whitelist(allow_guest=True)  # ← Add this
def update_workbench_page(page_id, updates):
    """Update a page"""
    page = frappe.get_doc('workbench_page', page_id)
    if isinstance(updates, str):
        updates = json.loads(updates)
    page.update(updates)
    page.save(ignore_permissions=True)
    return page.as_dict()


@whitelist(allow_guest=True)  # ← Add this
def delete_workbench_page(page_id):
    """Delete a page"""
    frappe.delete_doc('workbench_page', page_id)
    return {'status': 'deleted', 'id': page_id}


@whitelist(allow_guest=True)  # ← Add this
def list_workbench_pages(workbench):
    """Get all pages in a workbench"""
    pages = frappe.get_list('workbench_page',
        filters={'workbench': workbench, 'is_archived': 0},
        fields=['name', 'title', 'icon', 'cover_image', 'owner_id', 'creation'],
        order_by='creation asc'
    )
    return pages


@whitelist(allow_guest=True)
def archive_workbench_page(page_id):
    """Archive a page"""
    page = frappe.get_doc('workbench_page', page_id)
    page.is_archived = 1
    page.save(ignore_permissions=True)
    return page.as_dict()


@whitelist(allow_guest=True)
def get_block_tree_optimized(page_id):
    """
    Fetch all blocks for a page in a single optimized query.
    Returns a flat list of blocks. Frontend handles tree construction.
    """
    try:
        # Verify page exists
        frappe.get_doc('workbench_page', page_id)
    except frappe.DoesNotExistError:
        frappe.throw("Page not found", frappe.DoesNotExistError)

    # Fetch all blocks for this page
    # We fetch specific fields to minimize data transfer
    blocks = frappe.get_all('workbench_block',
        filters={'workbench_page': page_id},
        fields=['name', 'block_type', 'properties', 'content', 'parent_block', 'position', 'owner'],
        order_by='position asc'
    )

    # Normalize data
    normalized_blocks = []
    for block in blocks:
        # Parse JSON fields
        if isinstance(block.get('content'), str):
            block['content'] = json.loads(block['content']) or []
        else:
            block['content'] = block.get('content') or []
            
        if isinstance(block.get('properties'), str):
            block['properties'] = json.loads(block['properties']) or {}
        else:
            block['properties'] = block.get('properties') or {}

        normalized_blocks.append(block)

    return {
        'blocks': normalized_blocks
    }


@whitelist(allow_guest=True)
def batch_update_blocks(page_id, updates):
    """
    Process a batch of block updates atomically.
    updates: List of operations [{cmd: 'create'|'update'|'delete', id: '...', data: {...}}]
    """
    if isinstance(updates, str):
        updates = json.loads(updates)

    results = []
    
    # Use a savepoint to ensure atomicity for the batch
    try:
        for op in updates:
            cmd = op.get('cmd')
            block_id = op.get('id')
            data = op.get('data', {})
            
            if cmd == 'create':
                # Create new block
                if not block_id:
                    # If no ID provided (shouldn't happen with client-side UUIDs), generate one?
                    # But we expect client to provide UUID.
                    pass 
                
                doc = frappe.get_doc({
                    'doctype': 'workbench_block',
                    'name': block_id, # Explicitly set name if allowed by naming series, otherwise it might be ignored if not set to User defined
                    'workbench_page': page_id,
                    **data
                })
                # If name is manually set, we might need to ensure autoname is handled or use insert(set_name=...)
                # For UUIDs, we usually set autoname='UUID' in DocType, but if we want client-side UUIDs, 
                # we might need to relax that or pass it as 'name' and ensure the system accepts it.
                # Assuming 'autoname' is set to 'UUID' or we can force it.
                # If we want to use the client-provided ID as the name:
                doc.name = block_id
                doc.insert(ignore_permissions=True)
                results.append({'id': block_id, 'status': 'created'})

            elif cmd == 'update':
                if frappe.db.exists('workbench_block', block_id):
                    doc = frappe.get_doc('workbench_block', block_id)
                    doc.update(data)
                    doc.save(ignore_permissions=True)
                    results.append({'id': block_id, 'status': 'updated'})
                else:
                    results.append({'id': block_id, 'status': 'not_found'})

            elif cmd == 'delete':
                if frappe.db.exists('workbench_block', block_id):
                    # Optional: Cascade delete is handled by frontend sending delete for children? 
                    # Or we can do it here. User requirement: "delete_block includes optional cascade"
                    # For batch update, we assume the client sends what needs to be deleted, 
                    # OR we implement recursive delete here.
                    # Let's implement recursive delete for safety.
                    _delete_block_recursive(block_id)
                    results.append({'id': block_id, 'status': 'deleted'})
                else:
                    results.append({'id': block_id, 'status': 'not_found'})

    except Exception as e:
        frappe.log_error(f"Batch update failed: {str(e)}")
        raise e

    return {'results': results}


def _delete_block_recursive(block_id):
    """Helper to delete a block and its children recursively"""
    children = frappe.get_all('workbench_block', filters={'parent_block': block_id}, fields=['name'])
    for child in children:
        _delete_block_recursive(child.name)
    frappe.delete_doc('workbench_block', block_id, ignore_permissions=True)


@whitelist(allow_guest=True)
def reorder_blocks(page_id, block_order):
    """
    Efficiently update positions for multiple blocks.
    block_order: Dict of {block_id: position}
    """
    if isinstance(block_order, str):
        block_order = json.loads(block_order)

    # We can use a single SQL query for better performance if needed, 
    # but loop with get_doc/save is safer for hooks.
    # For raw speed:
    try:
        for block_id, position in block_order.items():
            frappe.db.set_value('workbench_block', block_id, 'position', position, update_modified=False)
        
        # Update page modified timestamp
        frappe.db.set_value('workbench_page', page_id, 'modified', frappe.utils.now())
        
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}
