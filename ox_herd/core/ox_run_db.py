"""Simple database to track job execution.
"""

import logging
import os
import datetime
import sqlite3

class RunDB(object):
    """Abstract specification for database to track running of tasks.
    """

    def record_job_start(self, job_name):
        """Record that we are starting job with given name in database.

        :arg job_name:        String name for job.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :returns:   Job id to use in referring to job later (e.g, in
                    record_job_finish method).

        PURPOSE:

        """
        raise NotImplementedError

    def record_job_finish(self, job_id, return_value, status='finished'):
        """Record we finished a job.

        :arg job_id:        ID for job as returned by record_job_start.

        :arg return_value:  String return value of job.

        :arg status='finished':   String status of job.

        """
        raise NotImplementedError

    def get_jobs(self, status='%'):
        'Get all jobs matching given status string.'

        raise NotImplementedError

class SqliteRunDB(RunDB):
    """Implementation of RunDB with sqlite backend.
    """

    def __init__(self, db_path, allow_create=True):
        if not os.path.exists(db_path) and allow_create:
            logging.warning('No db file at %s; creating', str(db_path))
            self.create(db_path)
        self.conn = sqlite3.connect(db_path)

    @staticmethod
    def sql_to_create_tables():
        "Return SQL to create required database tables."

        sql = """CREATE TABLE job_info (
          job_id INTEGER PRIMARY KEY ASC,
          job_name text,
          job_start_utc text,
          job_status text,
          job_end_utc text,
          return_value text
        );
        """
        return sql

    def create(self, db_path):
        "Create database at given path."

        sql = self.sql_to_create_tables()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        conn.close()

    def record_job_start(self, job_name):
        'Implement record_job_start for this backend.'

        sql = '''INSERT INTO job_info (
          job_name, job_start_utc, job_status) VALUES (?, ?, ?)
        '''
        cursor = self.conn.cursor()
        cursor.execute(sql, [job_name, datetime.datetime.utcnow(), 'started'])
        result = cursor.execute('SELECT last_insert_rowid()')
        job_id = result.fetchall()
        assert len(job_id) == 1 and len(job_id[0]) == 1
        return job_id[0][0]

    def record_job_finish(self, job_id, return_value, status='finished'):
        'Implement record_job_finish for this backend.'

        sql = '''UPDATE job_info
        SET job_end_utc=?, return_value=?, job_status=?
        WHERE job_id=?'''
        cursor = self.conn.cursor()
        cursor.execute(sql, [datetime.datetime.utcnow(),
                             return_value, status, job_id])

    def get_jobs(self, status='%'):
        'Implement get_jobs for this backend.'

        cursor = self.conn.cursor()
        cursor.execute('select * from job_info where job_status like ?',
                       [status])
        return cursor.fetchall()

    @staticmethod
    def _regr_test():
        """
>>> import os, tempfile, datetime, time
>>> from ox_herd.core import ox_run_db
>>> db_file = tempfile.mktemp(suffix='.sql')
>>> db = ox_run_db.SqliteRunDB(db_file)
>>> job_id = db.record_job_start('test')
>>> time.sleep(1)
>>> db.record_job_finish(job_id, 'test_return')
>>> db.conn.close()
>>> del db
>>> os.remove(db_file)
>>> assert not os.path.exists(db_file)

"""
