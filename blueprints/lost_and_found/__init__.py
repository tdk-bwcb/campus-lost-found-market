from flask import Blueprint

lost_and_found_bp = Blueprint('lost_and_found', __name__, url_prefix='/lost')

# Import routes to register them with the blueprint
from . import routes