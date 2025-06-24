from flask import Blueprint

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/market')

# Import routes to register them with the blueprint
from . import routes