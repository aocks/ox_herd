"""Simple database to track task execution.
"""

import collections
import doctest
import logging
import os
import datetime
import json
import sqlite3
import redis

from ox_herd import settings as ox_settings

def create(run_db=None):
    "Create and return RunDB reference based on run_db input."

    run_db = run_db if run_db else ox_settings.RUN_DB
    if run_db[0] == 'redis':
        return RedisRunDB()
    if run_db[0] == 'sqlite':
        return SqliteRunDB(run_db[1])

    raise ValueError('Could not understand run_db %s' % str(run_db))

class RunDB(object):
    """Abstract specification for database to track running of tasks.
    """

    def record_task_start(self, task_name, template=None):
        """Record that we are starting task with given name in database.

        :arg task_name:        String name for task.

        :arg template:    String indicating template to use in displaying
                          task result or None to use default.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :returns:   Task id to use in referring to task later (e.g, in
                    record_task_finish method). This is backend dependeant
                    and may be an integer or string or something else 
                    depending on what is easiest for the backend.

        PURPOSE:    Record that we started something.

        """
        raise NotImplementedError

    def record_task_finish(self, task_id, return_value, status='finished',
                           json_blob=None, pickle_blob=None):
        """Record we finished a task.

        :arg task_id:        ID for task as returned by record_task_start.

        :arg return_value:  String return value of task.

        :arg status='finished':   String status of task.

        :arg json_blob=None:  Optional string representing json encoding of 
                              task output. Using JSON to store the result
                              for later inspection is more portable.

        :arg pickle_blob=None:  Optional string representing python pickle
                                encoding of task output. Using JSON to store 
                                the result for later inspection is more 
                                portable, but you can use pickle if necessary.

        """
        raise NotImplementedError

    def delete_task(self, task_id):
        """Delete the task from the database.
        
        :arg task_id:        ID for task as returned by record_task_start.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:   Delete the task.
        
        """
        raise NotImplementedError


    def get_tasks(self, status='finished', start_utc=None, end_utc=None):
        """Return list of TaskInfo objects.
        
        :arg status='finished':   Status of tasks to search. Should be one
                                  of entries from get_allowed_status().
        
        :arg start_utc=None: String specifying minimum task_start_utc.       
        
        :arg end_utc=None:   String specifying maximum task_end_utc     
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:       List of TaskInfo objects.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:        Main way to get information about the tasks run.
        
        """
        raise NotImplementedError

    @staticmethod
    def get_allowed_status():
        """Return list of allowed status strings for tasks.

        It is important to only use values from the allowed list so
        we can store effectively on things like redis.
        """
        return ['started', 'finished']

class TaskInfo(object):
    """Python class to represent task info stored in database.
    """

    def __init__(
            self, task_id, task_name, task_start_utc, task_status,
            task_end_utc=None, return_value=None, json_data=None, 
            pickle_data=None, template=None):
        self.task_id = task_id
        self.task_name = task_name
        self.task_start_utc = task_start_utc
        self.task_status = task_status
        self.task_end_utc = task_end_utc
        self.template = template
        self.return_value = return_value
        self.json_data = json_data
        self.pickle_data = pickle_data

    def __repr__(self):
        args = ', '.join(['%s=%s' % (
            name, repr(value)) for name, value in self.to_dict().items()])
        return '%s(%s)' % (self.__class__.__name__, args)

    def to_dict(self):
        """Return self as a dict.
        """
        return collections.OrderedDict([
            (name, getattr(self, name, '')) for name in [
                'task_id', 'task_name', 'task_start_utc', 'task_status',
                'task_end_utc', 'return_value', 'json_data', 'pickle_data',
                'template']])

    def to_json(self):
        """Return json version of self.
        """
        return json.dumps(self.to_dict())

            

class RedisRunDB(RunDB):
    """Implementation of RunDB with redis backend.
    """

    def __init__(self):
        self.conn = redis.StrictRedis()
        self.my_prefix = ox_settings.REDIS_PREFIX + ':__'
        self.id_counter = self.my_prefix + 'task_id_counter'
        self.task_master = self.my_prefix + 'task_master' + '::'

    def delete_all(self, really=False):
        """Delete everything related to this from Redis.

        Only works if really=True.
        Mainly for testing; be *VERY* careful with this.
        """
        if not really:
            raise ValueError('Not doing delete_all since really=%s' % str(
                really))
        my_keys = list(self.conn.scan_iter(match=self.my_prefix + '*'))
        if my_keys:
            #names = ' '.join([item.decode('utf8') for item in my_keys])
            self.conn.delete(*my_keys)

    def record_task_start(self, task_name, template=None):
        'Implement record_task_start for this backend.'

        if not task_name:
            raise ValueError('Must have non-empty task_name not "%s"' % str(
                task_name))
        if task_name[0:2] == ':_':
            raise ValueError('Invalid task name %s; cannot start with ":_"' % (
                str(task_name)))
        task_id = '%s_%s' % (task_name, datetime.datetime.utcnow().timestamp())
        task_key = self.task_master + task_id
        if self.conn.get(task_key):
            raise ValueError('Cannot add task %s as %s since already exists' % (
                str(task_name), task_id))
        info = TaskInfo(
            task_id, task_name, str(datetime.datetime.utcnow()), 
            'started', template=template).to_json()
        add_result = self.conn.set(task_key, info)
        assert add_result, 'Got add_result = %s for %s; race condition?' % (
            add_result, task_id)

        return task_id

    def delete_task(self, task_id):
        """Delete desired id.
        """
        task_key = self.task_master + task_id
        self.conn.delete(task_key)

    def get_task_info(self, task_id):
        """Return dict representation of task with given task_id or None.
        """
        task_info = None
        task_key = self.task_master + task_id
        task_info_json = self.conn.get(task_key)
        if task_info_json:
            task_info = json.loads(task_info_json.decode('utf-8'))
        return task_info

    def get_task(self, task_id):
        task_info = self.get_task_info(task_id)
        if task_info:
            return TaskInfo(**task_info)
        
        return None

    def record_task_finish(self, task_id, return_value, status='finished',
                           json_blob=None, pickle_blob=None):
        'Implement record_task_finish for this backend.'

        task_info = self.get_task_info(task_id)
        if not task_info:
            logging.error('Unable to update existing task with finish stats')
            logging.error('Will create finished but unstarted task')
            task_info = {'task_name' : 'unknown', 'task_status' : 'unknown'}

        if task_info['task_status'] == 'finished':
            raise ValueError('Cannot record_task_finish for %s; already ended.'
                             % str(task_info))
        task_info['task_end_utc'] = str(datetime.datetime.utcnow())
        task_info['return_value'] = return_value
        task_info['task_status'] = 'finished'
        task_info['json_data'] = json_blob
        task_info['pickle_data'] = pickle_blob
        task_key = self.task_master + task_id
        self.conn.set(task_key, json.dumps(task_info))

    def get_tasks(self, status='finished', start_utc=None, end_utc=None):
        """Return list of TaskInfo objects.
        
        :arg status='finished':   Status of tasks to search. Should be one
                                  entries from get_allowed_status().
        
        :arg start_utc=None: String specifying minimum task_start_utc.       
        
        :arg end_utc=None:   String specifying maximum task_end_utc     
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:       List of TaskInfo objects.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:        Main way to get information about the tasks run.
        
        """
        result = []
        for key in self.conn.scan_iter(match=self.task_master + '*'):
            item_json = self.conn.get(key)
            item_kw = json.loads(item_json.decode('utf8'))
            if not (status is None or item_kw['task_status'] == status):
                continue
            if not (start_utc is None or item_kw['start_utc'] >= start_utc):
                continue
            if not (end_utc is None or item_kw['end_utc'] <= end_utc):
                continue
            result.append(TaskInfo(**item_kw))
        return result

    @staticmethod
    def _regr_test():
        """
>>> import os, tempfile, datetime, time, random, imp
>>> random_key = random.randint(0,10000000) # so tests do not collide
>>> print('Using random_key = %s' % str(random_key)) # doctest: +ELLIPSIS
Using random_key = ...
>>> from ox_herd.core import ox_run_db
>>> ox_run_db.ox_settings.REDIS_PREFIX += ('test_%s' % random_key)
>>> ignore = imp.reload(ox_run_db)
>>> db = ox_run_db.RedisRunDB()
>>> task_id = db.record_task_start('test')
>>> time.sleep(1)
>>> db.record_task_finish(task_id, 'test_return')
>>> t = db.get_tasks()
>>> len(t)
1
>>> t[0].task_name
'test'
>>> t[0].task_status
'finished'
>>> task_id = db.record_task_start('test_again')
>>> len(db.get_tasks('finished'))
1
>>> len(db.get_tasks(None))
2
>>> db.delete_all(really=True)
>>> db.conn.keys(ox_run_db.ox_settings.REDIS_PREFIX + '*')
[]

"""


class SqliteRunDB(RunDB):
    """Implementation of RunDB with sqlite backend.

    Redis is preferred, but SqliteRunDB is also possible with more
    configuration.
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
          return_value text,
          json_blob text,
          pickle_blob text,
          template text
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

    def record_task_start(self, task_name, template=None):
        'Implement record_task_start for this backend.'

        sql = '''INSERT INTO task_info (
          task_name, task_start_utc, task_status, template) VALUES (?, ?, ?, ?)
        '''
        cursor = self.conn.cursor()
        cursor.execute(sql, [task_name, datetime.datetime.utcnow(), 'started',
                             template])
        task_id = cursor.lastrowid
        self.conn.commit()
        assert task_id is not None, (
            'Expected 1 task id for insert but got %s' % str(task_id))
        return task_id

    def delete_task(self, task_id):
        """Delete desired id.
        """
        sql = '''DELETE FROM task_info WHERE task_id = ?'''
        self.conn.execute(sql, task_id)


    def record_task_finish(self, task_id, return_value, status='finished',
                           json_blob=None, pickle_blob=None):
        'Implement record_task_finish for this backend.'

        sql = '''UPDATE task_info
        SET task_end_utc=?, return_value=?, task_status=?, 
            json_blob=?, pickle_blob=?
        WHERE task_id=?'''
        cursor = self.conn.cursor()
        utcnow = datetime.datetime.utcnow()
        cursor.execute(sql, [utcnow, return_value, str(status), json_blob,
                             pickle_blob, task_id])
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
              task_id, task_end_utc, return_value, task_status
              json_blob=?, pickle_blob=?) VALUES (
              'unknown', 'unknown', ?, ?, ?, ?)'''
            cursor.execute(sql, [json_blob, pickle_blob, task_id, 
                                 utcnow, return_value, status])

        self.conn.commit()

    def get_tasks(self, status='finished', start_utc=None, end_utc=None):
        """Return list of TaskInfo objects.
        
        :arg status='finished':   Status of tasks to search. Should be one
                                  entries from get_allowed_status().
        
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