"""
Workbench Realtime API
Uses Frappe's publish_realtime to broadcast updates via socket.io
"""
import frappe
from frappe import whitelist
import json


@whitelist(allow_guest=False)
def join_page_room(page_id: str):
    """
    API endpoint to join a page-specific room.
    
    Note: Frappe's socket.io server handles room membership automatically
    when publish_realtime is called with a room name. This endpoint serves
    as a way to track room membership and can be extended if custom handlers
    are added to Frappe's socket.io server.
    
    Args:
        page_id: The workbench page ID to join
        
    Returns:
        dict: Status of room join operation
    """
    import json
    import os
    try:
        # #region agent log
        log_data = {
            "location": "realtime_api.py:join_page_room",
            "message": "join_page_room called",
            "data": {
                "page_id": page_id,
                "user": frappe.session.user,
                "has_socketio": hasattr(frappe, 'publish_realtime'),
            },
            "timestamp": frappe.utils.now_datetime().timestamp(),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "D"
        }
        try:
            log_path = os.path.join(frappe.get_site_path(), '.cursor', 'debug.log')
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a') as f:
                f.write(json.dumps(log_data) + '\n')
        except:
            pass
        # #endregion
        
        room = get_workbench_page_room(page_id)
        # In the future, this could trigger a socket.io event to join the room
        # For now, room membership is handled automatically by Frappe when
        # publish_realtime is called with the room parameter
        return {
            "status": "success",
            "room": room,
            "message": "Room join request registered"
        }
    except Exception as e:
        frappe.log_error(f"Join page room error: {str(e)}")
        return {"status": "error", "error": str(e)}


@whitelist(allow_guest=False)
def leave_page_room(page_id: str):
    """
    API endpoint to leave a page-specific room.
    
    Args:
        page_id: The workbench page ID to leave
        
    Returns:
        dict: Status of room leave operation
    """
    try:
        room = get_workbench_page_room(page_id)
        # In the future, this could trigger a socket.io event to leave the room
        return {
            "status": "success",
            "room": room,
            "message": "Room leave request registered"
        }
    except Exception as e:
        frappe.log_error(f"Leave page room error: {str(e)}")
        return {"status": "error", "error": str(e)}


def get_workbench_page_room(page_id: str) -> str:
    """
    Get room name for workbench page.
    
    Uses page-specific rooms so only users viewing the same page
    receive updates for that page. Clients must explicitly join
    these rooms via the workbench:join_page event.
    """
    return f"workbench_page:{page_id}"


@whitelist(allow_guest=True)
def process_batch_with_realtime(page_id: str, operations: str):
    """
    Process batch operations and broadcast via Frappe realtime.
    
    Args:
        page_id: The workbench page ID
        operations: JSON string of operations to process
        
    Returns:
        dict: Status and results of operations
    """
    from workbench_react.api.block_api import (
        create_workbench_block,
        update_workbench_block,
        move_workbench_block,
        delete_workbench_block_cascade
    )
    
    try:
        if isinstance(operations, str):
            operations = json.loads(operations)
        
        results = []
        for op in operations:
            op_type = op.get('op')
            try:
                if op_type == 'set':
                    result = create_workbench_block(
                        page=page_id,
                        block_type=op.get('type', 'paragraph'),
                        position=op.get('position', 0),
                        parent_block=op.get('parentId'),
                        properties=op.get('properties', {})
                    )
                    results.append(result)
                elif op_type == 'update':
                    result = update_workbench_block(
                        block_id=op.get('id'),
                        updates={
                            'properties': op.get('properties', {}),
                            'type': op.get('type')
                        }
                    )
                    results.append(result)
                elif op_type == 'listAfter':
                    result = move_workbench_block(
                        block_id=op.get('id'),
                        new_parent_id=op.get('parentId'),
                        new_position=op.get('position', 0)
                    )
                    results.append(result)
                elif op_type == 'delete':
                    result = delete_workbench_block_cascade(op.get('id'))
                    results.append(result)
                else:
                    results.append({'error': f'Unknown operation type: {op_type}'})
            except Exception as e:
                frappe.log_error(f"Operation {op_type} failed: {str(e)}")
                results.append({'error': str(e)})
        
        # Broadcast to all clients in page room via Frappe realtime
        room = get_workbench_page_room(page_id)
        frappe.publish_realtime(
            event="workbench:broadcast",
            message={
                "type": "broadcast",
                "pageId": page_id,
                "operations": operations,
                "result": {"status": "success", "results": results},
                "userId": frappe.session.user,
                "timestamp": frappe.utils.now_datetime().timestamp()
            },
            room=room,
            after_commit=True
        )
        
        return {"status": "success", "results": results}
    except Exception as e:
        frappe.log_error(f"Batch processing error: {str(e)}")
        return {"status": "error", "error": str(e)}


@whitelist(allow_guest=True)
def load_page_state(page_id: str):
    """
    Load page state and broadcast via realtime.
    
    Args:
        page_id: The workbench page ID
        
    Returns:
        dict: Page state with blocks
    """
    from workbench_react.api.block_api import get_block_tree
    import os
    import json
    
    try:
        # #region agent log
        log_data = {
            "location": "realtime_api.py:load_page_state",
            "message": "load_page_state called - testing publish_realtime",
            "data": {
                "page_id": page_id,
                "user": frappe.session.user if hasattr(frappe, 'session') else None,
                "has_publish_realtime": hasattr(frappe, 'publish_realtime'),
            },
            "timestamp": frappe.utils.now_datetime().timestamp(),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "C"
        }
        try:
            log_path = os.path.join(frappe.get_site_path(), '.cursor', 'debug.log')
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a') as f:
                f.write(json.dumps(log_data) + '\n')
        except:
            pass
        # #endregion
        
        blocks = get_block_tree(page_id)
        
        # Convert blocks to page state format
        block_map = {}
        root_blocks = []
        
        for block in blocks:
            block_id = block.get('block_id') or block.get('name')
            block_map[block_id] = block
            
            if not block.get('parent_block'):
                root_blocks.append(block)
        
        page_state = {
            "status": "success",
            "rootBlocks": root_blocks,
            "blockMap": block_map
        }
        
        # Broadcast page state via realtime
        room = get_workbench_page_room(page_id)
        frappe.publish_realtime(
            event="workbench:page_state",
            message={
                "type": "page_state",
                "pageId": page_id,
                "data": page_state,
                "timestamp": frappe.utils.now_datetime().timestamp()
            },
            room=room
        )
        
        return page_state
    except Exception as e:
        frappe.log_error(f"Load page state error: {str(e)}")
        return {"status": "error", "error": str(e)}


@whitelist(allow_guest=True)
def update_presence(page_id: str, block_id: str = None, position: int = 0):
    """
    Update user presence and broadcast to other users.
    
    Args:
        page_id: The workbench page ID
        block_id: Currently selected block ID
        position: Cursor position
        
    Returns:
        dict: Status
    """
    try:
        room = get_workbench_page_room(page_id)
        frappe.publish_realtime(
            event="workbench:presence_update",
            message={
                "type": "presence_update",
                "pageId": page_id,
                "userId": frappe.session.user,
                "blockId": block_id,
                "position": position,
                "timestamp": frappe.utils.now_datetime().timestamp()
            },
            room=room
        )
        
        return {"status": "success"}
    except Exception as e:
        frappe.log_error(f"Update presence error: {str(e)}")
        return {"status": "error", "error": str(e)}
