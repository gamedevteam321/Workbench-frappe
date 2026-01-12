"""
Port Configuration API

Provides port information to frontend for dynamic port configuration.
This allows the frontend to discover ports without hardcoding them.
"""

import frappe
from frappe import whitelist


@whitelist(allow_guest=True)
def get_port_config():
    """
    Get port configuration for the current site.
    
    Returns:
        dict: Port configuration including webserver_port and socketio_port
    """
    try:
        # Get port configuration from common_site_config.json
        config = frappe.conf
        
        # Extract ports with defaults
        webserver_port = config.get('webserver_port', 8000)
        socketio_port = config.get('socketio_port', 9000)
        
        # Get site name
        site_name = frappe.local.site if hasattr(frappe.local, 'site') else None
        
        # Get host information
        host = frappe.conf.get('host') or 'localhost'
        
        return {
            'webserver_port': webserver_port,
            'socketio_port': socketio_port,
            'site_name': site_name,
            'host': host,
            'api_url': f'http://{host}:{webserver_port}',
            'socket_url': f'http://{host}:{socketio_port}',
        }
    except Exception as e:
        # Return defaults if there's an error
        frappe.log_error(f'Error getting port config: {str(e)}', 'Port Config API')
        return {
            'webserver_port': 8000,
            'socketio_port': 9000,
            'site_name': None,
            'host': 'localhost',
            'api_url': 'http://localhost:8000',
            'socket_url': 'http://localhost:9000',
            'error': str(e),
        }







