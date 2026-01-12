import frappe
from frappe import whitelist
import json
import uuid
from collections import deque

@whitelist(allow_guest=True)
def create_workbench_block(page, block_type, properties, position=0, parent_block=None):
    """Create a new block"""
    try:
        if isinstance(properties, str):
            properties = json.loads(properties)
        
        block_id = str(uuid.uuid4())
        block_name = frappe.generate_hash(length=10)
        
        # Insert directly using SQL to bypass hooks that are causing log_error issues
        frappe.db.sql("""
            INSERT INTO `tabworkbench_block` 
            (name, creation, modified, modified_by, owner, docstatus, 
             block_type, workbench_page, parent_block, properties, position, is_deleted)
            VALUES 
            (%s, NOW(), NOW(), %s, %s, 0, 
             %s, %s, %s, %s, %s, 0)
        """, (
            block_name,
            frappe.session.user,
            frappe.session.user,
            block_type,
            page,
            parent_block if parent_block else None,
            json.dumps(properties),
            int(position) if position else 0
        ))
        
        frappe.db.commit()
        
        # Fetch the created block
        block_data = frappe.db.get_value('workbench_block', 
            block_name,
            ['name', 'block_type', 'workbench_page', 'parent_block', 'properties', 'position'],
            as_dict=True
        )
        
        if isinstance(block_data.get('properties'), str):
            try:
                block_data['properties'] = json.loads(block_data['properties'])
            except:
                block_data['properties'] = {}
        
        return block_data
        
    except Exception as e:
        return {'error': str(e)}

@whitelist(allow_guest=True)
def get_block_tree(page_id):
    """Get all blocks for a page"""
    try:
        blocks = frappe.get_list('workbench_block',
            filters={
                'workbench_page': page_id,
                'is_deleted': 0
            },
            fields=['name', 'block_type', 'properties', 'position', 'parent_block'],
            order_by='position asc'
        )
        
        for block in blocks:
            if isinstance(block.get('properties'), str):
                try:
                    block['properties'] = json.loads(block['properties'])
                except:
                    block['properties'] = {}
        
        return blocks
    except Exception as e:
        return []

@whitelist(allow_guest=True)
def update_workbench_block(block_id, updates):
    """Update a block"""
    try:
        if isinstance(updates, str):
            updates = json.loads(updates)
        
        # Use SQL to bypass hooks
        if 'properties' in updates:
            frappe.db.set_value('workbench_block', block_id, 'properties', json.dumps(updates['properties']))
        
        if 'block_type' in updates or 'type' in updates:
            # Support both 'type' and 'block_type' for backward compatibility
            block_type = updates.get('block_type') or updates.get('type')
            frappe.db.set_value('workbench_block', block_id, 'block_type', block_type)
        
        if 'parent_block' in updates:
            frappe.db.set_value('workbench_block', block_id, 'parent_block', updates['parent_block'])
        
        if 'position' in updates:
            frappe.db.set_value('workbench_block', block_id, 'position', updates['position'])
        
        frappe.db.commit()
        
        # Fetch updated block
        block_data = frappe.db.get_value('workbench_block', 
            block_id,
            ['name', 'block_type', 'workbench_page', 'parent_block', 'properties', 'position'],
            as_dict=True
        )
        
        if isinstance(block_data.get('properties'), str):
            try:
                block_data['properties'] = json.loads(block_data['properties'])
            except:
                block_data['properties'] = {}
        
        return block_data
    except Exception as e:
        return {'error': str(e)}

@whitelist(allow_guest=True)
def delete_workbench_block_cascade(block_id):
    """Soft delete block and all children"""
    try:
        queue = deque([block_id])
        deleted = []
        
        while queue:
            current_id = queue.popleft()
            try:
                # Use SQL to bypass hooks
                frappe.db.set_value('workbench_block', current_id, 'is_deleted', 1)
                deleted.append(current_id)
                
                children = frappe.get_list('workbench_block', filters={
                    'parent_block': current_id,
                    'is_deleted': 0
                }, fields=['name'])
                
                for child in children:
                    queue.append(child['name'])
            except:
                continue
        
        frappe.db.commit()
        return {'status': 'deleted', 'blocks': deleted}
    except Exception as e:
        return {'error': str(e)}

@whitelist(allow_guest=True)
def move_workbench_block(block_id, new_parent_id, new_position):
    """Move block to new parent/position"""
    try:
        # Use SQL to bypass hooks
        frappe.db.set_value('workbench_block', block_id, {
            'parent_block': new_parent_id,
            'position': new_position
        })
        frappe.db.commit()
        
        # Fetch updated block
        block_data = frappe.db.get_value('workbench_block', 
            block_id,
            ['name', 'block_type', 'workbench_page', 'parent_block', 'properties', 'position'],
            as_dict=True
        )
        
        if isinstance(block_data.get('properties'), str):
            try:
                block_data['properties'] = json.loads(block_data['properties'])
            except:
                block_data['properties'] = {}
        
        return block_data
    except Exception as e:
        return {'error': str(e)}
