from flask import Flask, render_template
#from config import config
#print (help('modules main'))
#def create_app(config_name):
def create_app():
    #app = Flask(__name__)
    #app.config.from_object(config[config_name])
    #config[config_name].init_app(app)
    # ...
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'P@nd@1989'
    from .main import main as bp
    app.register_blueprint(bp)
    return app
