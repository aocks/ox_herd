"""Simple example of an ox_herd plugin.

This is module serves as an example of how to create an ox_herd plugin.
It provides a single class: CheckCPU which uses the psutil module (which
you may have to install on your system if you don't have it already).

Provided that you include this plugin in the OX_PLUGINS variable in
ox_herd.settings or in your OX_PLUGINS environment variable, this will be
picked up automatically and used as a plugin.

In general, there are a variety of more complicated things you can do
in configuring plugins. See documentation on plugins or see the pytest_plugin
example for more details.
"""

import json
import psutil

from ox_herd.core.plugins import base


class CheckCPU(base.OxPlugTask):
    """Class to check and report CPU usage.

    This is meanly meant to serve as an example of a minimal plugin.
    All we do is implement the main_call method.
    """

    @classmethod
    def main_call(cls, ox_herd_task):
        """Main method to lookup CPU usage.

        :arg ox_herd_task:   Instance of a CheckCPU task perhaps containing
                        additional data (e.g., ox_herd_task.name). If your
                        main_call does not need arguments, you can basically
                        just ignore ox_herd_task. If you do want to be able
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
        pid_func = getattr(psutil, 'get_pid_list', getattr(psutil, 'pids'))
        if pid_func is None:
            raise ValueError(
                'Do not know how to get pids with version %s of psutil' % (
                    getattr(psutil, '__version__', 'unknown')))
        pids = len(pid_func())
        data = {'cpu_percent': cpu, 'num_pids': pids}
        return {
            'return_value': 'Task %s completed succesfully: cpu=%s' % (
                ox_herd_task.name, cpu), 'json_blob': json.dumps(data)
            }
