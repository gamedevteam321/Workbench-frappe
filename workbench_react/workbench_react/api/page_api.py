import frappe
from frappe import whitelist
import json
import uuid


@whitelist(allow_guest=True)
def create_workbench_page(title, workbench=None, workspace_id=None, icon=None, cover_image=None, owner_id=None):
    """Create a new page
    
    Args:
        title: Page title (required)
        workbench: Workbench/workspace ID (deprecated, use workspace_id)
        workspace_id: Workspace ID (preferred over workbench)
        icon: Page icon (optional)
        cover_image: Cover image (optional)
        owner_id: Owner ID (optional, defaults to current user)
    """
    if not owner_id:
        owner_id = frappe.session.user
    
    # Use workspace_id if provided, otherwise fall back to workbench parameter
    workspace = workspace_id or workbench
    
    if not workspace:
        frappe.throw("Either 'workbench' or 'workspace_id' parameter is required")
    
    # Validate workspace exists
    if not frappe.db.exists('workbench', workspace):
        frappe.throw(f"Workspace '{workspace}' does not exist")
    
    # Generate UUID-based name (similar to workspace) to prevent duplicate name conflicts
    unique_name = f"workbench-page-{uuid.uuid4().hex[:8]}"
    
    # Default title if empty
    page_title = title or 'New Page'
    
    page = frappe.get_doc({
        'doctype': 'workbench_page',
        'title': page_title,
        'icon': icon or '📄',
        'cover_image': cover_image,
        'workbench': workspace,  # Link to workspace/workbench
        'owner_id': owner_id
    })
    
    # Set name explicitly and prevent autoname from running
    page.flags.name_set = True
    page.name = unique_name
    
    page.insert(ignore_permissions=True)
    
    # Ensure title is preserved (autoname might have overwritten it)
    if page.title != page_title:
        page.title = page_title
        page.save(ignore_permissions=True)
    
    frappe.db.commit()
    page.reload()  # Ensure we have the latest data
    
    page_dict = page.as_dict()
    
    # Explicitly ensure title is in the response (safeguard)
    if 'title' not in page_dict or not page_dict.get('title'):
        page_dict['title'] = page_title
    
    # Broadcast page creation via realtime
    # Broadcast to user room for page list updates
    frappe.publish_realtime(
        event="workbench:page_created",
        message={
            "type": "page_created",
            "page": page_dict,
            "timestamp": frappe.utils.now_datetime().timestamp()
        },
        room=f"user:{frappe.session.user}",
        after_commit=True
    )
    
    return page_dict


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
    page_dict = page.as_dict()
    
    # Broadcast page update via realtime
    # Broadcast to user room for page list updates
    frappe.publish_realtime(
        event="workbench:page_updated",
        message={
            "type": "page_updated",
            "page": page_dict,
            "timestamp": frappe.utils.now_datetime().timestamp()
        },
        room=f"user:{frappe.session.user}",
        after_commit=True
    )
    
    # Also broadcast to page-specific room for users viewing this page
    from workbench_react.api.realtime_api import get_workbench_page_room
    page_room = get_workbench_page_room(page_id)
    frappe.publish_realtime(
        event="workbench:page_updated",
        message={
            "type": "page_updated",
            "page": page_dict,
            "timestamp": frappe.utils.now_datetime().timestamp()
        },
        room=page_room,
        after_commit=True
    )
    
    return page_dict


@whitelist(allow_guest=True)  # ← Add this
def delete_workbench_page(page_id=None, **kwargs):
    """Delete a page and all its blocks"""
    import json
    import os
    
    # Ensure log directory exists
    log_dir = os.path.join(os.path.expanduser('~'), 'frappe-bench', '.cursor')
    try:
        os.makedirs(log_dir, exist_ok=True)
    except:
        pass
    log_path = os.path.join(log_dir, 'debug.log')
    
    # #region agent log
    try:
        with open(log_path, 'a') as f:
            f.write(json.dumps({"location":"page_api.py:delete_workbench_page:entry","message":"Function entry","data":{"page_id_param":page_id,"form_dict_keys":list(frappe.form_dict.keys()) if hasattr(frappe, 'form_dict') and frappe.form_dict else [],"form_dict_page_id":frappe.form_dict.get('page_id') if hasattr(frappe, 'form_dict') and frappe.form_dict else None},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + "\n")
    except Exception as log_err:
        # Log to stderr if file logging fails
        import sys
        print(f"[DEBUG LOG ERROR] {log_err}", file=sys.stderr)
    # #endregion
    
    # Handle parameter from request body (Frappe API)
    # Frappe passes parameters via form_dict for POST requests
    # Try multiple ways to get page_id
    if not page_id:
        # Try from kwargs first (Frappe may pass it this way)
        page_id = kwargs.get('page_id')
    if not page_id:
        # Try from form_dict
        if hasattr(frappe, 'form_dict') and frappe.form_dict:
            page_id = frappe.form_dict.get('page_id')
    
    # #region agent log
    try:
        with open(log_path, 'a') as f:
            f.write(json.dumps({"location":"page_api.py:delete_workbench_page:after_extract","message":"After parameter extraction","data":{"page_id":page_id,"is_none":page_id is None,"is_empty":not page_id if page_id else True},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"A"}) + "\n")
    except Exception as log_err:
        import sys
        print(f"[DEBUG LOG ERROR] {log_err}", file=sys.stderr)
    # #endregion
    
    if not page_id:
        frappe.throw("page_id is required", frappe.ValidationError)
    
    # Get page info before deletion for broadcasting
    try:
        page = frappe.get_doc('workbench_page', page_id)
        workbench_id = page.workbench
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"location":"page_api.py:delete_workbench_page:page_found","message":"Page found","data":{"page_id":page_id,"workbench_id":workbench_id},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + "\n")
        except: pass
        # #endregion
    except frappe.DoesNotExistError as e:
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"location":"page_api.py:delete_workbench_page:page_not_found","message":"Page not found","data":{"page_id":page_id,"error":str(e)},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + "\n")
        except: pass
        # #endregion
        frappe.throw(f"Page {page_id} not found", frappe.DoesNotExistError)
    except Exception as e:
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"location":"page_api.py:delete_workbench_page:page_get_error","message":"Error getting page","data":{"page_id":page_id,"error":str(e),"error_type":type(e).__name__},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"B"}) + "\n")
        except: pass
        # #endregion
        raise
    
    # Delete all blocks for this page first (recursively)
    # This prevents LinkExistsError
    try:
        blocks = frappe.get_all('workbench_block', 
            filters={'workbench_page': page_id}, 
            fields=['name']
        )
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"location":"page_api.py:delete_workbench_page:blocks_found","message":"Blocks found","data":{"page_id":page_id,"block_count":len(blocks),"block_names":[b['name'] for b in blocks]},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + "\n")
        except: pass
        # #endregion
        
        # Delete blocks recursively (handles parent-child relationships)
        for i, block in enumerate(blocks):
            try:
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({"location":"page_api.py:delete_workbench_page:deleting_block","message":"Deleting block","data":{"page_id":page_id,"block_name":block['name'],"block_index":i,"total_blocks":len(blocks)},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + "\n")
                except: pass
                # #endregion
                _delete_block_recursive(block.name)
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({"location":"page_api.py:delete_workbench_page:block_deleted","message":"Block deleted successfully","data":{"page_id":page_id,"block_name":block['name']},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + "\n")
                except: pass
                # #endregion
            except Exception as e:
                # #region agent log
                try:
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({"location":"page_api.py:delete_workbench_page:block_delete_error","message":"Error deleting block","data":{"page_id":page_id,"block_name":block['name'],"error":str(e),"error_type":type(e).__name__},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + "\n")
                except: pass
                # #endregion
                raise
    except Exception as e:
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"location":"page_api.py:delete_workbench_page:blocks_error","message":"Error processing blocks","data":{"page_id":page_id,"error":str(e),"error_type":type(e).__name__},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + "\n")
        except: pass
        # #endregion
        raise
    
    # Now delete the page
    try:
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"location":"page_api.py:delete_workbench_page:deleting_page","message":"Deleting page","data":{"page_id":page_id},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + "\n")
        except: pass
        # #endregion
        frappe.delete_doc('workbench_page', page_id, ignore_permissions=True)
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"location":"page_api.py:delete_workbench_page:page_deleted","message":"Page deleted successfully","data":{"page_id":page_id},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + "\n")
        except: pass
        # #endregion
    except Exception as e:
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"location":"page_api.py:delete_workbench_page:page_delete_error","message":"Error deleting page","data":{"page_id":page_id,"error":str(e),"error_type":type(e).__name__},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"D"}) + "\n")
        except: pass
        # #endregion
        raise
    
    # Broadcast page deletion via realtime
    # Broadcast to user room for page list updates
    frappe.publish_realtime(
        event="workbench:page_deleted",
        message={
            "type": "page_deleted",
            "pageId": page_id,
            "workbench": workbench_id,
            "timestamp": frappe.utils.now_datetime().timestamp()
        },
        room=f"user:{frappe.session.user}",
        after_commit=True
    )
    
    # Also broadcast to page-specific room for users viewing this page
    from workbench_react.api.realtime_api import get_workbench_page_room
    page_room = get_workbench_page_room(page_id)
    frappe.publish_realtime(
        event="workbench:page_deleted",
        message={
            "type": "page_deleted",
            "pageId": page_id,
            "workbench": workbench_id,
            "timestamp": frappe.utils.now_datetime().timestamp()
        },
        room=page_room,
        after_commit=True
    )
    
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
    page_dict = page.as_dict()
    
    # Broadcast page archive via realtime (treat as update)
    frappe.publish_realtime(
        event="workbench:page_updated",
        message={
            "type": "page_updated",
            "page": page_dict,
            "timestamp": frappe.utils.now_datetime().timestamp()
        },
        room=f"user:{frappe.session.user}",
        after_commit=True
    )
    
    return page_dict


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
    import json
    import os
    log_path = os.path.join(os.path.expanduser('~'), 'frappe-bench', '.cursor', 'debug.log')
    
    try:
        children = frappe.get_all('workbench_block', filters={'parent_block': block_id}, fields=['name'])
        for child in children:
            _delete_block_recursive(child.name)
        frappe.delete_doc('workbench_block', block_id, ignore_permissions=True)
    except Exception as e:
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({"location":"page_api.py:_delete_block_recursive:error","message":"Error in recursive block delete","data":{"block_id":block_id,"error":str(e),"error_type":type(e).__name__},"timestamp":frappe.utils.now_datetime().timestamp(),"sessionId":"debug-session","runId":"run1","hypothesisId":"C"}) + "\n")
        except: pass
        # #endregion
        raise


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
