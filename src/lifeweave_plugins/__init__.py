"""Small plugin registry and invocation boundary for existing LifeWeave owners."""

from .core import PluginDefinition, PluginHost, PluginRegistry, builtin_registry

__all__ = ["PluginDefinition", "PluginHost", "PluginRegistry", "builtin_registry"]
