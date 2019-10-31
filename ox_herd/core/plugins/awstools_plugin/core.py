"""Module containing some plugin to run pytest.
"""

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
                 bucket_name=None, timeout=1800, **kw):
        """Initializer.

        :arg *args:    Argumnets to OxHerdTask.__init__.

        :arg conn_string:  Connection string to database.

        :arg **kw:     Keyword arguments to OxHerdTask.__init__.

        """
        OxHerdTask.__init__(self, *args, **kw)
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

    @staticmethod
    def move_fd_to_s3(my_fd, bucket_name, remote_name, profile_name=None):
        """Move data in file descriptor to s3.

        :param my_fd:        File descriptor with data.

        :param profile_name=None:  Optional profile to use for S3.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Move data in file descriptor to s3.

        """
        session = boto3.Session(profile_name=profile_name)
        s3_client = session.client('s3')
        my_fd.seek(0)
        s3_client.upload_file(
            my_fd.name, bucket_name, remote_name)

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
            zipper = gzip.GzipFile(remote_name, 'wb', 9, my_fd)
            cmd = ['pg_dump', '-w', '--dbname=%s' % cls.get_conn_string(
                ox_herd_task)]
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

            # Note that on UNIX can just send my_fd.name but windows
            # would need to use my_fd but boto seems stupid about that.
            cls.move_fd_to_s3(my_fd, ox_herd_task.bucket_name, remote_name)

        msgs = ['Finished backup succesfully\nStatus=%s\n%s bytes written.' % (
            status, written)]
        msgs.append(popen.stderr.read().strip())
        if msgs[-1]:
            msgs[-1] = 'Errors: %s' % str(msgs[-1])

        return '\n'.join(msgs)
