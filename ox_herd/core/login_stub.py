"""Stub module for login to allow stand-alone usage.

If you import this module via something like

        from ox_herd.core import login_stub
        app.register_blueprint(login_stub.LOGIN_STUB_BP)

you will enable a simple stub login.
"""

from passlib.apps import custom_app_context as pwd_context

from flask import (Response, redirect, url_for, request,
                   Blueprint, flash, get_flashed_messages, escape)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user, login_required)

from ox_herd import settings

LOGIN_STUB_BP = Blueprint('login_stub', __name__)
LOGIN_MANAGER = LoginManager()

@LOGIN_STUB_BP.record_once
def on_load(state):
    "Initialize login manager"

    LOGIN_MANAGER.init_app(state.app)

class User(UserMixin):

    def __init__(self, uname):
        self.id = uname
        self.name = uname

@LOGIN_STUB_BP.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = settings.STUB_USER_DB.get(username, 'disabled')
        if password_hash != 'disabled' and pwd_context.verify(
                password, password_hash):
            user = User(username)
            login_user(user)
            next_url = request.args.get("next", '')
            next_url = next_url if next_url.strip().lower() != 'none' else (
                url_for('ox_herd.index'))
            return redirect(next_url)
        else:
            flash('Login failed to login as %s; try again' % username)
            if password_hash == 'disabled':
                flash('WARNING: username %s is disabled' % username)
            return redirect(url_for('login_stub.login'))
    else:
        messages = get_flashed_messages()
        flashes = '<UL>\n%s\n</UL>' % '\n'.join([
            '<LI>%s</LI>' % escape(m) for m in messages]) if messages else ''
        return Response(
            flashes + '''
            <h1>ox_herd login</h1>
            <p>
            Welcome to ox_herd! 
            You are running the stand-alone ox_herd server.            
            </p>
            <p>
            To interact, you need to login.
            See the ox_herd/settings.py file to setup a trivial 
            username/password dictionary to use with this stub login system.
            <p>
            Ideally, we will develop a better login setup for ox_herd or you
            can use ox_herd as a blueprint in a larger flask fraemwork that
            already handles its own login.
            </p>
        <form action="" method="post">
            <p><input type=text name=username>
            <p><input type=password name=password>
            <p><input type=submit value=Login>
        </form>
        ''')


# somewhere to logout
@LOGIN_STUB_BP.route("/logout")
@login_required
def logout():
    "Simple logout function."
    logout_user()
    return Response('<p>Logged out</p>')


@LOGIN_MANAGER.user_loader
def load_user(userid):
    "Callback to reload the user object"

    return User(userid)



@LOGIN_MANAGER.unauthorized_handler
def unauthorized():
    """Return response for when user is not logged in.
    """
    return redirect(url_for('login_stub.login'))
