"""Provides pytest plugin for ox_herd.
"""

from flask import Blueprint
from ox_herd.core.plugins.pytest_plugin.core import OxHerdPyTestPlugin

OxHerdPyTestPlugin.set_bp(Blueprint(
    'pytest_plugin', __name__, template_folder='templates'))

def get_ox_plugin():
    """Required function for module to provide plugin.
    """
    return OxHerdPyTestPlugin()


