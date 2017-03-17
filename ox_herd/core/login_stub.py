"""Stub module for login to allow stand-alone usage.

If you import this module via something like

        from ox_herd.core import login_stub
        app.register_blueprint(login_stub.LOGIN_STUB_BP)

you will enable a simple stub login.
"""

from flask import (Response, redirect, url_for, request,
                   Blueprint, flash, get_flashed_messages, escape)
from flask.ext.login import (
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
        if username in settings.STUB_USER_DB and (
                password == settings.STUB_USER_DB.get(username, None)):
            user = User(username)
            login_user(user)
            return redirect(request.args.get("next"))
        else:
            flash('Login failed; try again')
            return redirect(url_for('login_stub.login'))
    else:
        messages = get_flashed_messages()
        flashes = '<UL>\n%s\n</UL>' % '\n'.join([
            '<LI>%s</LI>' % escape(m) for m in messages]) if messages else ''
        return Response(flashes + '''
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

