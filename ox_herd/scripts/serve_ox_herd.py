"""Script to start the ox_herd server.

This is the main script to run ox_herd and provide a python Flask
based web server to respond to web requests.
"""

import configparser
import argparse
import logging
import os

from flask import Flask, redirect, url_for
from flask_login import LoginManager, UserMixin, login_required

from ox_herd import settings as ox_herd_settings

DEFAULT_PORT = 6617

def prepare_parser(parser):
    "Prepare an arg parser to read command line."

    parser.add_argument('--debug', type=int, default=0, help=(
        'Use 1 for debug mode else 0; cannot have host=0.0.0.0 w/debug'))
    parser.add_argument('--host', default='0.0.0.0', help=(
        'IP address for allowed host (0.0.0.0 for all access).'))
    parser.add_argument('--plugin', action='append', help=(
        'You can provide as many --plugin options as you like. Each\n'
        'must be the path to an ox herd plugin to enable. For example\n'
        'providing "--plugin ox_herd.core.plugins.pytest_plugin" would\n'
        'enable the pytest plugin if it was not already enabled.'))
    parser.add_argument('--port', default=DEFAULT_PORT, help=(
        'IP port to listen on.'))
    parser.add_argument('--base_url', help=(
        'Base URL to use for ox_herd site. This is usually automatically\n'
        'but you can override when testing.'))
    parser.add_argument('--logging', type=int, default=logging.INFO, help=(
        'Python logLevel. Use %i for DEBUG, %i for INFO, etc.' % (
            logging.DEBUG, logging.INFO)))

def run():
    "Main function to run server."

    parser = argparse.ArgumentParser(
        description='Command line tool to run ox_herd server')
    prepare_parser(parser)
    args = parser.parse_args()
    _do_setup(args)
    _serve(args)

def _do_setup(args):
    "Should be called by run() to do basic setup based on args."

    if args.debug and args.host == '0.0.0.0':
        logging.warning('Setting host to 127.0.0.1 since in debug mode')
        args.host = '127.0.0.1'

    logging.getLogger('').setLevel(args.logging)
    logging.info('Set log level to %s', args.logging)
    plugin_list = args.plugin if args.plugin else []
    plug_set = set(plugin_list)
    if len(plug_set) < len(plugin_list):
        raise ValueError('Duplicates in args.plugin = %s' % plugin_list)
    cur_plugs = set(ox_herd_settings.OX_PLUGINS)

    for item in plugin_list:
        if item not in cur_plugs:
            logging.info('Adding plugin %s to OX_PLUGINS.', item)
            ox_herd_settings.OX_PLUGINS.append(item)
        else:
            logging.info(
                'Not adding plugin %s to OX_PLUGINS since already there.', item)

def _setup_stub_login(app):
    conf_file = ox_herd_settings.OX_HERD_CONF
    if os.path.exists(conf_file):
        from ox_herd.core import login_stub
        app.register_blueprint(login_stub.LOGIN_STUB_BP)
        my_config = configparser.ConfigParser()
        my_config.read(conf_file)
        if 'STUB_USER_DB' in my_config:
            for user, hash_password in my_config.items('STUB_USER_DB'):
                ox_herd_settings.STUB_USER_DB[user] = hash_password
        else:
            logging.warning('Unable to find STUB_USER_DB in conf %s',
                            conf_file)
    else:
        logging.warning('Unable to find OX_HERD_CONF at %s',
                        ox_herd_settings.OX_HERD_CONF)


def _serve(args):
    "Run the server. Should only be called by run after doing setup."

    if args.host == '0.0.0.0':
        if args.debug:
            raise TypeError('Cannot have host 0.0.0.0 with debug mode')
    else:
        logging.warning('Host = %s. When host != 0.0.0.0 non-local connections '
                        '\nwill be *IGNORED*. Only use for testing.', args.host)

    app = Flask('ox_herd')

    settings = {'SECRET_KEY' : os.urandom(128),
                'USERNAME' : 'admin', 'DEBUG' : args.debug}

    app.config.from_object(__name__)
    app.config.update(settings)

    from ox_herd.ui.flask_web_ui import ox_herd
    from ox_herd.ui.flask_web_ui.ox_herd import views
    app.register_blueprint(ox_herd.OX_HERD_BP, url_prefix='/ox_herd')
    _setup_stub_login(app)

    assert bool(settings['DEBUG']) == bool(args.debug), (
        'Inconsistent debug values from settings and args.')

    @app.route("/")
    def redirect_to_ox_herd():
        """Simple redirect to blueprint root.

        This is required so we can redirect from the top-level path
        when running ox_herd in stand-alone mode.
        """
        return redirect(url_for("ox_herd.index"))
    logging.debug('Created %s for initial redirection', redirect_to_ox_herd)

    app.run(host=args.host, debug=args.debug, port=int(args.port))


if __name__ == '__main__':
    run()
