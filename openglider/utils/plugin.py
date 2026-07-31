from __future__ import annotations

import importlib
import importlib.metadata
import logging
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from openglider.gui.app import GliderApp

logger = logging.getLogger(__name__)


def setup_plugins(app: Optional["GliderApp"] = None) -> list[str]:
    """
    Discover and initialize OpenGlider plugins.
    """
    plugins = []
    seen = set()

    for plugin_name in _discover_plugins():
        if plugin_name in seen:
            continue
        seen.add(plugin_name)

        logger.info(f"Loading plugin: {plugin_name}")

        if not _load_plugin(plugin_name, app):
            continue

        plugins.append(plugin_name)

    if plugins:
        logger.info(f"Successfully loaded {len(plugins)} plugin(s): {', '.join(plugins)}")
    else:
        logger.info("No plugins loaded")

    return plugins


def _normalize(name: str) -> str:
    return name.lower().replace("-", "_").strip()


def _discover_plugins() -> list[str]:
    """
    Discover OpenGlider plugins using importlib.metadata.
    
    Searches for installed distributions with names starting with 'openglider-'
    or 'openglider_' (but not 'openglider' itself). This method properly handles
    editable installs and modern Python packaging.
    
    Returns:
        List of plugin package names
    """
    plugins = {}

    try:
        for dist in importlib.metadata.distributions():
            name = dist.name
            if not name:
                continue

            normalized = _normalize(name)

            # only match plugins
            if not normalized.startswith("openglider_"):
                continue

            # deduplicate by normalized name
            plugins[normalized] = dist

    except Exception as e:
        logger.error(f"Error discovering plugins: {e}", exc_info=True)

    return list(plugins.keys())


def _load_plugin(plugin_name: str, app: Optional["GliderApp"]) -> bool:
    try:
        module = importlib.import_module(plugin_name)
        
        # Look for the init function
        init_func: Optional[Callable] = getattr(module, "init", None)

        if init_func is None:
            logger.warning(f"Plugin '{plugin_name}' has no init() function")
            return False

        if not callable(init_func):
            logger.warning(f"Plugin '{plugin_name}' init is not callable")
            return False

        init_func(app)
        logger.debug(f"Initialized plugin: {plugin_name}")
        return True

    except ImportError as e:
        logger.error(f"Failed to import plugin '{plugin_name}': {e}", exc_info=True)
        return False

    except Exception as e:
        logger.error(f"Error initializing plugin '{plugin_name}': {e}", exc_info=True)
        raise