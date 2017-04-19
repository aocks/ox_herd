"""Forms for ox_herd commands.
"""

from wtforms import StringField
from ox_herd.core.plugins import base

class PylintForm(base.GenericOxForm):
    """Use this form to enter parameters for a new pylint job to schedule.
    """

    url = StringField('url', [], description=(
        'Location for package to analyze. This can be a github URL or a file\n'
        'location.'))

