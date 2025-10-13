"""
Expose the Flask app for production servers (gunicorn expects `server:app`).
Delegates to the actual application in py_simple.server.
"""
from py_simple.server import app  # noqa: F401
