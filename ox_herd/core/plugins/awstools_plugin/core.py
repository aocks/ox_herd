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
    def move_file_to_s3(cls, fname, bucket_name, remote_name, **botokw):
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
            logging.info('Using local file location for bucket "%s"',
                         bucket_name)
            remote_name = os.path.join(bucket_name[1:], remote_name)
            os.makedirs(os.path.dirname(remote_name))
            shutil.copy(fname, remote_name)
        else:
            session = boto3.Session(**botokw)
            s3_client = session.client('s3')

            s3_client.upload_file(fname, bucket_name, remote_name)

    @classmethod
    def make_dump_cmdline(cls, ox_herd_task, outfile):
        """Make command line to use to dump database.
        """
        return ['pg_dump', '-w', '-f', outfile, '--dbname=%s' % (
            cls.get_conn_string(ox_herd_task))]

    @classmethod
    def backup_pion_db(cls, ox_herd_task):
        """Do main work of backing up database to S3.
        """
        msgs, status = [], None
        remote_name = 'postgres_backups/%s/%s' % (
            ox_herd_task.prefix, datetime.datetime.utcnow().strftime(
                'backup_%A.sql.gz'))

        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = os.path.join(tmpdir, 'dump.sql')
            msgs.append(cls._do_dump(ox_herd_task, outfile))

            with open(outfile, 'rb') as f_in:
                with gzip.open(outfile + '.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            cls.move_file_to_s3(outfile + '.gz', ox_herd_task.bucket_name,
                                remote_name)

        msgs += ['Finished backup succesfully\nStatus=%s\n.' % (
            status)]

        return '\n'.join(msgs)

    @classmethod
    def _do_dump(cls, ox_herd_task, outfile):
        """

        :param ox_herd_task:   Task controlling the dump.

        :param outfile:        String path to output dump.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:   String describing result of dump.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   Create a subprocess to dump to outfile.

        """
        cmd = cls.make_dump_cmdline(ox_herd_task, outfile)
        logging.info('Running cmd: %s', str(cmd))
        logging.info('Dumping DB to temp file %s and then aws',
                     outfile)
        popen = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        try:
            status = popen.wait(timeout=ox_herd_task.timeout)
        except subprocess.TimeoutExpired as prob:
            logging.error('Timeout while trying to do backup: %s',
                          str(prob))
            raise
        if status != 0:
            msg = 'Got non-zero exist status %s; stderr=%s' % (
                status, popen.stderr.read())
            logging.error(msg)
            raise ValueError(msg)
        return 'Finished dump: extra messages="%s".' % (
            popen.stderr.read())
