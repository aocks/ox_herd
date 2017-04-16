"""Simple example of an ox_herd plugin.

This is module serves as an example of how to create an ox_herd plugin.
It provides a single class: CheckCPU which uses the psutil module (which
you may have to install on your system if you don't have it already).

The CheckCPU class inherits from OxHerdTask to indicate that it is a
task ox_herd can run and provides the main_call classmethod to actually
run the task. It also inherits from OxPluginComponent to indicate that
it is a plugin component.

Provided that you include this plugin in the OX_PLUGINS variable in
ox_herd.settings, this will be picked up automatically and used as a plugin.

In general, there are a variety of more complicated things you can do
in configuring plugins. See documentation on plugins or see the pytest_plugin
example for more details.
"""

import json

import psutil

from ox_herd.core.plugins import base
from ox_herd.core import ox_tasks

class CheckCPU(ox_tasks.OxHerdTask, base.OxPluginComponent):
    """Class to check and report CPU usage.

    This is meanly meant to serve as an example of a minimal plugin.
    Things to note are:

       1. We inherit from OxHerdTask and implement main_call to indicate
          the task that this plugin component does.
       2. We inherit from OxPluginComponent to indicate this is a plugin
          component.
    """

    @classmethod
    def main_call(cls, my_task):
        """Main method to lookup CPU usage.

        :arg my_task:   Instance of a CheckCPU task perhaps containing
                        additional data (e.g., my_task.name). If your
                        main_call does not need arguments, you can basically
                        just ignore my_task. If you do want to be able
                        to pass in arguments, see a more detailed discussion
                        of how to get arguments from the user and configure
                        a task in the full plugin documentation.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :returns:       Dictionary with 'return_value' and 'json_blob' as
                        required for OxPluginComponent.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:        Use the psutil module to lookup CP usage.

        """
        cpu = psutil.cpu_percent()
        pids = len(psutil.get_pid_list())
        data = {'cpu_percent' : cpu, 'num_pids' : pids}
        return {
            'return_value' : 'Task %s completed succesfully: cpu=%s' % (
                my_task.name, cpu), 'json_blob' : json.dumps(data)
            }
