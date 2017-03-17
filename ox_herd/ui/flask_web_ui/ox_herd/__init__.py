"""Flask Blueprnit for ox_herd.
"""

from flask import Blueprint

OX_HERD_BP = Blueprint('ox_herd', __name__, template_folder='templates',
                       static_folder='static', url_prefix='/ox_herd')

