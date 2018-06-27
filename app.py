from flask import Flask, request, jsonify, redirect, g
from flask_pymongo import PyMongo 
from pymongo import ReturnDocument

from werkzeug.security import generate_password_hash, check_password_hash

from bson import json_util

from config import MONGO_URI, MONGO_URI_TESTS, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD
from auth import *

import os
import redis

rcache = redis.Redis(
            host=REDIS_HOST, 
            port=REDIS_PORT,
            password=REDIS_PASSWORD)

def create_app(testing = False):
    app = Flask(__name__)
    if os.getenv('FLASK_TESTING') and os.getenv('FLASK_TESTING')==1:
        app.config['MONGO_URI'] = MONGO_URI_TESTS
    else:
        app.config['MONGO_URI'] = MONGO_URI
    app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = False
    app_context = app.app_context()
    app_context.push()        
    return app

app = Flask(__name__)
app.config['MONGO_URI'] = MONGO_URI
app.config['DEBUG'] = True

app_context = app.app_context()
app_context.push()

mongo = PyMongo(app)

col_users = mongo.db.users
col_questions = mongo.db.questions
col_tokens = mongo.db.tokens        # refresh tokens

def authenticate(username, password):
    user = col_users.find_one({'username': username})
    if user and check_password_hash(user['password'], password):
        return user
    else:
        return None

@app.route('/signin', methods=['POST'])
def signin():
    data = request.get_json()
    user = authenticate(data['username'], data['password'])
    if user:
        token_payload = {'username': user['username']}
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)
        col_tokens.insert_one({'value': refresh_token})
        return jsonify({'access_token': access_token, 
                        'refresh_token': refresh_token}), 200
    else:
        return "Unauthorized", 403

@app.route('/', methods=['GET'])
@jwt_required
def index():
    res = col_users.find({})
    return json_util.dumps(list(res)), 200

@app.route('/cached_example', methods=['GET'])
def questao_mais_legal_cacheada():    
    if rcache and rcache.get('questao_legal'):
        return rcache.get('questao_legal'), 200
    else:
        question = col_questions.find({'id': 'c14ca8e5-b7'})
        if rcache:
            rcache.set('questao_legal', json_util.dumps(question))
    return json_util.dumps(question), 200

@app.route('/not_cached_example', methods=['GET'])
def questao_mais_legal():    
    question = col_questions.find({'id': 'bc3b3701-b7'})
    return json_util.dumps(question), 200

@app.route('/refresh_token', methods=['GET'])
@jwt_refresh_required
def refresh_token():    
    token = col_tokens.find_one({'value': g.token})
    if token:
        col_tokens.delete_one({'value': g.token})
        token_payload = {'username': g.parsed_token['username']}
        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)
        col_tokens.insert_one({'value': refresh_token})
        return json_util.dumps({'access_token': access_token, 
                                'refresh_token': refresh_token}), 200
    else:
        return "Unauthorized", 401


# rota para visualizar o conteudo do payload encriptado no token.
@app.route('/token', methods=['GET'])
@jwt_required
def token():    
    return json_util.dumps(g.parsed_token), 200


@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    data['password'] = generate_password_hash(data['password'])
    
    user = col_users.find_one({'username': data['username']})
    
    if not user:
        col_users.insert_one(data)
        return 'usuario ' + data['username'] + ' criado.', 201
    else:
        return 'usuario existente', 203

@app.route('/users/<username>', methods=['GET'])
def get_user(username):
    user = col_users.find_one({'username': username})
    if not user:
        return 'usuario nao existe', 404
    else:
        return json_util.dumps(user), 200

@app.route('/users/<username>', methods=['PUT'])
def put_user(username):
    data = request.get_json()    

    result  = col_users.find_one_and_update({'username': username},
    {'$set': {"name": data['name'], "phones": data['phones'], "email": data['email']}})

    if not result:
        return 'nao foi possivel atualizar', 404
    else:
        return json_util.dumps(result), 200


@app.route('/authenticate1', methods=['POST'])
def authenticate1():
    data = request.get_json()    
    user = col_users.find_one({'username': data['username']})
    
    if not data['username'] or not data['password']:
        return 'informacao de usuario e senha obrigatoria.', 400
    else:   
        if user and check_password_hash(user['password'], data['password']):
            return 'usuario ' + data['username'] + ' autenticado.', 200
        else:
            return 'usuario ' + data['username'] + ' invalido.', 403

@app.route('/users/<username>', methods=['PATCH'])
def patch_user(username):
    data = request.get_json()    

    result  = col_users.find_one_and_update({'username': username},
    {'$set': {"password": data['password']}})

    if not result:
        return 'nao foi possivel atualizar', 404
    else:
        return json_util.dumps(result), 200

@app.route('/questions/<question_id>', methods=['GET'])
def get_question(question_id):
        
    question = col_questions.find_one({'id': question_id})

    if not question:
        return 'nao foi possivel carregar questao', 404
    else:
        return json_util.dumps(question), 200

@app.route('/comment', methods=['POST'])
def post_comment():
    data = request.get_json()    

    question = col_questions.find_one({'id': data['question_id']})
    
    if not question:
        return 'nao foi possivel encontrar a questao', 404
    else:        
        user = col_users.find_one({'username': data['username']})
        if not user:
            return 'usuario nao existe', 400
        else:
            #import pdb; pdb.set_trace()            
            del(data['question_id'])
            if 'comments' in question.keys():
                question['comments'].append(data)                
            else:
                question['comments'] = [data]
             
            result = col_questions.find_one_and_update({'id': question['id']},
            {'$set': {"comments": question['comments']}},
            return_document=ReturnDocument.AFTER)
            
            return json_util.dumps(result), 200


                
# rota para exemplificar como utilizar obter variaveis
# de url. teste acessando 
# http://localhost:8088/questions/search?disciplina=1 
@app.route('/questions/search', methods=['GET'])
def search():
    disciplina = request.args.get('disciplina')
    return disciplina, 200
