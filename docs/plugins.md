
# Ox Herd Plugins

Ox Herd provides a plugin infrastructure so that you can create own tasks,
reports, and so on.

# A simple plugin

The simplest way to create a plugin is to write a python module which defines
a sub-class of `OxPlugTask` as illustrated below:

```
import psutil # A neat little module to illustrate a neat task

from ox_herd.core.plugins import base

class CheckCPU(base.OxPlugTask):
    """Class to check and report CPU usage.
    """

    @classmethod
    def main_call(cls, my_task):
        """Main method to lookup CPU and report CPU usage.
        """
        cpu = psutil.cpu_percent()
        return {
            'return_value' : 'Task %s completed succesfully: cpu=%s' % (
                my_task.name, cpu)}

```

We override the `main_call` method of `OxPlugTask` to do the work and
return a dictionary with a string `return_value` to provide the
result.  To register this plugin you can either append your plugin
module to the value of `ox_herd.settings.OX_PLUGINS` at startup or you
can provide a colon separated string of module paths in the
`OX_PLUGINS` environment variable.

For example, if you save the above code in
`/home/shepard/code/check_cpu.py` you could set
`OX_PLUGINS=code.check_cpu` (assuming that `code` is a python package
in your `PYTHONPATH`).

Doing the above will accomplish the following provide an plugin
viewable in Ox Herd dashboard which you can schedule for automatic
runs.

You can see a more detailed example by looking at source code for the `CheckCPU` in the [example_psutil_plugin.py](https://github.com/aocks/ox_herd/blob/e6db55faa9bf21c115c35559e7288bbd6844586a/ox_herd/core/plugins/example_psutil_plugin.py) module which provides some more comments.

# A more sophisticated example

The Ox Herd plugin architecutre lets you do a lot more, however. For example, see the source code for the [pytest_plugin](https://github.com/aocks/ox_herd/blob/e6db55faa9bf21c115c35559e7288bbd6844586a/ox_herd/core/plugins/pytest_plugin) as an example. This provides a python package which serves as a flask Blueprint.

The `__init__.py` file in the top-level `pytest_plugin` directory sets up the flask blueprint. The `forms.py` module provides a form using `WTForms` so the user can configure the task. The `templates` sub-directory provides a custom template to format a custom report for the result of the task. Finally, the `core.py` module provides the core implementation of an automated task to test your code using pylint.

