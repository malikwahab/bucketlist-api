import os, sys, inspect

currentdir = os.path.dirname(os.path.abspath(inspect.
    getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)

from werkzeug.http import parse_authorization_header
from flask import Flask, jsonify, request, abort, make_response
from flask_restful import Api, Resource, reqparse, fields, marshal
from flask_httpauth import HTTPBasicAuth
from bucketlist_api.models import User, BucketList, BucketListItem, get_db
from datetime import datetime

app = Flask(__name__, static_url_path='')
api = Api(app)
auth = HTTPBasicAuth()


@auth.verify_password
def authenticate_token(token, password):
    if User.verify_token(token):
        return True
    return False


class CreateUserAPI(Resource):
    """Register User to the app.

    """

    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('username', type=str, required=True)
        self.parser.add_argument('password', type=str, required=True)
        super(CreateUserAPI, self).__init__()

    def post(self):
        data = self.parser.parse_args()
        new_user = User(username=data['username'])
        new_user.hash_password(data['password'])
        db = get_db()
        if User.user_exist(new_user.username):
            abort(400)
        db.session.add(new_user)
        db.session.commit()
        token = new_user.generate_auth_token()
        response = jsonify({'token': token.decode('ascii')})
        response.status_code = 201
        return response




class LoginUserAPI(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()
        self.parser.add_argument('username', type=str, required=True,
                                    location='json')
        self.parser.add_argument('password', type=str, required=True,
                                    location='json')
        super(LoginUserAPI, self).__init__()


    def post(self):
        data = self.parser.parse_args()
        user = User.get_user(data['username'], data['password'])
        if not user:
            abort(401)
        token = user.generate_auth_token()
        return jsonify({'token': token.decode('ascii')})



class BucketListAPI(Resource):
    decorators = [auth.login_required]

    def __init__(self):
        self.parser = self.parser = reqparse.RequestParser()
        self.parser.add_argument('name', type=str, required=True,
                                  location='json')
        self.parser.add_argument('is_public', type=bool, location='json')
        self.parser.add_argument('Authorization', location='headers')
        self.db = get_db()


    def post(self):
        data = self.parser.parse_args()
        bucketlist = BucketList(name=data['name'], is_public=False)
        bucketlist.date_created = datetime.now()
        bucketlist.date_modified = datetime.now()
        if data.get('is_public'):
            bucketlist.is_public = data['is_public']
        auth_data = request.authorization
        user = User.get_user_with_token(auth_data)
        bucketlist.user_id = user.id
        self.db.session.add(bucketlist)
        self.db.session.commit()
        #response = jsonify({'bucketlist': url_for('apiendpoint', bucketlist_id, _external)})
        response = jsonify({'bucketlist':bucketlist.id})
        response.status_code = 201
        return response

    def get(self, id=None):
        auth_data = request.authorization
        limit = None
        page = None
        if 'limit' in request.args:
            limit = request.args['limit']
            if 'page' in request.args:
                page = request.args['page']
        user = User.get_user_with_token(auth_data)
        if id:
            bucketlist = BucketList.get_bucketlist(id=id, user_id=user.id)
        elif request.args.get('q'):
            q = request.args['q']
            bucketlist = BucketList.get_bucketlist(user_id=user.id, q=q)
        else:
            bucketlist = BucketList.get_bucketlist(user_id=user.id, limit=limit, page=page)
        if len(bucketlist) < 1:
            abort(404)
        return jsonify({'bucketlist': bucketlist})

    def put(self, id):
        auth_data = request.authorization
        data = self.parser.parse_args()
        user = User.get_user_with_token(auth_data)
        bucketlist = (BucketList.query.filter_by(id=id, user_id=user.id)
                                      .first())
        if bucketlist is None:
            abort(404)
        if data['name']:
            bucketlist.name = data['name']
        bucketlist.date_modified = datetime.now()
        self.db.session.add(bucketlist)
        self.db.session.commit()
        response = jsonify({'bucketlist':bucketlist.id})
        response.status_code = 201
        return response

    def delete(self, id):
        auth_data = request.authorization
        data = self.parser.parse_args()
        user = User.get_user_with_token(auth_data)
        bucketlist = (BucketList.query.filter_by(id=id, user_id=user.id)
                                      .delete())
        if not bucketlist:
            abort(404)
        items = (BucketListItem.query.filter_by(bucketlist_id = id).delete())
        self.db.session.commit()
        response = jsonify({'bucketlist':bucketlist})
        response.status_code = 201
        return response



class ItemListAPI(Resource):
    decorators = [auth.login_required]

    def __init__(self):
        self.parser = self.parser = reqparse.RequestParser()
        self.parser.add_argument('name', type=str, location='json')
        self.parser.add_argument('done', type=int, location='json')
        self.db = get_db()

    def post(self, id):
        data = self.parser.parse_args()
        auth_data = request.authorization
        if not User.bucketlist_own_by_user(auth_data, id):
            abort(401)
        item = BucketListItem(name=data['name'], bucketlist_id=id)
        item.date_created = datetime.now()
        item.date_modified = datetime.now()
        self.db.session.add(item)
        BucketList.update_bucketlist(id)
        self.db.session.commit()
        response = jsonify({'item':item.id})
        response.status_code = 201
        return response

    def put(self, id, item_id):
        auth_data = request.authorization
        data = self.parser.parse_args()
        if not User.bucketlist_own_by_user(auth_data, id):
            abort(401)
        item = (BucketListItem.query.filter_by(id=item_id, bucketlist_id=id)
                                   .first())
        if not item:
            abort(404)
        if data['name']:
            item.name = data['name']
        if data['done']:
            item.done = data['done']
        item.date_modified = datetime.now()
        self.db.session.add(item)
        BucketList.update_bucketlist(id)
        self.db.session.commit()
        response = jsonify({'item':item.id})
        response.status_code = 200
        return response

    def delete(self, id, item_id):
        auth_data = request.authorization
        if not User.bucketlist_own_by_user(auth_data, id):
            abort(401)
        item = BucketListItem.query.filter_by(id=item_id,
                                           bucketlist_id=item_id).delete()
        if not item:
            abort(404)
        BucketList.update_bucketlist(id)
        self.db.commit()
        response = jsonify({'item': item})
        response.status_code = 200
        return response






#build api end point to handle 405 that returns json
api.add_resource(CreateUserAPI, '/auth/register', endpoint='register')
api.add_resource(LoginUserAPI, '/auth/login', endpoint='login')
api.add_resource(BucketListAPI, '/bucketlists', endpoint='bucketlists')
api.add_resource(BucketListAPI, '/bucketlists/<int:id>', endpoint='bucktelist')
api.add_resource(ItemListAPI, '/bucketlists/<int:id>/items',
                 endpoint='items')
api.add_resource(ItemListAPI, '/bucketlists/<int:id>/items/<int:item_id>',
                 endpoint='item')

if __name__ == '__main__':
    app.run(debug=True)
