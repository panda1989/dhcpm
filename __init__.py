from flask import Flask, render_template
def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'P@nd@1989'
    from .main import main as bp
    app.register_blueprint(bp)
    return app
