"""Forms for ox_herd commands.
"""

from wtforms import StringField
from ox_herd.core.plugins import base

class SchedJobForm(base.GenericOxForm):
    """Use this form to enter parameters for a new pytest job to schedule.
    """

    url = StringField('url', [], description=(
        'Location for package to test. This can be a github URL or a file\n'
        'location.'))

    pytest_cmd = StringField(
        'pytest_cmd', [], 
        default='--ignore=/path/to/setup.py --doctest-modules',
        description=(
            'Command line arguments for pytest. For example, you could\n'
            'provide something like\n\n'
            '  --ignore=/path/to/setup.py --doctest-modules\n\n'
            'to get pytest working as you like. This will be passed through\n'
            'shlex.split.\n'))
    
    xml_file = StringField(
        'xml_file', [], description=(
            'Optional path to xml file for output of test run. Usually,\n'
            'you should not provide this and a temp file will be used\n'
            'and then deleted. If you do manually specify a path, then that\n'
            'path will be used and *NOT* deleted (which can be useful\n'
            'for debugging).'))
