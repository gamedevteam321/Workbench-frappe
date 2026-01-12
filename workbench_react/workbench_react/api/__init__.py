# Import API modules to ensure whitelisted functions are registered
# This ensures the @whitelist decorators run and functions are registered
from . import workbench_api
from . import block_api
from . import page_api
from . import realtime_api
from . import clickable_canvas_api
from . import port_config_api

