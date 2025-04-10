from flask import Flask, request, session, current_app
from flask_bootstrap import Bootstrap
from flask_babel import Babel, lazy_gettext as _l
from config import Config
import os 

bootstrap = Bootstrap()
babel = Babel()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    bootstrap.init_app(app)
    babel.init_app(app)
    app.config["BOOTSTRAP_SERVE_LOCAL"] = True
    app.config["DATABASE"] = 'er2.sqlite'

    from . import db
    db.init_app(app)

    # Register the errors blueprint with the application
    from app.errors import bp as errors_bp
    app.register_blueprint(errors_bp)

    from app.auth import bp as auth_bp
    # app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(auth_bp)

    # Register the main blueprint with the application
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app


@babel.localeselector
def get_locale():
    try:
        return session["language"]
    except KeyError:
        session["language"] = request.accept_languages.best_match(
            current_app.config["LANGUAGES"]
        )
        return session["language"] 