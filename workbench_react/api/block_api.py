import frappe
from frappe import whitelist
import json
import uuid
from collections import deque

@whitelist(allow_guest=True)
def update_workbench_block(block_id, updates):
    """Update a block's properties, type, and rich text content"""
    try:
        if isinstance(updates, str):
            updates = json.loads(updates)
        
        # 1. Update Properties (Visuals, toggles, etc.)
        if 'properties' in updates:
            frappe.db.set_value('workbench_block', block_id, 'properties', json.dumps(updates['properties']))
        
        # 2. Update Type (Convert block)
        if 'type' in updates:
            frappe.db.set_value('workbench_block', block_id, 'type', updates['type'])
            
        # 3. [NEW] Update Content (Rich Text / Structure)
        if 'content' in updates:
            content_val = updates['content']
            # Ensure it's stored as a JSON string
            if not isinstance(content_val, str):
                content_val = json.dumps(content_val)
            frappe.db.set_value('workbench_block', block_id, 'content', content_val)
        
        frappe.db.commit()
        
        # Fetch updated block to return to frontend
        block_data = frappe.db.get_value('workbench_block', 
            {'name': block_id},
            ['name', 'block_id', 'type', 'workbench_page', 'parent_block', 'properties', 'content', 'position'],
            as_dict=True
        )
        
        # Parse JSON fields for the response
        if block_data:
            if isinstance(block_data.get('properties'), str):
                try:
                    block_data['properties'] = json.loads(block_data['properties'])
                except:
                    block_data['properties'] = {}
            
            if isinstance(block_data.get('content'), str):
                try:
                    block_data['content'] = json.loads(block_data['content'])
                except:
                    block_data['content'] = []

        return block_data
    except Exception as e:
        frappe.log_error(f"Update Block Error: {str(e)}")
        return {'error': str(e)}

# ... (Keep create_workbench_block, delete_workbench_block_cascade, etc. as they were)

@whitelist(allow_guest=True)
def create_workbench_block(page, block_type, properties, position=0, parent_block=None, block_id=None):
    """
    Create a new block. 
    Accepts 'block_id' from frontend to support Optimistic Updates.
    """
    try:
        if isinstance(properties, str):
            properties = json.loads(properties)
        
        # 1. Use Client ID if provided, else generate one
        final_block_id = block_id if block_id else str(uuid.uuid4())
        
        # 2. SQL Insert with the specific Name/ID
        frappe.db.sql("""
            INSERT INTO `tabworkbench_block` 
            (name, creation, modified, modified_by, owner, docstatus, 
             block_id, type, workbench_page, parent_block, properties, position, is_deleted)
            VALUES 
            (%s, NOW(), NOW(), %s, %s, 0, 
             %s, %s, %s, %s, %s, %s, 0)
        """, (
            final_block_id,          # Name (PK)
            frappe.session.user,
            frappe.session.user,
            final_block_id,          # Block ID field
            block_type,
            page,
            parent_block if parent_block else None,
            json.dumps(properties),
            int(position) if position else 0
        ))
        
        frappe.db.commit()
        
        return frappe.db.get_value('workbench_block', final_block_id, '*', as_dict=True)
        
    except Exception as e:
        frappe.log_error(f"Create Block Error: {str(e)}")
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
            fields=['name', 'type', 'properties', 'position', 'parent_block', 'block_id'],
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
        
        if 'type' in updates:
            frappe.db.set_value('workbench_block', block_id, 'type', updates['type'])
        
        frappe.db.commit()
        
        # Fetch updated block
        block_data = frappe.db.get_value('workbench_block', 
            {'name': block_id},
            ['name', 'block_id', 'type', 'workbench_page', 'parent_block', 'properties', 'position'],
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
            {'name': block_id},
            ['name', 'block_id', 'type', 'workbench_page', 'parent_block', 'properties', 'position'],
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
