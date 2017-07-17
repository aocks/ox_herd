"""An ox_herd plugin for posting messages to github.

This module provides a single class: PostToGitHub to post messages to github.
It is useful as a tool for the pylint plugin and perhaps others.

Provided that you include this plugin in the OX_PLUGINS variable in
ox_herd.settings or in your OX_PLUGINS environment variable, this will be
picked up automatically and used as a plugin.

In general, there are a variety of more complicated things you can do
in configuring plugins. See documentation on plugins or see the pytest_plugin
example for more details.
"""

import configparser
import json

from eyap.core import github_comments

from ox_herd.core.plugins import base
from ox_herd.core.ox_tasks import OxHerdTask


class PostToGitHub(OxHerdTask, base.OxPluginComponent):
    """Class to post a message to github.

    """

    def __init__(self, msg, full_repo, title, number, conf_file, conf_sec,
                 *args, **kw):
        """Initializer.

        :arg msg:      String message to post.

        :arg full_repo: Full name of github repo (e.g., 'aocks/ox_herd').

        :arg title:     String title of issue to post to *ONLY* if no
                        github_issue is specified in the conf file (see below).
                        This will be ignored if github_issue is provided.

        :arg number:    Optional issue number. This is useful if you have
                        multiple issues with the same title and need to
                        distinguish between them.

        :arg conf_file: Path to configuration file to be read by python
                        configparser module.

        :arg conf_sec:  String name of section in conf_file to read. 
                        This section should have entries for the following:

                           github_user:  Name of github user for login.
                           github_token: Token or password to access github.
                           github_issue: Optional issue title to use instead of
                                         title argument.
        
        :arg *args:    Argumnets to OxHerdTask.__init__.
        
        :arg **kw:     Keyword arguments to OxHerdTask.__init__.
        
        """
        OxHerdTask.__init__(self, *args, **kw)
        base.OxPluginComponent.__init__(self)
        self.msg = msg
        self.full_repo = full_repo
        self.title = title
        self.number = number
        self.conf_file = conf_file
        self.conf_sec = conf_sec

    @classmethod
    def main_call(cls, ox_herd_task):
        """Main method to post to github.

        :arg ox_herd_task:   Instance of a PostToGitHub task perhaps containing
                             additional data (e.g., ox_herd_task.name). 

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        :returns:       Dictionary with 'return_value' and 'json_blob' as
                        required for OxPluginComponent.

        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-

        PURPOSE:        Post a message to github.

        """
        my_config = configparser.ConfigParser()
        my_config.read(ox_herd_task.conf_file)
        my_csec = my_config[ox_herd_task.conf_sec]
        cthread = cls.prep_comment_thread(
            ox_herd_task.title, ox_herd_task.number, ox_herd_task.full_repo,
            my_csec)
        cthread.add_comment(ox_herd_task.msg, allow_create=True)

        return {
            'return_value': 'Task %s completed succesfully.' % (
                ox_herd_task.name), 'json_blob': json.dumps({})}


    @staticmethod
    def prep_comment_thread(title, number, full_repo, my_conf):
        """Prepare a CommentThread object to use in positing comments.
        
        :arg ox_herd_task: Ox Herd task with raw data.       
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        :returns:  A GitHubCommentThread object.
        
        ~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-~-
        
        PURPOSE:   This method reads from the configuration in the dictionary
                   in my_conf, figures out the github parameters, and creates a
                   GitHubCommentThread we can use in posting comments.
        """
        user = my_conf['github_user']
        token = my_conf['github_token']
        topic = my_conf['github_issue'] if 'github_issue' in my_conf else None

        if topic is None:
            topic = title
            thread_id = number
            if isinstance(thread_id, str):
                thread_id = thread_id.strip()
            if thread_id == '':
                thread_id = None
        else:
            thread_id = None

        owner, repo = full_repo.split('/')

        comment_thread = github_comments.GitHubCommentThread(
            owner, repo, topic, user, token, thread_id=thread_id)

        return comment_thread        
