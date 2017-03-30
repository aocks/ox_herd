"""Script to start the ox_herd server.

This is the main script to run ox_herd and provide a python Flask
based web server to respond to web requests.
"""

import argparse
import logging
import os

from flask import Flask, redirect, url_for
from flask.ext.login import LoginManager, UserMixin, login_required

DEFAULT_PORT = 4111

def prepare_parser(parser):
    "Prepare an arg parser to read command line."

    parser.add_argument('--debug', type=int, default=0, help=(
        'Use 1 for debug mode else 0; cannot have host=0.0.0.0 w/debug'))
    parser.add_argument('--host', default='0.0.0.0', help=(
        'IP address for allowed host (0.0.0.0 for all access).'))
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

    if args.host == '0.0.0.0':
        logging.warning('Setting host to 127.0.0.1 since in debug mode')
        args.host = '127.0.0.1'

    logging.getLogger('').setLevel(args.logging)


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
                'USERNAME' : 'admin', 'DEBUG' : True}

    app.config.from_object(__name__)
    app.config.update(settings)

    from ox_herd.ui.flask_web_ui import ox_herd
    from ox_herd.ui.flask_web_ui.ox_herd import views
    app.register_blueprint(ox_herd.OX_HERD_BP, url_prefix='/ox_herd')

    if settings['DEBUG']:
        from ox_herd.core import login_stub
        app.register_blueprint(login_stub.LOGIN_STUB_BP)

    @app.route("/")
    def redirect_to_ox_herd():
        "Simple redirect to blueprint root."
        return redirect(url_for("ox_herd.show_scheduled"))

    app.run(host=args.host,
            debug=True, #FIXME: debug=args.debug,
            port=int(args.port))


if __name__ == '__main__':
    run()
