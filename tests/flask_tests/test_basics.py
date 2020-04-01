"""Basic tests.
"""

import logging
import random

import requests

from ox_herd.core.utils import test_utils


class SimpleTest(test_utils.SelfContainedTest):
    """Run some simple tests.
    """

    _user_info = {}

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        if not cls._user_info:
            cls._user_info = {
                'generic': str(random.randint(0, 1e20)),
                'test_admin': str(random.randint(0, 1e20))
                }
        stub_info = ','.join(['%s:%s' % (k, v)
                              for k, v in cls._user_info.items()])
        cls._serverInfo = test_utils.start_server(
            stub_user=stub_info, stub_roles='test_admin:admin')
    
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
            self._serverInfo.port), {
                'username': 'test_admin',
                'password': self._user_info['test_admin']})
        url = 'http://localhost:%i/ox_herd/use_plugin' % self._serverInfo.port
        result = session.get(url, params={
            'plugname': 'ox_herd.core.plugins.example_psutil_plugin',
            'plugcomp': 'CheckCPU'})
        self.assertEqual(result.reason, 'OK')
        self.assertEqual(result.status_code, 200)

    def test_access_restricted_ox_herd(self):
        "Verify that non-admin user cannot access ox_herd views"

        self.check_access_restricted_ox_herd(
            'generic', 'FORBIDDEN', 403)
        self.check_access_restricted_ox_herd('test_admin')

    def check_access_restricted_ox_herd(
            self, username, reason='OK', status=200):
        session = requests.session()
        result = session.post('http://localhost:%i/login' % (
            self._serverInfo.port), {'username': username,
                                     'password': self._user_info[username]})
        self.assertEqual(result.status_code, 200)

        url = 'http://localhost:%i/ox_herd/show_scheduled' % (
            self._serverInfo.port)
        result = session.get(url)
        self.assertEqual(result.reason, reason)
        self.assertEqual(result.status_code, status)
