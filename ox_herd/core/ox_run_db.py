"""Simple database to track task execution.
"""

import doctest
import logging
import os
import datetime
import sqlite3

def create(run_db):
    "Create and return RunDB reference based on run_db input."
    if run_db[0] == 'sqlite':
        return SqliteRunDB(run_db[1])

    raise ValueError('Could not understand run_db %s' % str(run_db))

class RunDB(object):
    """Abstract specification for database to track running of tasks.
    """

    def record_task_start(self, task_name):
        """Record that we are starting task with given name in database.

        :arg task_name:        String name for task.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :returns:   Task id to use in referring to task later (e.g, in
                    record_task_finish method).

        PURPOSE:

        """
        raise NotImplementedError

    def record_task_finish(self, task_id, return_value, status='finished'):
        """Record we finished a task.

        :arg task_id:        ID for task as returned by record_task_start.

        :arg return_value:  String return value of task.

        :arg status='finished':   String status of task.

        """
        raise NotImplementedError

    def get_tasks(self, status='%', start_utc=None, end_utc=None):
        """Return list of TaskInfo objects.
        
        :arg status='%':     Wildcard pattern for task status.
        
        :arg start_utc=None: String specifying minimum task_start_utc.       
        
        :arg end_utc=None:   String specifying maximum task_end_utc     
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:       List of TaskInfo objects.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:        Main way to get information about the tasks run.
        
        """
        raise NotImplementedError

class TaskInfo(object):
    """Python class to represent task info stored in database.
    """

    def __init__(
            self, task_id, task_name, task_start_utc, task_status,
            task_end_utc, return_value):
        self.task_id = task_id
        self.task_name = task_name
        self.task_start_utc = task_start_utc
        self.task_status = task_status
        self.task_end_utc = task_end_utc
        self.return_value = return_value


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

        sql = """CREATE TABLE task_info (
          task_id INTEGER PRIMARY KEY ASC,
          task_name text,
          task_start_utc text,
          task_status text,
          task_end_utc text,
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

    def record_task_start(self, task_name):
        'Implement record_task_start for this backend.'

        sql = '''INSERT INTO task_info (
          task_name, task_start_utc, task_status) VALUES (?, ?, ?)
        '''
        cursor = self.conn.cursor()
        cursor.execute(sql, [task_name, datetime.datetime.utcnow(), 'started'])
        task_id = cursor.lastrowid
        self.conn.commit()
        assert task_id is not None, (
            'Expected 1 task id for insert but got %s' % str(task_id))
        return task_id

    def record_task_finish(self, task_id, return_value, status='finished'):
        'Implement record_task_finish for this backend.'

        sql = '''UPDATE task_info
        SET task_end_utc=?, return_value=?, task_status=?
        WHERE task_id=?'''
        cursor = self.conn.cursor()
        utcnow = datetime.datetime.utcnow()
        cursor.execute(sql, [utcnow, return_value, str(status), task_id])
        rowcount = cursor.rowcount
        if rowcount > 1:
            raise ValueError(
                'Impossible: updated multiple rows with single task_id %s' % (
                    str(task_id)))
        elif not rowcount:
            logging.error('Unable to update existing task with finish stats')
            logging.error('Will create finished but unstarted task')
            sql = '''INSERT INTO task_info (
              task_name, task_start_utc, 
              task_id, task_end_utc, return_value, task_status) VALUES (
              'unknown', 'unknown', ?, ?, ?, ?)'''
            cursor.execute(sql, [task_id, utcnow, return_value, status])

        self.conn.commit()

    def get_tasks(self, status='%', start_utc=None, end_utc=None):
        """Return list of TaskInfo objects.
        
        :arg status='%':     Wildcard pattern for task status.
        
        :arg start_utc=None: String specifying minimum task_start_utc.       
        
        :arg end_utc=None:   String specifying maximum task_end_utc     
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:       List of TaskInfo objects.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:        Main way to get information about the tasks run.
        
        """
        cursor = self.conn.cursor()
        sql = ['select * from task_info where task_status like ?']
        args = [status]
        if start_utc is not None:
            sql.append(' AND task_start_utc >= ?')
            args.append(str(start_utc))
        if end_utc is not None:
            sql.append(' AND (task_end_utc IS NULL OR task_end_utc >= ?)')
            args.append(str(end_utc))
                       
        cursor.execute('\n'.join(sql), args)

        return [TaskInfo(*item) for item in cursor.fetchall()]

    @staticmethod
    def _regr_test():
        """
>>> import os, tempfile, datetime, time
>>> from ox_herd.core import ox_run_db
>>> db_file = tempfile.mktemp(suffix='.sql')
>>> db = ox_run_db.SqliteRunDB(db_file)
>>> task_id = db.record_task_start('test')
>>> time.sleep(1)
>>> db.record_task_finish(task_id, 'test_return')
>>> db.conn.close()
>>> del db
>>> os.remove(db_file)
>>> assert not os.path.exists(db_file)

"""

if __name__ == '__main__':
    doctest.testmod()
    print('Finished tests')