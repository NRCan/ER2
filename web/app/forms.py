from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, BooleanField
from wtforms.validators import DataRequired, ValidationError
from flask import current_app
from flask_babel import _, lazy_gettext as _l

class LoginForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    submit = SubmitField(_l('Login'))

def security_key_check(form, field):
    if field.data != os.environ.get('REGISTER_SECURITY_KEY'):
        raise ValidationError(_l('Incorrect security key!'))


class RegisterForm(FlaskForm):
    username = StringField(_l('Username'), validators=[DataRequired()])
    admin = BooleanField(_l('Admin'))
    password = PasswordField(_l('Password'), validators=[DataRequired()])
    security_key = PasswordField(_l('Security Key'), validators=[DataRequired(), security_key_check])
    submit = SubmitField('Register')