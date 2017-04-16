"""Base classes for ox_herd plugins.
"""

from flask_wtf import FlaskForm
from wtforms import (StringField, RadioField, IntegerField, validators)

from ox_herd.core import ox_tasks

class OxPlugin(object):
    """Abstract class for an ox_herd plugin.
    """

    def name(self):
        """Return string name of the plug-in.
        """
        raise NotImplementedError

    def description(self):
        """Return string description of plug-in.
        """
        raise NotImplementedError

    def get_flask_blueprint(self):
        """Return flask blueprint if one exists for the plugin; else None.
        """
        dummy = self # suppress pylint warnings
        return None

    def get_components(self):
        """Return list of OxPluginComponents provided by this OxPlugin
        """
        raise NotImplementedError

class TrivialOxPlugin(OxPlugin):
    """Trivial implementation of an ox_herd plugin.
    """

    def __init__(self, components, name=None, doc=None):
        self._components = components
        self._name = name
        self._doc = doc

    def name(self):
        """Return self._name if set otherwise use name of class.
        """
        return self._name if self._name is not None else self.__class__.__name__

    def description(self):
        """Use self._doc if set otherwise use docstring as description.
        """
        return self._doc if self._doc is not None else self.__doc__

    def get_components(self):
        return self._components

class GenericOxForm(FlaskForm):
    """Use this form to enter parameters for a new job to schedule.
    """

    name = StringField('name', [], default='test_', description=(
        'String name for the job you are going to schedule.'))

    queue_name = StringField('queue_name', [validators.DataRequired()],
                             default='', description=(
        'String name for the job queue that the task will use.\n'
        'Usually this is "default". If you use other names, you should\n'
        'make sure you have the appropriate workers running for that queue.'))

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


class OxPluginComponent(object):

    def cmd_name(self):
        """Return command name to use in running this component.

        Sub-classes should probably override to provide pretty name.
        """
        return self.__class__.__name__

    def get_flask_form(self):
        """Return a sub-classs of GenericOxForm allowing user to configure  job.

        Can return None if configuring job via Flask form not allowed.
        """
        return GenericOxForm

    def get_ox_task_cls(self):
        """Return a sub-class of OxHerdTask
        """
        my_class = self.__class__
        if issubclass(my_class, ox_tasks.OxHerdTask):
            return my_class
        else:
            raise ValueError('Do not know how to produce OxHerdTask from %s' % (
                str(self.__class__.__name__)))

    def get_flask_form_template(self):
        """Return string for jinja template to render result of get_flask_form.

        Default is 'ox_wtf.html' but you can override if desired.
        """
        dummy = self # suppress pylint warnings
        return 'ox_wtf.html'

class OxPlugTask(ox_tasks.OxHerdTask, OxPluginComponent):
    """Example class to show how to make the simplest plugin.

    This is meanly meant to serve as an example of a minimal plugin.
    Things to note are:

       1. We inherit from OxHerdTask and implement main_call to indicate
          the task that this plugin component does.
       2. We inherit from OxPluginComponent to indicate this is a plugin
          component.
    """

    pass
