from __future__ import annotations

import importlib
import importlib.metadata
import logging
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from openglider.gui.app import GliderApp

logger = logging.getLogger(__name__)


def setup_plugins(app: Optional[GliderApp] = None) -> list[str]:
    """
    Discover and initialize OpenGlider plugins.
    """
    plugins = []
    potential_plugins = _discover_plugins()
    
    for plugin_name in potential_plugins:
        logger.info(f"Loading plugin: {plugin_name}")
        
        if not _load_plugin(plugin_name, app):
            continue
            
        plugins.append(plugin_name)
    
    if plugins:
        logger.info(f"Successfully loaded {len(plugins)} plugin(s): {', '.join(plugins)}")
    else:
        logger.info("No plugins loaded")
        
    return plugins


def _discover_plugins() -> list[str]:
    """
    Discover OpenGlider plugins using importlib.metadata.
    
    Searches for installed distributions with names starting with 'openglider-'
    or 'openglider_' (but not 'openglider' itself). This method properly handles
    editable installs and modern Python packaging.
    
    Returns:
        List of plugin package names
    """
    plugins = []
    
    try:
        # Get all installed distributions
        distributions = importlib.metadata.distributions()
        
        for dist in distributions:
            name = dist.metadata.get("Name", "")
            
            # Match openglider-* or openglider_* but not openglider itself
            if name and name != "openglider":
                # Normalize name for comparison (PEP 503)
                normalized = name.lower().replace("-", "_")
                if normalized.startswith("openglider_"):
                    # Use the normalized form as module name
                    plugins.append(normalized)
                    
    except Exception as e:
        logger.error(f"Error discovering plugins: {e}", exc_info=True)
    
    return plugins


def _load_plugin(plugin_name: str, app: Optional[GliderApp]) -> bool:
    """
    Load and initialize a single plugin.
    
    Args:
        plugin_name: Name of the plugin module to load
        app: The GliderApp instance to pass to the init function
        fail_fast: Whether to raise exceptions or just log them
        
    Returns:
        True if plugin loaded successfully, False otherwise
        
    Raises:
        Exception: If fail_fast=True and loading fails
    """
    try:
        module = importlib.import_module(plugin_name)
        
        # Look for the init function
        init_func: Optional[Callable] = getattr(module, "init", None)
        
        if init_func is None:
            logger.warning(f"Plugin '{plugin_name}' has no init() function - skipping initialization")
            logger.info(f"dir: {dir(module)}")
            return False
        
        if not callable(init_func):
            logger.warning(f"Plugin '{plugin_name}' has non-callable init attribute - skipping")
            return False
        
        # Call the plugin's init function
        init_func(app)
        logger.debug(f"Successfully initialized plugin: {plugin_name}")
        return True
        
    except ImportError as e:
        error_msg = f"Failed to import plugin '{plugin_name}': {e}"
        logger.error(error_msg, exc_info=True)
        return False
        
    except Exception as e:
        error_msg = f"Error initializing plugin '{plugin_name}': {e}"
        logger.error(error_msg)
        raise
