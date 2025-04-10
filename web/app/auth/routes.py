from app.main import bp

import functools

import os
import logging
LOGGINGLEVEL = os.environ.get('LOGGINGLEVEL', 'WARNING')
logging.basicConfig(level=LOGGINGLEVEL, format=' %(asctime)s - %(levelname)s - %(message)s')

from flask import flash, redirect, render_template, redirect, request, session, url_for, g, current_app
from werkzeug.security import check_password_hash, generate_password_hash
from app.db import get_db
from app.forms import LoginForm, RegisterForm
from werkzeug.urls import url_parse

from flask_babel import _, lazy_gettext as _l


def admin_login_required(view):
    """View decorator that redirects anonymous users to the login page."""

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("main.login", next=request.path.replace('/','')))
        elif g.admin is not 'y':
            logging.info(g.admin)
            return render_template("errors/401.html")
        else:
            return view(**kwargs)

    return wrapped_view

@bp.route("/login", methods=("GET", "POST"))
def login():
    """Log in a registered user by adding the user id to the session."""
    if request.method == "POST":
        logging.info("Attempting to login")
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        error = None
        logging.info(f'Retrieving username {username} from the database')

        user = db.execute(
            "SELECT * FROM user WHERE username = ?", (username,)
        ).fetchone()

        if user is None:
            logging.info("Failed to find username")
            error = "Incorrect username."
        elif not check_password_hash(user["password"], password):
            logging.info("Incorrect password")
            error = "Incorrect password."

        if error is None:
            logging.info("Successfully retrieved username/password from database.")
            admin = db.execute("SELECT admin FROM user WHERE username = ?", (username,)).fetchone()[0]
            # store the user id in a new session and return to the index
            session.clear()
            logging.info(f'Adding session variables: user_id={user["id"]}, username={user["username"]}, admin={admin}')
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["admin"] = admin
            next_page = request.args.get('next')
            # logging.info("LOOK HERE")


            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for("main.index")
            return redirect(next_page)


        flash(error)

    # Login page (GET)
    form = LoginForm()
    return render_template("auth/form.html", form=form, title=_l('ER2 Login'))


@bp.before_app_request
def load_logged_in_user():
    """If a user id is stored in the session, load the user object from
    the database into ``g.user``."""

    user_id = session.get("user_id")
    logging.info(f'Loading user {user_id}')

    if user_id is None:
        logging.info(f'Setting global g.user to None')
        g.user = None
        g.admin = None
    else:
        g.user = (
            get_db().execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()[0]
        )
        g.admin = (
            get_db().execute("SELECT admin FROM user WHERE id = ?", (user_id,)).fetchone()[0]
        )
        logging.info(f'Fetching g.user from database.\ng.user={g.user}')


# @admin_login_required
@bp.route("/register", methods=("GET", "POST"))
def register():
    """Register a new user.
    Validates that the username is not already taken. Hashes the
    password for security.
    """
    if request.method == "POST":
        form = RegisterForm()
        error = None
        logging.info('Fetching database')
        db = get_db()

        if not form.validate_on_submit():
            logging.info('form not validated')
            try:
                error = form.errors['security_key'][0]
            except:
                error = "Error"
        username = request.form["username"]
        password = request.form["password"]
        admin = request.form.get("admin",None)


        if (
            db.execute("SELECT id FROM user WHERE username = ?", (username,)).fetchone()
            is not None
        ):
            error = "User {0} is already registered.".format(username)

        if error is None:
            # the name is available, store it in the database and go to
            # the login page
            logging.info(f'Registering {username} by adding to database')
            db.execute(
                "INSERT INTO user (username, password, admin) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), admin),
            )
            db.commit()

            return redirect(url_for('main.index'))

        flash(error)
    form = RegisterForm()
    return render_template("auth/form.html", form=form, title=_l('Register ER2 User'))




@bp.route("/logout")
def logout():
    """Clear the current session, including the stored user id."""
    logging.info('User logout. Clearing session.')
    session.clear()
    return redirect(url_for("main.index"))