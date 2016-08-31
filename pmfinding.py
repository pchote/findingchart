from flask import Flask
from flask import render_template
from flask import request

app = Flask(__name__)

@app.route('/')
def input_display():
    return render_template('input.html')

@app.route('/generate')
def generate_chart():
    print(request.args.get('coordinates', ''))
    return 'hi'
