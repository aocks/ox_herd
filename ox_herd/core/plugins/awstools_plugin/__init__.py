"""Provides plugin containing ox_herd tools for AWS.
"""

from flask import Blueprint
from ox_herd.core.plugins.awstools_plugin.core import OxHerdAWSToolsPlugin


AWSTOOLS_BP = Blueprint(
    'awstools_plugin', __name__, template_folder='templates')
OxHerdAWSToolsPlugin.set_bp(AWSTOOLS_BP)


def get_ox_plugin():
    """Required function for module to provide plugin.
    """
    return OxHerdAWSToolsPlugin
