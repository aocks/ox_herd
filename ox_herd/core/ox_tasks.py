"""Module to handle ox_herd tasks.

An OxHerdTask is a general class to represent a task managed by ox_herd.
Users are meant to sub-class OxHerdTask for their own use. See docstring for
OxHerdTask for details.

You can find some example sub-classes of OxHerdTask in the simple_ox_tasks.py
module.
"""

import shlex
import copy
import logging

from ox_herd import settings as ox_settings
from ox_herd.core import ox_run_db

class OxHerdTask(object):
    """Generic task class for ox_herd.

    Users should sub-class OxHerdTask and implement the main_call method.

    Due to the way python rq is setup, it's painful to try and pass class
    instances. Instead, it's better to have your task class have only 
    class methods and pass the data in the kwargs part of a python rq job.
    This lets you more easily inspect the data that a task will be running on.
    To faciliate this, the OxHerdTask is setup to use only classmethods
    and pass an instance of itself in the kwargs of python rq.

    Basically, you create an INSTANCE of OxHerdTask (or sub-class) with the
    desired data to configure the task. You then pass that INSTANCE to
    the add_to_schedule method of OxScheduler which sets things up so that
    if you are using python rq, the INSTANCE is in kwargs and the function
    is a class method which uses those kwargs.

    The simple_ox_tasks has some examples.

    TL;DR = Use only classmethod in OxHerdTask (or sub-classes) and expect
            an instance to be passed in with data.
    """

    # Fields that affect how we pass job into python rq
    rq_fields = ['func', 'queue_name', 'timeout', 'cron_string']

    def __init__(self, name, func=None, run_db=None, queue_name=None, 
                 timeout=None, cron_string=None):
        """Initializer.

        :arg name:     String name for the task.

        :arg func=None:  Function to run remotely. Usually this is the
                         run_ox_task classmethod of a sub-class of the
                         OxHerdTask and that is what we use if func is None.
                         The instance of OxHerdTask will be passed
                         as a keyword arg to func with key 'ox_herd_task', so 
                         make sure func can be called as 
                         func(ox_herd_task=task).

        :arg run_db=None:    Database used to track execution of the task. If
                             None is provided, we use default db.

        :arg queue_name=None:  Optional string representing which queue
                               to run. If not provided, then we use the
                               first item from ox_settings.QUEUE_NAMES.

        :arg timeout=None:     Optional timeout for job.

        :arg cron_string=None: Optional string in cron format saying how
                               the job should be scheduled.

        """
        self.name = name
        self.func = func if func is not None else self.run_ox_task
        self.run_db = run_db if run_db else self.choose_default_run_db()
        self.queue_name = queue_name if queue_name else shlex.split(
            ox_settings.QUEUE_NAMES)[0]
        self.timeout = timeout
        self.cron_string = cron_string
        self.rdb_job_id = None # job_id inside our own RunDB

    @staticmethod
    def make_copy(ox_herd_task, name_suffix='_copy'):
        """Helper function to make a copy of the task.
        
        :arg ox_herd_task:        Instance of OxHerdTask to copy.
        
        :arg name_suffix='_copy': Optional suffix to append to name.       
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:       Copied task.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:    We sometimes want to make copies of a task (e.g., 
                    if the user wants to launch a copy of a scheduled task).
                    This method makes a copy but with a different name. It
                    also allows sub-classes to control how copies are made.
        """
        args = copy.deepcopy(ox_herd_task)
        args.name += name_suffix
        return args


    @staticmethod
    def choose_default_run_db():
        """Chose default settings for run_db baed on settings for ox_herd.

        """

        run_db = ox_settings.RUN_DB
        if run_db[0] == 'redis':
            return run_db
        if run_db[0] == 'sqlite':
            if run_db[1]:
                return run_db
            else:
                raise ValueError('Need to provide valid path for sqlite run_db')

        raise ValueError('Could not understand run_db setting: %s'
                         % str(run_db))


    @staticmethod
    def get_template_name():
        """Return string for jinja template to use in display task result.

        By default we just display some information which every task should
        have available.

        If you register your own blueprints or otherwise get jinja templates
        into your path, you can override this to return your own templates.

        The task will be passed in as as task_data.
        """
        return 'generic_ox_task_result.html'
        
        
    @classmethod
    def main_call(cls, ox_herd_task):
        """Main function to run the task.

        Sub-classes should override to do something useful.
        
        The return value should either be a simple string of 80 characters
        or less describing the result or a dict.

        If a dict is returned, it should be as follows:

           { 'return_value' : <simple string or return code>,
             'json_blob' : <string as produced by json.dumps>,
             'pickle_blob' : <string as produced by pickle.dumps }

        You should use return_value for simple, small return codes like a
        'completed succesfully' message or 'invalid data' message or something.
        You should use json_blob for more complicated results when possible
        as that is most portable. If you have really complex return values,
        use pickle_blob. If provided, these values will be stored in the
        RunDB for later inspection by the web UI or other tools.
        """
        raise NotImplementedError

    @classmethod
    def pre_call(cls, ox_herd_task, rdb):
        """Will be called before main_call.

        :arg ox_herd_task:  The instance of the task to do pre_call for.

        :arg rdb:    Instance of RunDB to record job start and job end.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   Run some operations before main_call.

        This does things like stores the fact that we started the job in
        a database. If users override, they should probably call this, or
        implement their own job tracking. The idea is that users can just
        use the default pre_call and only override main_call for their job.
        """
        assert ox_herd_task.rdb_job_id is None, (
            'Cannot have rdb_job_id set before callign pre_call.')
        ox_herd_task.rdb_job_id = rdb.record_task_start(
            ox_herd_task.name, ox_herd_task.get_template_name())

    @classmethod
    def post_call(cls, ox_herd_task, rdb, call_result, status='finished'):
        """Called just after main_call finishes.

        :arg ox_herd_task:  The instance of the task to do post_call for.

        :arg rdb:    Instance of RunDB to record job start and job end.

        :arg call_result:  Value returned by main_call (either a string or
                           dict); see docs for main_call return value.

        :arg status='finished':    Final status of job.


        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:        Tracks completion of the job.

        This does things like stores the fact that we finished the job in
        a database. If users override, they should probably call this, or
        implement their own job tracking.
        """
        rval = {}
        if isinstance(call_result, str):
            rval['return_value'] = call_result
        elif isinstance(call_result, dict):
            rval = dict(call_result)
        else:
            raise TypeError(
                'call_result from main_call must be str or dict not %s' % (
                    str(call_result)))
                
        rdb.record_task_finish(ox_herd_task.rdb_job_id, status=status, **rval)

    @classmethod
    def run_ox_task(cls, ox_herd_task):
        """Entry point to run the task.

        This is what python rq or other managers will use to start the task.
        """
        job_name = ox_herd_task.name
        run_db = ox_herd_task.run_db
        rdb = ox_run_db.create(run_db)
        cls.pre_call(ox_herd_task, rdb)
        try:
            result = cls.main_call(ox_herd_task)
        except Exception as problem:
            logging.error('For job %s; storing exception result: %s',
                          job_name, str(problem))
            cls.post_call(ox_herd_task, rdb, str(problem), 'exception')
            raise
        cls.post_call(ox_herd_task, rdb, result)
