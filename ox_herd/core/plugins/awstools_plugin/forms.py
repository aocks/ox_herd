"""Forms for ox_herd commands.
"""

from wtforms import StringField
from ox_herd.core.plugins import base


class BackupForm(base.GenericOxForm):
    """Use this form to enter parameters for a new backup job.
    """

    bucket_name = StringField(
        'bucket_name', [], description=(
            'Name of AWS bucket to put backup into.'))

    bucket_name = StringField(
        'prefix', [], default='misc', description=(
            'Prefix to use in creating remote backup name.'))
    
