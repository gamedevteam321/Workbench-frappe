# workbench_react/hooks.py

app_name = "workbench_react"
app_title = "Workbench React"
app_publisher = "Your Name"
app_description = "Notion-like collaborative editor"
app_email = "you@example.com"
app_license = "MIT"

# Required apps/dependencies
# required_apps = []

# Includes in <head>
# add_to_head = "workbench_react/templates/includes/custom_head.html"

# includes app js, css files in order of string name
# app_include_css = "/assets/workbench_react/css/workbench_react.css"
# app_include_js = "/assets/workbench_react/js/workbench_react.js"

# include custom scss in every page where desk is rendered
# desk_theme_css = "workbench_react/public/css/workbench_react.css"

# includes custom scss in desk only
# desk_included_css = "/assets/workbench_react/css/custom_desk.css"

# include custom js in page
# page_js = {"page-name": "public/js/file.js"}

# include custom js in doctype views
# doctype_js = {"doctype_name": "public/js/doctype_name.js"}
# doctype_list_js = {"doctype_name": "public/js/doctype_list_name.js"}
# doctype_tree_js = {"doctype_name": "public/js/doctype_tree_name.js"}
# doctype_calendar_js = {"doctype_name": "public/js/doctype_calendar_name.js"}
# doctype_chat_js = {"doctype_name": "public/js/doctype_chat_name.js"}

# Svg icon hook
# doctype_icon_map = {"doctype_name": "custom/path/to/icon.svg"}

# Home Pages
# home_page_template = "templates/includes/home_page.html"
# welcome_page = "app/welcome"

# auto_install = True
# after_install = "workbench_react.install.after_install"

# Includes in Site
# insert_after_assets_include = ""

# include file in html head - use full path relative to home dir
# add_to_includes = "workbench_react/templates/includes/custom_script.html"

# Registration hook
# doctype_js = {"Event": "event.js"}
# doctype_list_js = {"Task": "task_list.js"}
# doctype_tree_js = {"Task": "task_tree.js"}
# doctype_calendar_js = {"Task": "task_calendar.js"}

# Wsgi middleware
# wsgi_middleware = [
#     "workbench_react.middleware.CustomMiddleware"
# ]

# User Data Protection
# user_data_fields = [
#     {
#         "doctype": "{doctype_name}",
#         "filter_by": "{filter_field}",
#         "redact_fields": ["{field_1}", "{field_2}"],
#         "depends_on": "{depends_on_doctype_field}",
#     },
# ]

# Authentication and authorization
# auth_hooks = [
#     "workbench_react.auth.validate"
# ]

# Translation files
# translated_pages = [
#     "app/index",
#     "app/profile",
# ]

# Fixtures
fixtures = []

# Migrate (after_migrate hook)
def after_migrate():
    """
    Create database indexes for fast CRUD operations.
    Called after bench migrate.
    """
    import frappe
    
    print("[🔧 Workbench] Creating database indexes...")
    
    try:
        # Index 1: Fast lookup of blocks by page
        frappe.db.add_index(
            "Workbench Block",
            ["workbench_page"],
            "idx_wb_block_page"
        )
        print("✅ Created index: idx_wb_block_page")
    except Exception as e:
        print(f"⚠️ Index idx_wb_block_page already exists or error: {str(e)}")
    
    try:
        # Index 2: Fast ordered iteration (page + position)
        frappe.db.add_index(
            "Workbench Block",
            ["workbench_page", "position"],
            "idx_wb_block_page_pos"
        )
        print("✅ Created index: idx_wb_block_page_pos")
    except Exception as e:
        print(f"⚠️ Index idx_wb_block_page_pos already exists or error: {str(e)}")
    
    try:
        # Index 3: Fast lookup by owner (for "my pages" queries)
        frappe.db.add_index(
            "Workbench Page",
            ["owner"],
            "idx_wb_page_owner"
        )
        print("✅ Created index: idx_wb_page_owner")
    except Exception as e:
        print(f"⚠️ Index idx_wb_page_owner already exists or error: {str(e)}")
    
    frappe.db.commit()
    print("[✅ Workbench] Database indexes created successfully!")
