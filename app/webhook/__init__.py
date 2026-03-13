from flask import Blueprint

bp = Blueprint('webhook', __name__)

from app.webhook import routes