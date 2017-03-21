"""Module to handle ox_herd jobs.

An OxHerdJob is a general class to represent a job managed by ox_herd.
Users are meant to sub-class OxHerdJob for their own use. See docstring for
OxHerdJob for details.
"""

import copy
import logging

from ox_herd.file_cache import cache_utils
from ox_herd import settings as ox_settings
from ox_herd.core import ox_run_db

class OxHerdArgs(object):
    """Generic arguments required for an OxHerdJob.
    """

    def __init__(self, name, run_db=None, queue_name='default', timeout=None,
                 cron_string=None, special=None):
        """Initializer.

        :arg name:     String name for the OxHerdJob.

        :arg run_db=None:    Database used to track execution of the job. If
                             None is provided, we use default db.

        """
        self.name = name
        self.run_db = run_db if run_db else self.choose_default_run_db()
        self.queue_name = queue_name
        self.timeout = timeout
        self.cron_string = cron_string
        self.special = special
        self.rdb_job_id = None # job_id inside our own RunDB


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


class OxHerdJob(object):
    """Generic job class for ox_herd.

Users should sub-class OxHerdJob and implement the main_call method.
"""

    def __init__(self, ox_herd_args):
        """Initializer.

        :arg ox_herd_args:   Instance of OxHerdArgs to store information about
                             the OxHerdJob.
        """
        self.ox_herd_args = ox_herd_args

    def make_copy(self, name_suffix='_copy'):
        args = copy.deepcopy(self.ox_herd_args)
        args.name += name_suffix
        result = self.__class__(args)
        return result

    def main_call(self):
        """Main function to run the task.

        Sub-classes should override to do something useful.
        """
        raise NotImplementedError

    def pre_call(self, rdb):
        """Will be called before main_call.

        :arg rdb:    Instance of RunDB to record job start and job end.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:

        This does things like stores the fact that we started the job in
        a database. If users override, they should probably call this, or
        implement their own job tracking.
        """
        assert self.ox_herd_args.rdb_job_id is None, (
            'Cannot have rdb_job_id set before callign pre_call.')
        self.ox_herd_args.rdb_job_id = rdb.record_job_start(
            self.ox_herd_args.name)

    def post_call(self, rdb, return_value, status='finished'):
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
        rdb.record_job_finish(self.ox_herd_args.rdb_job_id,
                              return_value, status)

    def __call__(self, is_ox_job):
        """Entry point to run the task.

        This is what python rq or other managers will use to
        start the task.
        """
        assert is_ox_job, (
            'Need to pass is_ox_job=1. This lets us identify ox_jobs on the q')
        job_name = self.ox_herd_args.name
        run_db = self.ox_herd_args.run_db
        assert run_db[0] == 'sqlite', (
            'Cannot handle run_db of %s' % str(run_db))
        rdb = ox_run_db.SqliteRunDB(run_db[1])
        self.pre_call(rdb)
        try:
            result = self.main_call()
        except Exception as problem:
            logging.error('For job %s; storing exception result: %s',
                          job_name, str(problem))
            self.post_call(rdb, str(problem), 'exception')
            raise
        self.post_call(rdb, str(result))
