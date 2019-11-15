"""Basic tests.
"""

import logging
import random

import requests

from ox_herd.core.utils import test_utils


class SimpleTest(test_utils.SelfContainedTest):
    """Run some simple tests.
    """

    def test_good_health_check(self):
        "Verify that health check is OK"

        logging.debug('Doing test_good_health_check on %s', str(self))
        result = requests.get(
            'http://localhost:%i/ox_herd/health_check?token=%s' % (
                self._serverInfo.port, self._serverInfo.health_token))
        self.assertEqual(result.status_code, 200)

    def test_bad_health_check(self):
        "Verify that health check returns 500 if try on non-existing queue"

        logging.debug('Doing test_bad_health_check on %s', str(self))
        queue = 'some_random_bad_queue_%s' % random.randint(0, 1e20)
        params = 'token=%s&check_queues=%s' % (
            self._serverInfo.health_token, queue)
        expect_bad = requests.get(
            'http://localhost:%i/ox_herd/health_check?%s' % (
                self._serverInfo.port, params))
        self.assertEqual(expect_bad.status_code, 500)

    def test_configure_job(self):
        """Test that we can trigger job configuration without error.
        """
        session = requests.session()
        session.post('http://localhost:%i/login' % (
            self._serverInfo.port), dict(zip(
                ['username', 'password'],
                self._serverInfo.stub_user.split(':'))))
        url = 'http://localhost:%i/ox_herd/use_plugin' % self._serverInfo.port
        result = session.get(url, params={
            'plugname': 'ox_herd.core.plugins.example_psutil_plugin',
            'plugcomp': 'CheckCPU'})
        self.assertEqual(result.reason, 'OK')
        self.assertEqual(result.status_code, 200)
