"""Utilities used by other tests.
"""

import sys
import os
import socket
import logging
import subprocess
import weakref
import unittest
import random

from passlib.apps import custom_app_context as pwd_context

import ox_herd


class ServerInfo:  # pylint: disable=too-few-public-methods
    """Information about an server running for testing.
    """

    def __init__(self, server, port, health_token, stub_user=None):
        self.server = server
        self.port = port
        self.health_token = health_token
        self.stub_user = stub_user


def start_server(
        debug='1',     # Need debug 1 so we can use tests endpoint
        reloader='0',  # Need to use reload 0 to prevent flask weirdness
        ox_port=None, cwd=None, stub_user=None):
    """Start flask server.

    :param debug='1':     Whether to run in debug mode.

    :param reloader='0':  Whether to use reloader in server. Often this
                          causes problems so it is best not to.

    :param ox_port=None:  Optional port for server. If None, we choose.

    :param cwd=None:      Current working directory to run in. If None,
                          we run in ox_herd root.

    :param stub_user=None:  Optional --stub_user argument (in the form
                            of <user>:<passwd>) for stub db for testing.
                            If None, we will randomly generate it.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    :return:  Instance of ServerInfo containing information about the
              server we started.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    PURPOSE:  Use python subprocess module to start an instance of the
              server in the background. You can use the returned
              ServerInfo instance to interact with the server. This is
              useful for making the test self-contained.

              You can call kill_server to cleanup.
    """
    health_token = random.randint(0, 1e20)
    server_script = os.path.join(os.path.dirname(ox_herd.__file__),
                                 'scripts', 'serve_ox_herd.py')
    cwd = cwd if cwd else os.path.join(os.path.dirname(ox_herd.__file__))
    ox_port = ox_port if ox_port else str(find_free_port())
    cmd = [sys.executable, server_script, '--debug', str(debug),
           '--port', ox_port, '--health_token', str(health_token),
           '--plugin', 'ox_herd.core.plugins.example_psutil_plugin']
    if not stub_user:
        stub_user = '%s:%s' % (
            random.randint(0, 1e10), random.randint(0, 1e10))
    cmd.extend(['--stub_user', '%s:%s' % (
        stub_user.split(':')[0], pwd_context.hash(stub_user.split(':')[1]))])
    server = run_cmd(cmd=cmd, cwd=cwd, timeout=-4)
    return ServerInfo(server, int(ox_port), health_token,
                      stub_user=stub_user)


def run_cmd(cmd, cwd=None, timeout=30):
    """Helper to run a command in a subprocess.

    :param cmd:   List of strings for commands to run.

    :param cwd=None:    Optional current working directory string.
                        If None, we use ox_herd root.

    :param timeout=30:  Timeout in seconds before killing command.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    :return:  The subprocess created to run the command.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    PURPOSE:  Provides some convenience for calling subprocess.Popen
              to run subprocess commands.

    """
    if cwd is None:
        cwd = os.path.join(os.path.dirname(ox_herd.__file__))
    logging.info('Running cmd: %s', str(cmd))
    proc = subprocess.Popen(cmd, cwd=cwd)
    if timeout is not None:
        try:
            result = proc.wait(timeout=abs(timeout))
        except subprocess.TimeoutExpired:
            if timeout < 0:
                result = proc.returncode  # timeout is OK
            else:
                raise  # timeout not ok so re-raise it
    else:
        result = proc.returncode
    if result:
        raise ValueError('Error code "%s" in cmd "%s"' % (
            result, proc))
    return proc


def find_free_port():
    "Find and return a free port number"

    result = None
    my_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        my_sock.bind(('', 0))
        my_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        result = my_sock.getsockname()[1]
    finally:
        my_sock.close()
    return result


def cleanup(cleanup_files, server_info=None):
    """Cleanup files and server.

    :param cleanup_files:  List of files to remove.

    :param server_info=None:  Instance of ServerInfo to clean.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    :return:  A weakref to server_info.server if we stop it.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    PURPOSE:  Cleanup by remoging cleanup_files and stopping
              server_info.server if they exist.

    """
    for name in cleanup_files:
        if os.path.exists(name):
            logging.info('Removing file %s', name)
            os.remove(name)
            assert not os.path.exists(name), 'Could note remove ' + name

    if server_info is None:
        return None
    kill_server(server_info)
    dead_server = weakref.ref(
        server_info.server)  # keep weakref for debugging

    return dead_server


def kill_server(server_info):
    """Kill server to cleanup.

    :param server_info:   Instance of ServerInfo.

    ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

    PURPOSE:  Terminate server in server_info.server.

    """
    timeout = 10
    server_info.server.terminate()
    status = server_info.server.wait(timeout=timeout)
    if status is None:
        logging.warning('Server failed to terminate; killing')
        server_info.server.kill()
        status = server_info.server.wait(timeout=timeout)
        if status is None:
            raise ValueError('Server refused to die')


class SelfContainedTest(unittest.TestCase):
    """Self contained test to start a flask server and tear it down.
    """

    _serverInfo = None

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        """Setup the class to have a running server.
        """
        if cls._serverInfo is not None:
            raise ValueError('Refusing to setup since _serverInfo not empty')
        cls._serverInfo = start_server()

    @classmethod
    def tearDownClass(cls):  # pylint: disable=invalid-name
        """Tear down the class.
        """
        kill_server(cls._serverInfo)
        cls._serverInfo = None
