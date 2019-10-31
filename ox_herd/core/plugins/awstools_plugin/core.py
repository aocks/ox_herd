"""Module containing some plugin to run pytest.
"""

import os
import shutil
import datetime
import gzip
import logging
import tempfile
import subprocess

import boto3

from ox_herd.core.plugins import base
from ox_herd.core.ox_tasks import OxHerdTask
from ox_herd.core.plugins.awstools_plugin import forms


class OxHerdAWSToolsPlugin(base.OxPlugin):
    """Plugin to provide AWS services for ox_herd
    """

    __blueprint = None

    @classmethod
    def set_bp(cls, my_bp):
        """Set blueprint class variable.
        """
        cls.__blueprint = my_bp

    def get_flask_blueprint(self):
        """Implement as required by OxPlugin."""

        return self.__class__.get_bp()

    @classmethod
    def get_bp(cls):
        """Get blueprint class variable.
        """
        return cls.__blueprint

    def name(self):
        """Implement as required by OxPlugin."""

        return 'awstools_plugin'

    def description(self):
        """Implement as required by OxPlugin."""

        return "Plugin to provide AWS tools for ox_herd."

    def get_components(self):
        return [BackupPostgresToAWS()]


class BackupPostgresToAWS(OxHerdTask, base.OxPluginComponent):
    """Task to backup postgres instance to AWS
    """

    def __init__(self, *args, conn_string=None, prefix=None,
                 bucket_name=None, timeout=1800, **kwargs):
        """Initializer.

        :arg *args:    Argumnets to OxHerdTask.__init__.

        :arg conn_string:  Connection string to database.

        :arg **kwargs:     Keyword arguments to OxHerdTask.__init__.

        """
        OxHerdTask.__init__(self, *args, **kwargs)
        self.conn_string = conn_string
        self.prefix = prefix
        self.bucket_name = bucket_name
        self.timeout = timeout

    @classmethod
    def get_flask_form_via_cls(cls):
        """Get flask form class to enter parameters.
        """
        result = forms.BackupForm
        logging.debug('Providing form %s for cls %s', result, cls)
        return result

    @staticmethod
    def get_conn_string(ox_herd_task):
        """Get connection string from class.

By default we just look for ox_herd_task.conn_string but sub-classes can
override to pull from secret vault or something.
        """
        return ox_herd_task.conn_string

    @classmethod
    def main_call(cls, ox_herd_task):

        rval = cls.backup_pion_db(ox_herd_task)
        return {'return_value': rval}

    @classmethod
    def move_file_to_s3(fname, bucket_name, remote_name, **botokw):
        """Move data in file descriptor to s3.

        :param fname:        Path to file to move.

        :param bucket_name:  String name of S3 bucket. If this starts with
                             '@' then we write to location bucket[1:] (this
                             is useful for testing).

        :param **botokw:  Keyword args for boto (e.g., profile, key, etc.).

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Move data in file descriptor to s3.

        """
        if not bucket_name:
            raise ValueError('Invalid bucket_name: "%s"' % str(bucket_name))
        if bucket_name[0] == '@':
            logging.info('Using local file location for bucket "%s"' % str(
                bucket_name))
            remote_name = os.path.join(bucket_name[1:], remote_name)
            os.makedirs(os.path.dirname(remote_name))
            shutil.copy(fname, remote_name)
        else:
            session = boto3.Session(**botokw)
            s3_client = session.client('s3')

            s3_client.upload_file(fname, bucket_name, remote_name)

    @classmethod
    def make_dump_cmdline(cls, ox_herd_task):
        """Make command line to use to dump database.
        """
        return ['pg_dump', '-w', '--dbname=%s' % cls.get_conn_string(
            ox_herd_task)]        
        
    @classmethod
    def backup_pion_db(cls, ox_herd_task):
        """Do main work of backing up database to S3.
        """
        status = None
        written = 0
        remote_name = 'postgres_backups/%s/%s' % (
            ox_herd_task.prefix, datetime.datetime.utcnow().strftime(
                'backup_%A.sql.gz'))

        with tempfile.NamedTemporaryFile(mode='wb') as my_fd:
            logging.info('Using tempfile %s', getattr(my_fd, 'name', '?'))
            zipper = gzip.GzipFile(remote_name, 'wb', 9, my_fd)
            cmd = cls.make_dump_cmdline(ox_herd_task)
            logging.info('Dumping DB to temp file %s and then aws', my_fd.name)
            popen = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     universal_newlines=True)
            for stdout_line in iter(popen.stdout.readline, ''):
                written += zipper.write(bytes(stdout_line, 'utf8'))
            popen.stdout.close()
            status = popen.wait(timeout=ox_herd_task.timeout)
            zipper.close()
            if not written:
                raise ValueError('Did not get any backup data')

            cls.move_file_to_s3(my_fd.name, ox_herd_task.bucket_name,
                                remote_name)

        msgs = ['Finished backup succesfully\nStatus=%s\n%s bytes written.' % (
            status, written)]
        msgs.append(popen.stderr.read().strip())
        if msgs[-1]:
            msgs[-1] = 'Errors: %s' % str(msgs[-1])

        return '\n'.join(msgs)
