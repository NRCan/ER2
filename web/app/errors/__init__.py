from flask import Blueprint

# Creation of errors blueprint
bp = Blueprint('errors', __name__)

# To register the error handlers with the errors blueprint
# Import at bottom to avoid circular dependencies 
from app.errors import handlers