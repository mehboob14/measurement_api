
from flask import Flask

def create_app():
    app = Flask(__name__)
    from .routes import main as main_blueprint
    from .llm_utils import llm_bp as llm_blueprint
    app.register_blueprint(llm_blueprint)
    app.register_blueprint(main_blueprint)

    return app