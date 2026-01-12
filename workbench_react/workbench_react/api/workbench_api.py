import frappe
from frappe import whitelist
from frappe.utils.response import build_response
import json
import uuid
import os
from frappe.utils import now_datetime

# #region agent log - Track module load
try:
    import json as json_module
    import time
    log_path = '/home/vrushali/frappe-bench/.cursor/debug.log'
    with open(log_path, 'a', encoding='utf-8') as f:
        log_entry = json_module.dumps({
            "sessionId": "debug-session",
            "runId": "initial",
            "hypothesisId": "B",
            "location": "workbench_api.py:module_load",
            "message": "workbench_api module loaded",
            "data": {
                "has_frappe": hasattr(frappe, '__name__'),
                "has_whitelist": hasattr(frappe, 'whitelist'),
                "whitelist_imported": 'whitelist' in globals(),
                "whitelisted_exists": hasattr(frappe, 'whitelisted'),
                "whitelisted_count": len(frappe.whitelisted) if hasattr(frappe, 'whitelisted') else 0
            },
            "timestamp": int(time.time() * 1000)
        }) + '\n'
        f.write(log_entry)
except:
    pass
# #endregion


# ============================================
# HELPER FUNCTIONS
# ============================================

def check_workbench_permission(workbench, current_user=None):
	"""Check if current user has permission to access/modify a workbench"""
	if current_user is None:
		current_user = frappe.session.user
	return workbench.owner_id == current_user or current_user == 'Administrator'

def success_response(data):
	"""Return a standardized success response"""
	return {
		'status': 'success',
		'data': data
	}

def error_response(error_message, log_error=None):
	"""Return a standardized error response"""
	if log_error:
		frappe.logger().error(log_error)
	return {
		'status': 'error',
		'error': str(error_message)
	}

def handle_api_error(func_name, error, rollback=False):
	"""Standardized error handling for API functions"""
	if rollback:
		frappe.db.rollback()
	frappe.logger().error(f"Error in {func_name}: {str(error)}")
	return error_response(str(error), f"Error in {func_name}: {str(error)}")

# ============================================
# CSRF TOKEN
# ============================================

@whitelist(allow_guest=True)  # Allow guest to get token for their session
def get_csrf_token():
	"""Get CSRF token for current session"""
	from frappe.sessions import get_csrf_token as frappe_get_csrf_token
	return frappe_get_csrf_token()

# ============================================
# INITIALIZATION & DEFAULTS
# ============================================


@whitelist(allow_guest=False)
def ensure_default_workbench():
	"""Ensure a default workbench exists for the current user"""
	current_user = frappe.session.user
	
	# Require authentication
	if not current_user or current_user == 'Guest':
		frappe.throw("User must be logged in", frappe.PermissionError)
	
	try:
		# Check if user already has a workbench
		existing = frappe.get_list(
			'workbench',
			filters={'owner_id': current_user},
			fields=['name', 'title', 'slug'],
			limit=1
		)
		
		if existing:
			workbench_doc = frappe.get_doc('workbench', existing[0].name)
			# Return data directly - Frappe will wrap it in 'message'
			return workbench_doc.as_dict()
		
		# Create default workbench if none exists
		workbench = frappe.get_doc({
			'doctype': 'workbench',
			'title': f"{current_user}'s Workbench",
			'slug': f"{current_user.lower().replace('@', '-').replace('.', '-')}-workbench",
			'owner_id': current_user
		})
		workbench.insert(ignore_permissions=True)
		frappe.db.commit()
		
		# Return data directly - Frappe will wrap it in 'message'
		return workbench.as_dict()
	
	except Exception as e:
		frappe.log_error(f"Error ensuring default workbench: {str(e)}")
		frappe.throw(f"Failed to ensure default workbench: {str(e)}")


# ============================================
# WORKBENCH CRUD
# ============================================


# Note: Debug instrumentation will be added after function definitions

@whitelist(allow_guest=True)  # Allow guest users to create workspaces
def create_workbench(title, slug=None, owner_id=None, icon=None):
	"""Create a new workbench"""
	try:
		current_user = frappe.session.user
		
		# For guest users, always set owner_id to Guest
		# For authenticated users, use provided owner_id or current_user
		if not owner_id:
			owner_id = current_user
		
		# Validate permissions - only allow setting owner_id to current_user or Administrator
		if owner_id != current_user and current_user != 'Administrator':
			return error_response('Permission denied')
		
		if not slug:
			slug = title.lower().replace(' ', '-')
		
		# Generate unique name to avoid duplicate key errors
		# Since autoname is "field:title", we need to ensure title is unique
		# or set a unique name explicitly
		base_title = title
		unique_title = base_title
		
		# For "New Workspace", always use it as-is without appending numbers
		# Use UUID-based name to ensure uniqueness while keeping title exactly as "New Workspace"
		if base_title == "New Workspace":
			# Generate unique name using UUID, but keep title exactly as "New Workspace"
			unique_name = f"new-workspace-{str(uuid.uuid4())[:8]}"
			# Don't put 'name' in workbench_data - set it directly on the doc object after creation
			# This prevents Frappe from processing it through autoname
			workbench_data = {
				'doctype': 'workbench',
				'title': base_title,  # Keep title exactly as "New Workspace" (no numbers)
				'slug': slug,
				'owner_id': owner_id
			}
			# Store unique_name for later use
			workbench_data['_unique_name'] = unique_name
		else:
			# For other titles, check for duplicates and append numbers if needed
			unique_title = base_title
			counter = 1
			while frappe.db.exists('workbench', unique_title):
				unique_title = f"{base_title} {counter}"
				counter += 1
				# Safety limit to prevent infinite loop
				if counter > 1000:
					# Fallback to UUID-based name if too many duplicates
					unique_title = f"{base_title}-{str(uuid.uuid4())[:8]}"
					break
			
			# Prepare workbench data
			workbench_data = {
				'doctype': 'workbench',
				'title': unique_title,  # Use unique title to avoid duplicate name errors
				'slug': slug,
				'owner_id': owner_id
			}
		
		# Add icon if provided
		if icon:
			workbench_data['icon'] = icon
		
		# Try to insert the workbench
		# Handle potential race condition where duplicate is created between check and insert
		max_retries = 3
		retry_count = 0
		
		while retry_count < max_retries:
			try:
				workbench = frappe.get_doc(workbench_data)
				# For "New Workspace", prevent autoname from overriding our UUID-based name
				if base_title == "New Workspace" and '_unique_name' in workbench_data:
					# Set the name and flag BEFORE insert to prevent autoname from running
					unique_name = workbench_data['_unique_name']
					workbench.name = unique_name  # Set name first
					workbench.flags.name_set = True  # Tell Frappe name is already set (prevents set_new_name from running)
					# Explicitly set title to ensure it's saved correctly
					workbench.title = base_title  # Ensure title is "New Workspace"
					# #region agent log
					try:
						import json as json_module
						import time
						log_path = '/home/vrushali/frappe-bench/.cursor/debug.log'
						with open(log_path, 'a', encoding='utf-8') as f:
							log_entry = json_module.dumps({
								"location": "workbench_api.py:create_workbench-before-insert",
								"message": "Before insert - New Workspace with UUID name",
								"data": {
									"unique_name": workbench_data.get('_unique_name', 'N/A'),
									"title": base_title,
									"workbench_name": workbench.name,
									"flags_name_set": getattr(workbench.flags, 'name_set', False),
									"has_flags": hasattr(workbench, 'flags'),
									"hypothesisId": "D"
								},
								"timestamp": int(time.time() * 1000),
								"sessionId": "debug-session",
								"runId": "run1"
							}) + '\n'
							f.write(log_entry)
					except:
						pass
					# #endregion
				workbench.insert(ignore_permissions=True)
				# After insert, if title was overwritten (which happens with autoname="field:title"), restore it
				if base_title == "New Workspace" and workbench.title != base_title:
					workbench.title = base_title
					workbench.save(ignore_permissions=True)
				frappe.db.commit()
				# Reload workbench from DB to ensure all fields are fresh before returning
				workbench.reload()
				# #region agent log
				if base_title == "New Workspace":
					try:
						import json as json_module
						import time
						log_path = '/home/vrushali/frappe-bench/.cursor/debug.log'
						# Get fresh data from reloaded workbench
						as_dict_result = workbench.as_dict()
						with open(log_path, 'a', encoding='utf-8') as f:
							log_entry = json_module.dumps({
								"location": "workbench_api.py:create_workbench-after-insert",
								"message": "After insert - New Workspace created",
								"data": {
									"workbench_name": workbench.name,
									"workbench_title_after_reload": workbench.title,
									"title_matches": workbench.title == "New Workspace",
									"name_is_uuid": workbench.name.startswith("new-workspace-") if workbench.name else False,
									"as_dict_title": as_dict_result.get('title'),
									"as_dict_name": as_dict_result.get('name'),
									"as_dict_keys": list(as_dict_result.keys())[:10],
									"title_restored_after_insert": workbench.title == base_title,
									"hypothesisId": "D"
								},
								"timestamp": int(time.time() * 1000),
								"sessionId": "debug-session",
								"runId": "run1"
							}) + '\n'
							f.write(log_entry)
					except:
						pass
				# #endregion
				# Return the workbench with fresh data from DB (already reloaded above)
				workbench_dict = workbench.as_dict()
				# Explicitly ensure title is in the response (safeguard)
				if 'title' not in workbench_dict or not workbench_dict.get('title'):
					workbench_dict['title'] = base_title
				return success_response(workbench_dict)
			except Exception as insert_error:
				# Check if it's a duplicate key error (primary key violation)
				is_duplicate = False
				if hasattr(frappe.db, 'is_primary_key_violation'):
					is_duplicate = frappe.db.is_primary_key_violation(insert_error)
				else:
					# Fallback: check error string
					error_str = str(insert_error).lower()
					is_duplicate = 'duplicate' in error_str or 'primary' in error_str or 'integrity' in error_str or '1062' in error_str
				
				if is_duplicate:
					# For "New Workspace", regenerate UUID name
					if base_title == "New Workspace":
						retry_count += 1
						if retry_count >= max_retries:
							# Last retry - use longer UUID
							unique_name = f"new-workspace-{str(uuid.uuid4())}"
							workbench_data['_unique_name'] = unique_name
							workbench = frappe.get_doc(workbench_data)
							workbench.name = unique_name  # Set name first
							workbench.flags.name_set = True  # Prevent autoname override
							workbench.title = base_title  # Ensure title is "New Workspace"
							workbench.insert(ignore_permissions=True)
							frappe.db.commit()
							workbench.reload()  # Reload to get fresh data
							return success_response(workbench.as_dict())
						else:
							# Regenerate UUID name
							unique_name = f"new-workspace-{str(uuid.uuid4())[:8]}"
							workbench_data['_unique_name'] = unique_name
					else:
						retry_count += 1
						if retry_count >= max_retries:
							# Last retry - use UUID to guarantee uniqueness
							unique_title = f"{base_title}-{str(uuid.uuid4())[:8]}"
							workbench_data['title'] = unique_title
							workbench = frappe.get_doc(workbench_data)
							workbench.insert(ignore_permissions=True)
							frappe.db.commit()
							workbench.reload()  # Reload to get fresh data
							return success_response(workbench.as_dict())
						else:
							# Try with incremented counter
							unique_title = f"{base_title} {counter}"
							counter += 1
							workbench_data['title'] = unique_title
				else:
					# For other errors, re-raise immediately
					raise
		
		# This should not be reached if all paths return properly, but kept as fallback
		# Reload workbench to ensure fresh data
		if 'workbench' in locals():
			workbench.reload()
			return success_response(workbench.as_dict())
		else:
			# Should not happen, but handle edge case
			return error_response('Failed to create workbench')
	
	except Exception as e:
		return handle_api_error('create_workbench', e, rollback=True)

# #region agent log - Verify create_workbench whitelist registration after definition
try:
	import json as json_module
	import time
	log_path = '/home/vrushali/frappe-bench/.cursor/debug.log'
	func_id = id(create_workbench)
	in_whitelist = False
	wrapped_in_whitelist = False
	whitelisted_count = 0
	whitelist_ids = []
	if hasattr(frappe, 'whitelisted'):
		whitelisted_count = len(frappe.whitelisted)
		whitelist_ids = [id(f) for f in frappe.whitelisted[:30]]  # First 30 IDs
		in_whitelist = create_workbench in frappe.whitelisted
		if not in_whitelist and hasattr(create_workbench, '__wrapped__'):
			wrapped_in_whitelist = create_workbench.__wrapped__ in frappe.whitelisted
	with open(log_path, 'a', encoding='utf-8') as f:
		log_entry = json_module.dumps({
			"sessionId": "debug-session",
			"runId": "initial",
			"hypothesisId": "B",
			"location": "workbench_api.py:after_create_workbench_def",
			"message": "After create_workbench definition - whitelist check",
			"data": {
				"func_id": func_id,
				"func_name": create_workbench.__name__,
				"func_module": create_workbench.__module__,
				"in_whitelisted": in_whitelist,
				"wrapped_in_whitelisted": wrapped_in_whitelist,
				"whitelisted_count": whitelisted_count,
				"func_id_in_whitelist_ids": func_id in whitelist_ids,
				"has_wrapped": hasattr(create_workbench, '__wrapped__'),
				"whitelist_ids_sample": whitelist_ids[:10]  # First 10 for comparison
			},
			"timestamp": int(time.time() * 1000)
		}) + '\n'
		f.write(log_entry)
except:
	pass
# #endregion

# #region agent log - Patch frappe.get_attr to track method resolution
try:
	_original_get_attr = frappe.get_attr
	def _instrumented_get_attr(method_path):
		result = _original_get_attr(method_path)
		# Log when create_workbench is resolved
		if 'create_workbench' in method_path:
			try:
				import json as json_module
				import time
				log_path = '/home/vrushali/frappe-bench/.cursor/debug.log'
				result_id = id(result)
				in_whitelist = False
				if hasattr(frappe, 'whitelisted'):
					in_whitelist = result in frappe.whitelisted
					if not in_whitelist and hasattr(result, '__wrapped__'):
						in_whitelist = result.__wrapped__ in frappe.whitelisted
				with open(log_path, 'a', encoding='utf-8') as f:
					log_entry = json_module.dumps({
						"sessionId": "debug-session",
						"runId": "request-time",
						"hypothesisId": "D",
						"location": "workbench_api.py:get_attr_patch",
						"message": "frappe.get_attr resolved create_workbench",
						"data": {
							"method_path": method_path,
							"result_id": result_id,
							"result_name": result.__name__ if hasattr(result, '__name__') else 'unknown',
							"result_module": result.__module__ if hasattr(result, '__module__') else 'unknown',
							"in_whitelisted": in_whitelist,
							"has_wrapped": hasattr(result, '__wrapped__')
						},
						"timestamp": int(time.time() * 1000)
					}) + '\n'
					f.write(log_entry)
			except:
				pass
		return result
	frappe.get_attr = _instrumented_get_attr
except:
	pass
# #endregion


@whitelist(allow_guest=True)
def get_workbench(workbench_id):
	"""Get a workbench by ID"""
	try:
		workbench = frappe.get_doc('workbench', workbench_id)
		
		# Check permissions
		if not check_workbench_permission(workbench):
			return error_response('Permission denied')
		
		return success_response(workbench.as_dict())
	
	except Exception as e:
		return handle_api_error('get_workbench', e)


@whitelist(allow_guest=True)
def update_workbench(workbench_id, updates):
	"""Update a workbench"""
	try:
		workbench = frappe.get_doc('workbench', workbench_id)
		
		# Check permissions
		if not check_workbench_permission(workbench):
			return error_response('Permission denied')
		
		if isinstance(updates, str):
			updates = json.loads(updates)
		
		workbench.update(updates)
		workbench.save(ignore_permissions=True)
		
		return success_response(workbench.as_dict())
	
	except Exception as e:
		return handle_api_error('update_workbench', e)


@whitelist(allow_guest=True)
def delete_workbench(workbench_id):
	"""Delete a workbench and optionally cascade delete pages and blocks"""
	try:
		workbench = frappe.get_doc('workbench', workbench_id)
		
		# Check permissions
		if not check_workbench_permission(workbench):
			return error_response('Permission denied')
		
		# Optionally cascade delete pages and blocks
		# Get all pages in this workspace
		pages = frappe.get_list('workbench_page', 
			filters={'workbench': workbench_id, 'is_archived': 0},
			fields=['name']
		)
		
		# Soft delete pages (archive them) instead of hard delete
		for page in pages:
			try:
				page_doc = frappe.get_doc('workbench_page', page.name)
				page_doc.is_archived = 1
				page_doc.save(ignore_permissions=True)
			except Exception as e:
				# Log but continue - don't fail entire deletion
				frappe.log_error(f"Failed to archive page {page.name} during workspace deletion: {str(e)}")
		
		# Hard delete the workspace
		frappe.delete_doc('workbench', workbench_id, ignore_permissions=True)
		frappe.db.commit()
		
		return success_response({'id': workbench_id, 'pages_archived': len(pages)})
	
	except Exception as e:
		return handle_api_error('delete_workbench', e, rollback=True)


@whitelist(allow_guest=True)
def duplicate_workbench(workbench_id, new_title=None):
	"""Duplicate a workbench with all its pages and blocks"""
	try:
		# Get original workbench
		original_workbench = frappe.get_doc('workbench', workbench_id)
		
		# Check permissions
		if not check_workbench_permission(original_workbench):
			return error_response('Permission denied')
		
		# Generate new title
		if not new_title:
			base_title = original_workbench.title or 'Untitled Workspace'
			new_title = f"{base_title} Copy"
			# Ensure unique title
			counter = 1
			while frappe.db.exists('workbench', new_title):
				new_title = f"{base_title} Copy {counter}"
				counter += 1
				if counter > 1000:
					# Fallback to UUID-based name
					import uuid
					new_title = f"{base_title} Copy {str(uuid.uuid4())[:8]}"
					break
		
		# Create new workbench
		new_workbench_data = {
			'doctype': 'workbench',
			'title': new_title,
			'slug': new_title.lower().replace(' ', '-'),
			'owner_id': original_workbench.owner_id,
			'icon': original_workbench.icon
		}
		
		# Handle "New Workspace" title with UUID-based name
		if new_title == "New Workspace":
			import uuid
			unique_name = f"new-workspace-{str(uuid.uuid4())[:8]}"
			new_workbench_data['_unique_name'] = unique_name
		
		new_workbench = frappe.get_doc(new_workbench_data)
		
		# Set unique name if provided
		if '_unique_name' in new_workbench_data:
			new_workbench.name = new_workbench_data['_unique_name']
			new_workbench.flags.name_set = True
		
		new_workbench.insert(ignore_permissions=True)
		
		# Restore title if it was overwritten (for "New Workspace" case)
		if new_title == "New Workspace" and new_workbench.title != new_title:
			new_workbench.title = new_title
			new_workbench.save(ignore_permissions=True)
		
		frappe.db.commit()
		new_workbench.reload()
		
		# Get all pages from original workbench
		pages = frappe.get_list('workbench_page',
			filters={'workbench': workbench_id, 'is_archived': 0},
			fields=['name', 'title', 'icon', 'cover_image', 'order_index'],
			order_by='order_index'
		)
		
		# Map old page IDs to new page IDs for block parent references
		page_id_map = {}
		
		# Duplicate each page
		for page in pages:
			original_page = frappe.get_doc('workbench_page', page.name)
			
			# Create new page
			new_page_data = {
				'doctype': 'workbench_page',
				'title': original_page.title,
				'icon': original_page.icon,
				'cover_image': original_page.cover_image,
				'workbench': new_workbench.name,
				'owner_id': original_page.owner_id,
				'order_index': original_page.order_index
			}
			
			new_page = frappe.get_doc(new_page_data)
			new_page.insert(ignore_permissions=True)
			frappe.db.commit()
			
			# Store mapping
			page_id_map[page.name] = new_page.name
		
		# Duplicate all blocks for all pages
		for old_page_id, new_page_id in page_id_map.items():
			# Get all blocks for this page
			blocks = frappe.get_list('workbench_block',
				filters={'workbench_page': old_page_id, 'is_deleted': 0},
				fields=['name', 'block_type', 'properties', 'parent_block', 'order_index'],
				order_by='order_index'
			)
			
			# Map old block IDs to new block IDs for parent references
			block_id_map = {}
			
			# First pass: create all blocks without parent references
			for block in blocks:
				original_block = frappe.get_doc('workbench_block', block.name)
				
				new_block_data = {
					'doctype': 'workbench_block',
					'workbench_page': new_page_id,
					'block_type': original_block.block_type,
					'properties': original_block.properties,
					'order_index': original_block.order_index,
					'owner_id': original_block.owner_id
				}
				
				new_block = frappe.get_doc(new_block_data)
				new_block.insert(ignore_permissions=True)
				frappe.db.commit()
				
				# Store mapping
				block_id_map[block.name] = new_block.name
			
			# Second pass: update parent_block references
			for block in blocks:
				if block.parent_block and block.parent_block in block_id_map:
					new_block_id = block_id_map[block.name]
					new_block = frappe.get_doc('workbench_block', new_block_id)
					new_block.parent_block = block_id_map[block.parent_block]
					new_block.save(ignore_permissions=True)
			
			frappe.db.commit()
		
		frappe.db.commit()
		new_workbench.reload()
		
		return success_response(new_workbench.as_dict())
	
	except Exception as e:
		return handle_api_error('duplicate_workbench', e, rollback=True)


@whitelist(allow_guest=True)  # Allow guest access - function will handle guest users appropriately
def list_workbenches():
	"""Get all workbenches for current user"""
	try:
		current_user = frappe.session.user
		
		# Return workbenches for the current user (including Guest), excluding archived
		workbenches = frappe.get_list('workbench', 
			filters={'owner_id': current_user, 'is_archived': 0},
			fields=['name', 'title', 'slug', 'creation'],
			order_by='creation desc'
		)
		
		return success_response(workbenches)
	
	except Exception as e:
		return handle_api_error('list_workbenches', e)


@whitelist(allow_guest=True)
def archive_workbench(workbench_id):
	"""Archive a workbench"""
	try:
		workbench = frappe.get_doc('workbench', workbench_id)
		
		# Check permissions
		if not check_workbench_permission(workbench):
			return error_response('Permission denied')
		
		workbench.is_archived = 1
		workbench.save(ignore_permissions=True)
		
		return success_response(workbench.as_dict())
	
	except Exception as e:
		return handle_api_error('archive_workbench', e)


# ============================================
# PAGE CRUD
# ============================================


@whitelist(allow_guest=False)
def get_pages(workbench_id):
	"""Get all pages for a workbench"""
	try:
		pages = frappe.get_list(
			'workbench_page',
			filters={
				'workbench': workbench_id,
				'is_deleted': 0
			},
			fields=['name', 'title', 'slug', 'creation'],
			order_by='creation asc'
		)
		
		return success_response(pages)
	
	except Exception as e:
		return handle_api_error('get_pages', e)


@whitelist(allow_guest=False)
def create_page(workbench_id, title, slug=None):
	"""Create a new page"""
	try:
		if not slug:
			slug = title.lower().replace(' ', '-')
		
		page = frappe.get_doc({
			'doctype': 'workbench_page',
			'workbench': workbench_id,
			'title': title,
			'slug': slug,
			'is_deleted': 0
		})
		page.insert(ignore_permissions=True)
		
		return success_response(page.as_dict())
	
	except Exception as e:
		return handle_api_error('create_page', e)


# ============================================
# BLOCK CRUD
# ============================================


@whitelist(allow_guest=True)
def get_blocks(page_id):
	"""Get all blocks for a specific page"""
	try:
		if not page_id:
			return success_response([])
		
		blocks = frappe.get_list(
			'workbench_block',
			filters={
				'workbench_page': page_id,
				'is_deleted': 0
			},
			fields=[
				'name',
				'block_type',
				'workbench_page',
				'parent_block',
				'properties',
				'position'
			],
			order_by='position asc'
		)
		
		return success_response(blocks)
	
	except Exception as e:
		return handle_api_error('get_blocks', e)


@whitelist(allow_guest=True)
def create_block(workbench_page, parent_block='', block_type='paragraph', properties='{}', position=None):
	"""Create a new block"""
	try:
		# Get position if not provided
		if position is None:
			filters = {
				'workbench_page': workbench_page,
				'parent_block': parent_block or '',
				'is_deleted': 0
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
			'block_type': block_type,
			'workbench_page': workbench_page,
			'parent_block': parent_block or None,
			'properties': json.dumps(properties),
			'position': position,
			'is_deleted': 0
		})
		block.insert(ignore_permissions=True)
		
		# Update parent block's content field if this is a nested block
		if parent_block:
			try:
				parent = frappe.get_doc('workbench_block', parent_block)
				content = json.loads(parent.content) if parent.content else []
				if block.name not in content:
					content.append(block.name)
					parent.content = json.dumps(content)
					parent.save(ignore_permissions=True)
			except Exception as e:
				# Log but don't fail - parent update is optional
				frappe.log_error(f"Failed to update parent block content: {str(e)}")
		
		return success_response(block.as_dict())
	
	except Exception as e:
		return handle_api_error('create_block', e)


@whitelist(allow_guest=True)
def update_block(block_id, updates_json):
	"""Update a block's properties and other fields"""
	try:
		block = frappe.get_doc('workbench_block', block_id)
		
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
		
		return success_response(block.as_dict())
	
	except Exception as e:
		return handle_api_error('update_block', e)


@whitelist(allow_guest=True)
def delete_block(block_id):
	"""Soft delete a block"""
	try:
		block = frappe.get_doc('workbench_block', block_id)
		block.is_deleted = 1
		block.save(ignore_permissions=True)
		
		# Remove from parent's content field if nested
		if block.parent_block:
			try:
				parent = frappe.get_doc('workbench_block', block.parent_block)
				content = json.loads(parent.content) if parent.content else []
				if block.name in content:
					content.remove(block.name)
					parent.content = json.dumps(content)
					parent.save(ignore_permissions=True)
			except Exception as e:
				# Log but don't fail - parent update is optional
				frappe.log_error(f"Failed to update parent block content on delete: {str(e)}")
		
		return success_response({'block_id': block_id, 'name': block.name})
	
	except Exception as e:
		return handle_api_error('delete_block', e)


@whitelist(allow_guest=True)
def reorder_block(block_id, new_position):
	"""Update block position"""
	try:
		block = frappe.get_doc('workbench_block', block_id)
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
		                         fields=['name', 'position'],
		                         order_by='position')
		
		# Reorder positions
		if new_position > old_position:
			# Moving down - shift others up
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
		
		# Update parent's content field order if nested
		if block.parent_block:
			try:
				parent = frappe.get_doc('workbench_block', block.parent_block)
				content = json.loads(parent.content) if parent.content else []
				if block.name in content:
					content.remove(block.name)
					# Insert at new position
					sibling_names = [s.name for s in siblings if s.name != block.name]
					if new_position < len(sibling_names):
						sibling_names.insert(new_position, block.name)
					else:
						sibling_names.append(block.name)
					parent.content = json.dumps(sibling_names)
					parent.save(ignore_permissions=True)
			except Exception as e:
				# Log but don't fail - parent update is optional
				frappe.log_error(f"Failed to update parent block content on reorder: {str(e)}")
		
		return success_response({'block_id': block_id, 'name': block.name, 'new_position': new_position})
	
	except Exception as e:
		return handle_api_error('reorder_block', e)


@whitelist(allow_guest=True)
def move_block(block_id, new_parent_block='', new_workbench_page=None):
	"""Move a block to a new parent or page"""
	try:
		block = frappe.get_doc('workbench_block', block_id)
		old_parent = block.parent_block
		
		# Remove from old parent's content field
		if old_parent:
			try:
				old_parent_doc = frappe.get_doc('workbench_block', old_parent)
				content = json.loads(old_parent_doc.content) if old_parent_doc.content else []
				if block.name in content:
					content.remove(block.name)
					old_parent_doc.content = json.dumps(content)
					old_parent_doc.save(ignore_permissions=True)
			except Exception as e:
				# Log but don't fail - parent update is optional
				frappe.log_error(f"Failed to remove from old parent block content: {str(e)}")
		
		# Update block's parent and page
		if new_workbench_page:
			block.workbench_page = new_workbench_page
		
		block.parent_block = new_parent_block or None
		
		# Reset position in new location
		filters = {
			'workbench_page': block.workbench_page,
			'parent_block': block.parent_block or '',
			'is_deleted': 0
		}
		siblings = frappe.get_all('workbench_block', 
								 filters=filters, 
								 fields=['position'],
								 order_by='position desc',
								 limit=1)
		block.position = (siblings[0].position if siblings else 0) + 1
		
		block.save(ignore_permissions=True)
		
		# Add to new parent's content field if nested
		if new_parent_block:
			try:
				new_parent = frappe.get_doc('workbench_block', new_parent_block)
				content = json.loads(new_parent.content) if new_parent.content else []
				if block.name not in content:
					content.append(block.name)
					new_parent.content = json.dumps(content)
					new_parent.save(ignore_permissions=True)
			except Exception as e:
				# Log but don't fail - parent update is optional
				frappe.log_error(f"Failed to add to new parent block content: {str(e)}")
		
		return success_response(block.as_dict())
	
	except Exception as e:
		return handle_api_error('move_block', e)