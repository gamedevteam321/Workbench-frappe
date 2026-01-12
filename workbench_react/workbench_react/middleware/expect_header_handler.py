"""
WSGI Middleware to strip Expect: 100-continue headers
Prevents HTTP 417 errors by removing problematic headers before request processing.

This middleware provides defense-in-depth: even if a request somehow includes
the Expect header (despite frontend blocking), the backend will handle it gracefully.
"""

import frappe


class ExpectHeaderMiddleware:
    """
    WSGI middleware to strip Expect: 100-continue headers from incoming requests.
    
    This middleware removes HTTP_EXPECT and HTTP_EXPECTATION from the WSGI environ
    before the request reaches Frappe's request handlers. This prevents HTTP 417
    errors that can occur when proxies or clients send Expect headers that the
    server doesn't support.
    """
    
    def __init__(self, application):
        """
        Initialize middleware with the WSGI application to wrap.
        
        Args:
            application: The WSGI application (Frappe app)
        """
        self.application = application
    
    def __call__(self, environ, start_response):
        """
        Process the WSGI request, removing Expect headers if present.
        
        Args:
            environ: WSGI environment dictionary
            start_response: WSGI start_response callable
            
        Returns:
            Response from the wrapped application
        """
        # Remove Expect headers from WSGI environment
        # WSGI servers convert HTTP headers to environ keys with HTTP_ prefix
        # and convert dashes to underscores, uppercase
        headers_removed = []
        
        if 'HTTP_EXPECT' in environ:
            headers_removed.append('Expect')
            del environ['HTTP_EXPECT']
        
        if 'HTTP_EXPECTATION' in environ:
            headers_removed.append('Expectation')
            del environ['HTTP_EXPECTATION']
        
        # Log removal in development mode (optional, can be removed for production)
        if headers_removed and frappe.conf.developer_mode:
            frappe.logger().debug(
                f"[ExpectHeaderMiddleware] Removed headers: {', '.join(headers_removed)}"
            )
        
        # Call the wrapped application
        return self.application(environ, start_response)
