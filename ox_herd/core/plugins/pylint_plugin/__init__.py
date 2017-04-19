"""Provides pylint plugin for ox_herd.
"""

from flask import Blueprint
from ox_herd.core.plugins.pylint_plugin.core import OxHerdPyLintPlugin

OxHerdPyLintPlugin.set_bp(Blueprint(
    'pylint_plugin', __name__, template_folder='templates'))

def get_ox_plugin():
    """Required function for module to provide plugin.
    """
    return OxHerdPyLintPlugin()


