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

def create_app():
    app = Flask(__name__)
    #import pdb; pdb.set_trace()
    if os.getenv('FLASK_TESTING') and os.getenv('FLASK_TESTING')=='1':
        app.config['MONGO_URI'] = MONGO_URI_TESTS
    else:
        app.config['MONGO_URI'] = MONGO_URI
    app.config['PRESERVE_CONTEXT_ON_EXCEPTION'] = False
    app_context = app.app_context()
    app_context.push()        
    return app

#app = Flask(__name__)
#app.config['MONGO_URI'] = MONGO_URI
#app.config['DEBUG'] = True
#app_context = app.app_context()
#app_context.push()

app = create_app()
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
    
    if 'password' not in data.keys() or 'username' not in data.keys():
        return 'Dados insuficientes.', 400
    
    data['password'] = generate_password_hash(data['password'])
    
    user = col_users.find_one({'username': data['username']})
    #import pdb; pdb.set_trace()
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

@app.route('/questions/search', methods=['GET'])
def search():
    args = request.args.to_dict()
    if 'disciplina' in args:
        args['disciplina'] = int_try_parse(args['disciplina'])
    if 'ano' in args:
        args['ano'] = int_try_parse(args['ano'])

    questions = col_questions.find(args)
    return json_util.dumps(list(questions)), 200

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

@app.route('/v1/questions/answer', methods=['POST'])
@jwt_required
def insert_answer():
    jwt = g.parsed_token
    data = request.get_json()
    userAnswer = data['answer'].upper()
    question_id = data['id']
    answer = col_answers.find_one({'id': question_id, 'username': jwt['username']})

    if answer is None:
        question = col_questions.find_one({'id': question_id}, {'_id': 0, 'resposta': 1})
        answer_is_correct = True if userAnswer == question['resposta'] else False
        
        answer = {
            'id': question_id,
            'username': jwt['username'],
            'answer': userAnswer,
            'answer_is_correct': answer_is_correct
        }
        
        col_answers.insert_one(answer)
        col_questions.update_one({'id': question_id}, {'$inc': {'answersNumber': 1}})

        if answer_is_correct:
            return 'Resposta Correta', 200
        else:
            return 'Resposta Incorreta', 200
    else:
        return 'Resposta já registrada', 409

@app.route('/questions/resposta', methods=['GET'])
@jwt_required
def get_answer():
    jwt = g.parsed_token
    answers = list(col_answers.find({'username': jwt['username']}, {'_id': 0, 'id': 1, 'answer': 1}))
    
    if len(answers) > 0:
        return json_util.dumps(answers), 200
    else:
        return 'Nao Encontrado', 404


@app.route('/destaque_questions', methods=['POST'])
def set_featured_questions():
    featured_questions = col_questions.find({}).sort([('answersNumber', DESCENDING)]).limit(10)
    rcache.set('featured_questions', json_util.dumps(list(featured_questions)))
    return 'Atualizacao de Cache', 200


@app.route('/destaque_questions', methods=['GET'])
def get_featured_questions():
    featured_questions = rcache.get('featured_questions')
    if featured_questions is not None:
        return featured_questions, 200
    else:
        featured_questions = list(col_questions.find({}).sort([('answersNumber', DESCENDING)]).limit(10))
        rcache.set('featured_questions', json_util.dumps(featured_questions))
        return json_util.dumps(featured_questions), 200
                
