import frappe
from frappe import whitelist
import json


# ============================================
# WORKBENCH CRUD
# ============================================

@whitelist(allow_guest=True)
def create_workbench(title, slug=None, owner_id=None):
    """Create a new workbench"""
    if not owner_id:
        owner_id = frappe.session.user
    
    if not slug:
        slug = title.lower().replace(' ', '-')
    
    workbench = frappe.get_doc({
        'doctype': 'workbench',
        'title': title,
        'slug': slug,
        'owner_id': owner_id
    })
    workbench.insert(ignore_permissions=True)
    return workbench.as_dict()


@whitelist(allow_guest=True)
def get_workbench(workbench_id):
    """Get a workbench by ID"""
    return frappe.get_doc('workbench', workbench_id).as_dict()


@whitelist(allow_guest=True)
def update_workbench(workbench_id, updates):
    """Update a workbench"""
    workbench = frappe.get_doc('workbench', workbench_id)
    if isinstance(updates, str):
        updates = json.loads(updates)
    workbench.update(updates)
    workbench.save(ignore_permissions=True)
    return workbench.as_dict()


@whitelist(allow_guest=True)
def delete_workbench(workbench_id):
    """Delete a workbench"""
    frappe.delete_doc('workbench', workbench_id)
    return {'status': 'deleted', 'id': workbench_id}


@whitelist(allow_guest=True)
def list_workbenches():
    """Get all workbenches for current user"""
    workbenches = frappe.get_list('workbench', 
        filters={'owner_id': frappe.session.user},
        fields=['name', 'title', 'slug', 'is_archived', 'creation']
    )
    return workbenches


@whitelist(allow_guest=True)
def archive_workbench(workbench_id):
    """Archive a workbench"""
    workbench = frappe.get_doc('workbench', workbench_id)
    workbench.is_archived = 1
    workbench.save(ignore_permissions=True)
    return workbench.as_dict()


# ============================================
# BLOCK CRUD
# ============================================

@whitelist(allow_guest=True)
def get_blocks(page_id):
    """Get all blocks for a specific page"""
    if not page_id:
        return []
    
    blocks = frappe.get_list(
        'workbench_block',
        filters={
            'workbench_page': page_id,
            'is_deleted': 0
        },
        fields=[
            'name',
            'block_id',
            'type',
            'workbench_page',
            'parent_block',
            'properties',
            'position'
        ],
        order_by='position asc'
    )
    
    return blocks


@whitelist(allow_guest=True)
def create_block(workbench_page, parent_block='', block_type='paragraph', properties='{}', position=None):
    """Create a new block"""
    import uuid
    
    # Generate unique block_id
    block_id = f"block_{block_type}_{str(uuid.uuid4())[:8]}"
    
    # Get position if not provided
    if position is None:
        filters = {
            'workbench_page': workbench_page,
            'parent_block': parent_block or ''
        }
        siblings = frappe.get_all('workbench_block', 
                                 filters=filters, 
                                 fields=['position'],
                                 order_by='position desc',
                                 limit=1)
        position = (siblings[0].position if siblings else 0) + 1
    
    # Parse properties if string
    if isinstance(properties, str):
        try:
            properties = json.loads(properties)
        except:
            properties = {}
    
    block = frappe.get_doc({
        'doctype': 'workbench_block',
        'block_id': block_id,
        'type': block_type,
        'workbench_page': workbench_page,
        'parent_block': parent_block or None,
        'properties': json.dumps(properties),
        'position': position,
        'is_deleted': 0
    })
    block.insert(ignore_permissions=True)
    return block.as_dict()


@whitelist(allow_guest=True)
def update_block(block_id, updates_json):
    """Update a block's properties and other fields"""
    block = frappe.get_doc('workbench_block', {'block_id': block_id})
    
    if isinstance(updates_json, str):
        updates = json.loads(updates_json)
    else:
        updates = updates_json
    
    for key, value in updates.items():
        if key == "properties":
            if isinstance(value, dict):
                block.properties = json.dumps(value)
            else:
                block.properties = value
        elif hasattr(block, key):
            setattr(block, key, value)
    
    block.save(ignore_permissions=True)
    return block.as_dict()


@whitelist(allow_guest=True)
def delete_block(block_id):
    """Soft delete a block"""
    block = frappe.get_doc('workbench_block', {'block_id': block_id})
    block.is_deleted = 1
    block.save(ignore_permissions=True)
    return {'status': 'deleted', 'block_id': block_id}


@whitelist(allow_guest=True)
def reorder_block(block_id, new_position):
    """Update block position"""
    block = frappe.get_doc('workbench_block', {'block_id': block_id})
    old_position = block.position
    new_position = int(new_position)
    
    # Get all siblings (same parent)
    filters = {
        'workbench_page': block.workbench_page,
        'parent_block': block.parent_block or '',
        'is_deleted': 0
    }
    siblings = frappe.get_all('workbench_block', 
                             filters=filters, 
                             fields=['name', 'block_id', 'position'],
                             order_by='position')
    
    # Reorder positions
    if new_position > old_position:
        # Moving down - sshift others up
        for sibling in siblings:
            if sibling.position > old_position and sibling.position <= new_position:
                sib_doc = frappe.get_doc('workbench_block', sibling.name)
                sib_doc.position -= 1
                sib_doc.save(ignore_permissions=True)
    else:
        # Moving up - shift others down
        for sibling in siblings:
            if sibling.position >= new_position and sibling.position < old_position:
                sib_doc = frappe.get_doc('workbench_block', sibling.name)
                sib_doc.position += 1
                sib_doc.save(ignore_permissions=True)
    
    # Update target block
    block.position = new_position
    block.save(ignore_permissions=True)
    
    return {'status': 'reordered', 'block_id': block_id, 'new_position': new_position}
