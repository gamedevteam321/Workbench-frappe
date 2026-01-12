__version__ = "0.0.1"

# #region agent log - Track module import
try:
    import json as json_module
    import time
    log_path = '/home/vrushali/frappe-bench/.cursor/debug.log'
    with open(log_path, 'a', encoding='utf-8') as f:
        log_entry = json_module.dumps({
            "sessionId": "debug-session",
            "runId": "initial",
            "hypothesisId": "A",
            "location": "workbench_react/__init__.py:import_start",
            "message": "Starting API module imports",
            "data": {
                "has_frappe": False,
                "frappe_whitelisted_exists": False,
                "whitelisted_count_before": 0
            },
            "timestamp": int(time.time() * 1000)
        }) + '\n'
        f.write(log_entry)
except:
    pass
# #endregion

# Import API modules to ensure whitelisted functions are registered
# This must happen at module load time so @whitelist decorators execute
# The decorators will execute when the module is imported, adding functions to frappe.whitelisted
try:
    import frappe
    # #region agent log - Track Frappe state before import
    try:
        import json as json_module
        import time
        log_path = '/home/vrushali/frappe-bench/.cursor/debug.log'
        whitelisted_count_before = len(frappe.whitelisted) if hasattr(frappe, 'whitelisted') else 0
        with open(log_path, 'a', encoding='utf-8') as f:
            log_entry = json_module.dumps({
                "sessionId": "debug-session",
                "runId": "initial",
                "hypothesisId": "A",
                "location": "workbench_react/__init__.py:before_import",
                "message": "Before importing API modules",
                "data": {
                    "has_frappe": True,
                    "frappe_whitelisted_exists": hasattr(frappe, 'whitelisted'),
                    "whitelisted_count_before": whitelisted_count_before,
                    "has_local_db": hasattr(frappe, 'local') and hasattr(frappe.local, 'db'),
                    "has_local_request": hasattr(frappe, 'local') and hasattr(frappe.local, 'request')
                },
                "timestamp": int(time.time() * 1000)
            }) + '\n'
            f.write(log_entry)
    except:
        pass
    # #endregion
    
    # Import using relative imports since we're inside the package
    # These imports will trigger the @whitelist decorators to execute
    from .api import workbench_api
    from .api import block_api
    from .api import page_api
    from .api import realtime_api
    from .api import clickable_canvas_api
    from .api import port_config_api
    
    # #region agent log - Track after import
    try:
        import json as json_module
        import time
        log_path = '/home/vrushali/frappe-bench/.cursor/debug.log'
        whitelisted_count_after = len(frappe.whitelisted) if hasattr(frappe, 'whitelisted') else 0
        create_workbench_in_whitelist = False
        create_workbench_obj = None
        try:
            create_workbench_obj = getattr(workbench_api, 'create_workbench', None)
            if create_workbench_obj and hasattr(frappe, 'whitelisted'):
                create_workbench_in_whitelist = create_workbench_obj in frappe.whitelisted
                if not create_workbench_in_whitelist and hasattr(create_workbench_obj, '__wrapped__'):
                    create_workbench_in_whitelist = create_workbench_obj.__wrapped__ in frappe.whitelisted
        except:
            pass
        with open(log_path, 'a', encoding='utf-8') as f:
            log_entry = json_module.dumps({
                "sessionId": "debug-session",
                "runId": "initial",
                "hypothesisId": "A",
                "location": "workbench_react/__init__.py:after_import",
                "message": "After importing API modules",
                "data": {
                    "whitelisted_count_after": whitelisted_count_after,
                    "whitelisted_count_increase": whitelisted_count_after - whitelisted_count_before,
                    "create_workbench_in_whitelist": create_workbench_in_whitelist,
                    "create_workbench_exists": create_workbench_obj is not None,
                    "create_workbench_id": id(create_workbench_obj) if create_workbench_obj else None,
                    "create_workbench_has_wrapped": hasattr(create_workbench_obj, '__wrapped__') if create_workbench_obj else False
                },
                "timestamp": int(time.time() * 1000)
            }) + '\n'
            f.write(log_entry)
    except:
        pass
    # #endregion
except (ImportError, AttributeError) as e:
    # Silently fail if modules can't be imported (e.g., during setup or if frappe not available)
    # This is expected during initial app installation
    # However, log the error in developer mode for debugging
    try:
        import frappe
        if hasattr(frappe, 'conf') and getattr(frappe.conf, 'developer_mode', False):
            frappe.logger().warning(f"[workbench_react] Could not import API modules (this is normal during installation): {e}")
    except:
        pass
except SyntaxError as e:
    # Syntax errors should be logged as they indicate code problems
    try:
        import sys
        print(f"[workbench_react] SyntaxError importing API modules: {e}", file=sys.stderr)
    except:
        pass
except Exception as e:
    # Log unexpected errors
    try:
        import sys
        print(f"[workbench_react] Unexpected error importing API modules: {e}", file=sys.stderr)
    except:
        pass
