"""Tests for awstools plugin.
"""

import shutil
import os
import tempfile


from ox_herd.core.plugins.awstools_plugin import core


class TestableBackupTask(core.BackupPostgresToAWS):
    """Sub-class of BackupPostgresToAWS for testing.
    """

    @classmethod
    def make_dump_cmdline(cls, ox_herd_task, outfile):
        """Override to just cat file for dump to simplify testing.
        """
        return ['cp', cls.get_conn_string(ox_herd_task), outfile]

    @staticmethod
    def get_conn_string(ox_herd_task):
        """Provide simplified version for testing in case we want override.

Helpful if we deal with a sqlite connection string.
        """
        return ox_herd_task.conn_string.split('://')[-1]


def test_basic_operation():
    "Test simplified version of backup task."
    try:
        db_loc = tempfile.mktemp()
        backup_loc = tempfile.mktemp()
        os.mkdir(backup_loc)
        open(db_loc, 'w').write('test_data.txt')
        task = TestableBackupTask(
            name='test_task', conn_string=db_loc, prefix='test',
            bucket_name='@'+backup_loc)
        result = task.main_call(task)
        assert result['return_value'].split()[:4] == [
            'Finished', 'dump:', 'extra', 'messages="b\'\'".']
    finally:
        for name in [db_loc]:
            if os.path.exists(name):
                os.remove(name)
        if os.path.exists(backup_loc):
            shutil.rmtree(backup_loc)
