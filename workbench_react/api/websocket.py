import frappe
import json
from frappe.utils import cint
from frappe import whitelist


@whitelist()
def load_page_state(page_id):
    """
    Load the complete page state with all blocks.
    Normalizes data format for frontend consumption.
    """
    try:
        # Fetch page
        page = frappe.get_doc('Workbench Page', page_id)
        
        # Fetch all blocks for this page
        blocks_data = frappe.db.sql("""
            SELECT name, workbench_page, block_type, content, properties, 
                   prev_id, next_id, position, parent_block, 
                   creation, modified, owner
            FROM `tabworkbench_block` 
            WHERE workbench_page = %s AND is_deleted = 0
            ORDER BY position ASC
        """, (page_id,), as_dict=True)
        
        # Normalize blocks data
        normalized_blocks = []
        first_block_id = None
        last_block_id = None
        
        for block in blocks_data:
            # Track first and last blocks
            if first_block_id is None and not block.get('prev_id'):
                first_block_id = block.get('name')
            if not block.get('next_id'):
                last_block_id = block.get('name')
            
            # Parse JSON fields safely
            try:
                content = json.loads(block.get('content') or '{}') if block.get('content') else {}
            except:
                content = {}
            
            try:
                properties = json.loads(block.get('properties') or '{}') if block.get('properties') else {}
            except:
                properties = {}
            
            # Normalize the block
            normalized_block = {
                'id': block.get('name'),
                'type': block.get('block_type') or 'paragraph',
                'workbenchPage': block.get('workbench_page'),
                'content': content,
                'properties': properties,
                'prevId': block.get('prev_id'),
                'nextId': block.get('next_id'),
                'position': block.get('position'),
                'parentBlock': block.get('parent_block'),
                'owner': block.get('owner'),
                'createdAt': str(block.get('creation', '')),
                'updatedAt': str(block.get('modified', ''))
            }
            normalized_blocks.append(normalized_block)
        
        # Normalize page data
        normalized_page = {
            'id': page.name,
            'title': page.title,
            'icon': page.get('icon', '📄'),
            'blockCount': len(normalized_blocks),
            'firstBlockId': first_block_id,
            'lastBlockId': last_block_id,
            'isArchived': cint(page.get('is_archived', 0)),
            'createdAt': str(page.creation),
            'updatedAt': str(page.modified)
        }
        
        return {
            'status': 'success',
            'page': normalized_page,
            'blocks': normalized_blocks
        }
        
    except frappe.DoesNotExistError:
        return {
            'status': 'error',
            'message': f'Page {page_id} not found'
        }
    except Exception as e:
        frappe.log_error(f'Error in load_page_state: {str(e)}', 'Workbench API')
        return {
            'status': 'error',
            'message': str(e)
        }


@whitelist()
def create_block(page_id, block_type='paragraph', position=None, content=None, properties=None):
    """Create a new block"""
    try:
        # Get max position if not provided
        if position is None:
            max_pos = frappe.db.sql(
                "SELECT MAX(position) as max_pos FROM `tabworkbench_block` WHERE workbench_page = %s",
                (page_id,),
                as_dict=True
            )
            position = (max_pos['max_pos'] or 0) + 1 if max_pos and max_pos['max_pos'] else 0
        
        # Create block
        block = frappe.get_doc({
            'doctype': 'Workbench Block',
            'workbench_page': page_id,
            'block_type': block_type,
            'position': position,
            'content': json.dumps(content or {}),
            'properties': json.dumps(properties or {}),
            'prev_id': None,
            'next_id': None
        })
        block.insert(ignore_permissions=True)
        
        return {
            'status': 'success',
            'block': {
                'id': block.name,
                'type': block.block_type,
                'content': content or {},
                'properties': properties or {},
                'position': position,
                'createdAt': str(block.creation),
                'updatedAt': str(block.modified)
            }
        }
    except Exception as e:
        frappe.log_error(f'Error creating block: {str(e)}', 'Workbench API')
        return {
            'status': 'error',
            'message': str(e)
        }


@whitelist()
def update_block(block_id, **kwargs):
    """Update a block's content and properties"""
    try:
        block = frappe.get_doc('Workbench Block', block_id)
        
        # Update allowed fields
        if 'block_type' in kwargs:
            block.block_type = kwargs['block_type']
        
        if 'content' in kwargs:
            content = kwargs['content']
            block.content = json.dumps(content) if isinstance(content, dict) else content
        
        if 'properties' in kwargs:
            properties = kwargs['properties']
            block.properties = json.dumps(properties) if isinstance(properties, dict) else properties
        
        if 'position' in kwargs:
            block.position = kwargs['position']
        
        if 'prev_id' in kwargs:
            block.prev_id = kwargs['prev_id']
        
        if 'next_id' in kwargs:
            block.next_id = kwargs['next_id']
        
        block.save(ignore_permissions=True)
        
        return {
            'status': 'success',
            'message': 'Block updated'
        }
    except Exception as e:
        frappe.log_error(f'Error updating block: {str(e)}', 'Workbench API')
        return {
            'status': 'error',
            'message': str(e)
        }


@whitelist()
def delete_block(block_id):
    """Delete a block"""
    try:
        frappe.delete_doc('Workbench Block', block_id, ignore_permissions=True)
        
        return {
            'status': 'success',
            'message': 'Block deleted'
        }
    except Exception as e:
        frappe.log_error(f'Error deleting block: {str(e)}', 'Workbench API')
        return {
            'status': 'error',
            'message': str(e)
        }


@whitelist()
def reorder_blocks(page_id, block_ids):
    """Reorder blocks and update their linked-list pointers"""
    try:
        # Update position for each block
        for position, block_id in enumerate(block_ids):
            block = frappe.get_doc('Workbench Block', block_id)
            block.position = position
            
            # Update linked-list pointers
            block.prev_id = block_ids[position - 1] if position > 0 else None
            block.next_id = block_ids[position + 1] if position < len(block_ids) - 1 else None
            
            block.save(ignore_permissions=True)
        
        return {
            'status': 'success',
            'message': 'Blocks reordered'
        }
    except Exception as e:
        frappe.log_error(f'Error reordering blocks: {str(e)}', 'Workbench API')
        return {
            'status': 'error',
            'message': str(e)
        }
from datetime import datetime
from typing import Dict, List, Optional     

@whitelist()
def get_workbench_page(page_id):
    """Fetch workbench page details"""
    try:
        page = frappe.get_doc('Workbench Page', page_id)
        return {
            'id': page.name,
            'title': page.title,
            'icon': page.get('icon', '📄'),
            'isArchived': cint(page.get('is_archived', 0)),
            'createdAt': str(page.creation),
            'updatedAt': str(page.modified)
        }
    except frappe.DoesNotExistError:
        return None
class UserPresence: