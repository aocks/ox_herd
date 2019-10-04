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
