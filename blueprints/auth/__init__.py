from flask import Blueprint

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Import routes to register them with the blueprint
from . import routes