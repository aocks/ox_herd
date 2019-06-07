"""Classes to help automate web tasks.
"""

import re
import logging
import urllib.parse

import requests

from ox_herd.core.plugins import base
from ox_herd.core import ox_tasks


class SimpleTaskResult:
    """Class to hold task result.

Clairfying the expected return values for a task makes it easier to display
and inspect task results with other tools.
    """

    def __init__(self, return_value: str, full_text: str = None,
                 status_code: int = 0, reason: str = 'OK',
                 extras: dict = None):
        """Initializer.

        :param return_value:str: String return value to display as task
                                 status.

        :param full_text:str:   Full text of result/response. This is typically
                                the full response to an HTTP request. You can
                                provide '' if you want to save space. If you
                                provide None, then we use return_value.

        :param status_code:int: Status code from an HTTP request. Use 0 if
                                was not an HTTP request.

        :param reason:str='OK': String reason provided for HTTP response. Use
                                'NA' if not an HTTP response.

        :param extras=None:  Optional dict of additional data.

        """
        self.return_value = return_value
        self.full_text = full_text if full_text is not None else return_value
        self.status_code = status_code
        self.reason = reason
        self.extras = extras if extras else {}

    @classmethod
    def fields(cls) -> list:
        """Return list of strings describing main fields in self.

Sub-classes can override if they want additional fields to showup
in to_dict.
        """

        _ = cls
        return ['return_value', 'full_text', 'status_code',
                'reason', 'extras']

    def to_dict(self) -> dict:
        "Return dict with data in self.fields()"
        return {n: getattr(self, n) for n in self.fields()}


class SimpleWebTask(ox_tasks.OxHerdTask, base.OxPluginComponent):
    """Generic command that can be sub-classed for automation.
    """

    def __init__(self, *args, base_url=None, base_port='', **kwargs):
        """Initializer.

        :arg base_url=None:        String url for where your server lives (or
                                   where the version you want to use lives).
        """
        if not args and 'name' not in kwargs:
            kwargs['name'] = self.__class__.__name__
        ox_tasks.OxHerdTask.__init__(self, *args, **kwargs)

        # Never use base_url/base_port directly. Instead call
        # set_base_url and make_url so we handle ports correctly.
        self.__base_url = ''
        self.__base_port = None
        self.set_base_url(base_url, base_port)

    def set_base_url(self, base_url: str, base_port: str = None):
        """Set the base_url (and optinally base_port).

        :param base_url:    String like http://foo or http://bar:9999

        :param base_port=None: Optional base_port if not in base_url.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Set base URL and port to use in connections.

        """
        self.__base_url = base_url if base_url else self.make_base_url()
        if not self.__base_url:
            return
        my_base, my_port = urllib.parse.splitport(self.__base_url)
        if my_port:
            self.__base_url = my_base  # take off port and store in base_port
            if base_port:
                raise ValueError('base_url=%s has port and base_port=%s' % (
                    self.__base_url, base_port))
            base_port = my_port
        self.__base_port = base_port

    def make_url(self, path: str = '') -> str:
        """Make url with given path.

        :param path='': Optional relative path.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  Full string URL.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Combine base URL and port set with set_base_url with path.

        """
        result = self.__base_url
        if not result:
            logging.error('self.__dict__: %s', str(self.__dict__))
            raise ValueError('Must have base_url set to call make_url')
        if self.__base_port:
            result += ':' + str(self.__base_port)
        result += '/' + path.lstrip('/')

        return result

    @classmethod
    def make_base_url(cls) -> str:
        """Return string indicating base URL or None if not known.

Sub-classes can override if they know a good default. Otherwise,
should call set_base_url when they have the url to use.
        """
        return None

    def get_login_info(self) -> (str, str):
        """Return string login field and login value

Sub-classes may want to override.
        """
        return 'username', getattr(self, 'username', 'test_user')

    def get_password(self, login_name: str) -> str:
        "Get password for given login name"
        return self.get_secret(login_name, 'test_passwords')

    @classmethod
    def get_login_route(cls) -> str:
        "Return path to login route."

        _ = cls
        return '/login'

    @classmethod
    def get_secret(cls, name: str, category: str = 'root') -> str:
        """Lookup a secret like a password or something.

        :param name:     Name of secret to lookup

        :param category='root':    Category of secret.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  A string reprsenting the secret you want to get.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Provide a way to lookup secrets like passwords, etc.

        """
        raise NotImplementedError

    def setup_session(self):
        """Setup a requests.session and return it.

This sets up a session so we are logged in to whatever we get
from self.make_url(self.get_login_route()) using the login from
get_login_info().
        """
        session = requests.session()
        my_url = self.make_url(self.get_login_route())
        csrf_field, csrf = None, None
        try:
            csrf_field, csrf = self.get_csrf_from_form(session, my_url)
        except Exception as problem:
            logging.error('Failed to get csrf due to exception: %s', str(
                problem))
            logging.error('Maybe override get_csrf_from_form?')
            raise

        login_field, login_name = self.get_login_info()
        password = self.get_password(login_name)
        data = {login_field: login_name, 'password': password}
        if csrf:
            data[csrf_field] = csrf
        post_resp = session.post(my_url, data, verify=False)
        if post_resp.status_code != 200:
            raise ValueError('Got unexpected status/reason: %s/%s in login' % (
                post_resp.status_code, post_resp.reason))
        return session

    def do_main(self, session) -> SimpleTaskResult:
        """Sub-classes should override this to do the main work.

Sub-classes should override this to return an instance of SimpleTaskResult
describing the result of running the task. See docs for SimpleTaskResult
for more details.
        """
        raise NotImplementedError

    @classmethod
    def main_call(cls, ox_herd_task):
        logging.info('Starting main_call for %s', cls.__name__)
        session = ox_herd_task.setup_session()
        result = ox_herd_task.do_main(session)
        msg = 'Go return_value %s' % (result.return_value)
        cls.note_comment(ox_herd_task, msg)

        return result

    @classmethod
    def note_comment(cls, ox_herd_task: ox_tasks.OxHerdTask,
                     comment: str):
        """Note a comment for a task we ran.

        :param ox_herd_task:    Task we ran.

        :param comment:         Comment to note.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Mainly a placeholder in case sub-classes want
                  to do some kind of logging for comments.

        """
        _ = cls
        logging.info('Comment for task %s: %s', ox_herd_task.name,
                     comment)

    @staticmethod
    def get_csrf_from_form(
            session, url: str, csrf_field: str = 'csrf_token',
            csrf_re: str = None) -> (str, str):
        """Do a get request for the given url and extract CSRF token.

        :param session:    Session we have to the web site.

        :param url:        String URL for form with CSRF token.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:  String name for CSRF field and string for CSRF token.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:  Flask WTForms provides a CSRF token to prevent CSRF
                  attacks. We need to hit the url with a GET request to
                  get the csrf_token and include that as a parameter of
                  our POST request. This function gets the csrf_token.
        """
        result = session.get(url)
        csrf_re = csrf_re if csrf_re else ' *'.join([
            'id="%s"' % csrf_field, 'name="%s"' % csrf_field,
            'type="hidden"', 'value="(?P<csrf>[^"]*)">'])
        if isinstance(csrf_re, str):
            csrf_re = re.compile(csrf_re)
        match = csrf_re.search(result.text)
        if not match:
            raise ValueError('Could not extract csrf from url "%s"' % url)
        return csrf_field, match.group('csrf')

    def raise_on_bad_status(self, result):
        """Raise ValueError if http response looks like an error.

        :param result:        Response from an HTTP command such as what
                              do_main might report.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :return:   False if no problems, otherwise raises an exception.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:   Raise an exception if result looks like an error.

        """
        if result.status_code != 200:
            msg = 'Problem in task %s with reason: "%s"' % (
                self.__class__.__name__, result.reason)
            logging.error(msg)
            raise ValueError(msg)
        if ' error' in result.text.lower():
            self.note_comment(self, 'Saw error in result: ' + str(result))
            if isinstance(result.reason, str):
                my_reason = result.reason
            else:
                my_reason = result.reason.text
            msg = 'Saw "error" in result for task %s: "%s"' % (
                self.__class__.__name__, my_reason)
            logging.error(msg)
            raise ValueError(msg)

        return False
