"""Forms for ox_herd commands.
"""

import datetime
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import (BooleanField, DateField, DateTimeField, StringField, 
                     RadioField, IntegerField)

class GenericRecord:
    pass

class SchedJobForm(FlaskForm):
    """Use this form to enter parameters for a new job to schedule.

    """

    url = StringField('url', [], description=(
        'Location for package to test. This can be a github URL or a file\n'
        'location.'))

    name = StringField('name', [], default='test_', description=(
        'String name for the job you are going to schedule.'))

    manager = RadioField(
        'manager', default='rq', choices=[(name, name) for name in [
            'instant', 'rq']], description=(
                'Backend implementation for test:\n\n'
                'rq      : python-rq backend for automated background runs\n'
                'instant : run instantly (useful for testing).'))

    timeout = IntegerField(
        'timeout', [], default=900, description=(
            'Timeout in seconds to allow for tasks.'))

    cron_string = StringField(
        'cron_string', [], default='5 1 * * *', description=(
            'Cron format string for when to schedule the task.\n'
            'For example, "5 1 * * 3" would be every Wednesday at 1:05 am.\n'
            'This is used for --manager choices such as rq which support cron\n'
            'scheduling. NOTE: cron_string should have 5 fields. If you try \n'
            'to use the non-standard extended cron format with 6 fields, you\n'
            'may get unexpected results.'))

    pytest = StringField(
        'pytest', [], default='--ignore=/path/to/setup.py --doctest-modules',
        description=(
            'Command line arguments for pytest. For example, you could\n'
            'provide something like\n\n'
            '  --ignore=/path/to/setup.py --doctest-modules\n\n'
            'to get pytest working as you like. This will be passed through\n'
            'shlex.split.\n'))
    
    json_file = StringField(
        'json_file', [], description=(
            'Optional path to json file for output of test run. Usually,\n'
            'you should not provide this and a temp file will be used\n'
            'and then deleted. If you do manually specify a path, then that\n'
            'path will be used and *NOT* deleted (which can be useful\n'
            'for debugging).'))
