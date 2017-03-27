"""Module to handle ox_herd tasks.

An OxHerdTask is a general class to represent a task managed by ox_herd.
Users are meant to sub-class OxHerdTask for their own use. See docstring for
OxHerdTask for details.
"""

import shlex
import copy
import logging

from ox_herd.file_cache import cache_utils
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
        args = copy.deepcopy(ox_herd_task)
        args.name += name_suffix
        return args


    @staticmethod
    def choose_default_run_db():
        "Chose default settings for run_db baed on settings for ox_herd."

        run_db = ox_settings.RUN_DB
        if run_db[0] == 'sqlite':
            if run_db[1]:
                return run_db
            else:
                return (run_db[0], cache_utils.get_path(
                    '_ox_herd_run_db.sqlite'))

        raise ValueError('Could not understand run_db setting: %s'
                         % str(run_db))


    @classmethod
    def main_call(cls, ox_herd_task):
        """Main function to run the task.

        Sub-classes should override to do something useful.
        """
        raise NotImplementedError

    @classmethod
    def pre_call(cls, ox_herd_task, rdb):
        """Will be called before main_call.

        :arg rdb:    Instance of RunDB to record job start and job end.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:

        This does things like stores the fact that we started the job in
        a database. If users override, they should probably call this, or
        implement their own job tracking.
        """
        assert ox_herd_task.rdb_job_id is None, (
            'Cannot have rdb_job_id set before callign pre_call.')
        ox_herd_task.rdb_job_id = rdb.record_task_start(ox_herd_task.name)

    @classmethod
    def post_call(cls, ox_herd_task, rdb, return_value, status='finished'):
        """Called just after main_call finishes.

        :arg rdb:    Instance of RunDB to record job start and job end.

        :arg return_value:   Return value of job.

        :arg status='finished':    Final status of job.


        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:        Tracks completion of the job.

        This does things like stores the fact that we finished the job in
        a database. If users override, they should probably call this, or
        implement their own job tracking.
        """
        rdb.record_task_finish(ox_herd_task.rdb_job_id, return_value, status)

    @classmethod
    def run_ox_task(cls, ox_herd_task):
        """Entry point to run the task.

        This is what python rq or other managers will use to start the task.
        """
        job_name = ox_herd_task.name
        run_db = ox_herd_task.run_db
        assert run_db[0] == 'sqlite', (
            'Cannot handle run_db of %s' % str(run_db))
        rdb = ox_run_db.SqliteRunDB(run_db[1])
        cls.pre_call(ox_herd_task, rdb)
        try:
            result = cls.main_call(ox_herd_task)
        except Exception as problem:
            logging.error('For job %s; storing exception result: %s',
                          job_name, str(problem))
            cls.post_call(ox_herd_task, rdb, str(problem), 'exception')
            raise
        cls.post_call(ox_herd_task, rdb, str(result))
