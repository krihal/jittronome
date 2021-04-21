import os
import json

from flask_restx import Api, Namespace, Resource
from flask import Flask, request, render_template


register = Namespace('register', description='Register senders/receivers',
                     prefix='/')


class RegisterApi(Resource):
    def post(self):
        #
        # {
        #     "name": "TUG-5",
        #     "type": "sender",
        #     "ip-address": "1.2.3.4",
        #     "room": "123123123"
        # }
        #

        json_in = request.get_json()

        with open('registry.json', 'r') as fd:
            json_data = json.load(fd)

        if json_in['name'] not in json_data:
            json_data['name'] = {}

        json_data['name']['type'] = json_in['type']
        json_data['name']['ip-address'] = json_in['ip-address']
        json_data['name']['room'] = json_in['room']

        with open('registry.json', 'w') as fd:
            fd.write(json.dumps(json_data))


register.add_resource(RegisterApi, '')


app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(128)

api = Api(app)
api.add_namespace(register)


@app.route('/dashboard')
def index():
    with open('registry.json', 'r') as fd:
        json_data = json.load(fd)

    return render_template("registry.html", data=json_data)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=4422)
