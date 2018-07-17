import json
from bson import json_util
from flask_testing import TestCase
from werkzeug.security import generate_password_hash
from pymongo import MongoClient
from app import app
from config import MONGO_URI_TESTS


class MainTestCase(TestCase):

    TESTING = True

    def create_app(self):
        app.config['MONGO_URI'] = MONGO_URI_TESTS
        return app
    
    def get_token(self, user, password):
        data = {'username': user, 'password': password}
        
        response = self.client.post('/signin', 
                                    data=json.dumps(data), 
                                    content_type='application/json')
                                    
        return response

    def config_database(self):
        client = MongoClient(MONGO_URI_TESTS)
        db = MONGO_URI_TESTS.split('/')[-1]        
        self.col_users = client[db].users
        self.col_questions = client[db].questions
        self.col_tokens = client[db].tokens  # para os refresh tokens
        self.col_answers = client[db].answers


    def database_cleanup(self):
        self.col_users.delete_many({})
        self.col_questions.delete_many({})
        self.col_tokens.delete_many({})
        self.col_answers.delete_many({})

    
    def user_populate(self):
        test_user = {'username': 'foo', 'name': 'Foo', 'password': generate_password_hash('123'), 'email':'foo@gmail.com'}        
        self.col_users.insert_one(test_user)
    

    def token_populate(self):
        # Preenche o token de acesso para evitar a dependência entre os testes
        token_response = self.get_token('foo', '123')
        self.token = json.loads(token_response.data)['access_token']

    
    def questions_populate(self):
        # insert questions
        with open('data.json') as f:
            content = f.readlines()
            
        content = [x.strip() for x in content] 
        for line in content:
            self.col_questions.insert_one(json_util.loads(line))
    

    def answers_populate(self):
        answer = { "username" : "foo", "answer" : "C",
                   "answer_is_correct" : True, "id" : "c14ca8e5-b7"}
        self.col_answers.insert_one(answer)


    def setUp(self):
        self.config_database()
        self.database_cleanup()
        self.user_populate()
        self.token_populate()
        self.questions_populate()
        self.answers_populate()


    def test_signin(self):
        response = self.get_token('foo', '123')

        self.assertEquals(response.status_code, 200)


    """ User tests """
    
    def test_create_user(self):
        data = {'username': 'mark', 'name': 'Mark', 'password': '123', 'email':'mark@gmail.com'}

        self.col_users.delete_many({})

        response = self.client.post('/v1/users', 
                                    data=json_util.dumps(data), 
                                    content_type='application/json')

        self.assertEquals(response.status_code, 201)


    def test_create_repeated_user(self):
        data = {'username': 'foo', 'name': 'Foo', 'password': '123', 'email':'foo@gmail.com'}

        response = self.client.post('/v1/users', 
                                    data=json_util.dumps(data), 
                                    content_type='application/json')
        
        self.assertEquals(response.status_code, 409)

    
    def test_create_user_no_username(self):
        data = {'name': 'Mark', 'password': '123', 'email':'mark@gmail.com'}
        
        response = self.client.post('/v1/users', 
                                    data=json_util.dumps(data), 
                                    content_type='application/json')
        
        self.assertEquals(response.status_code, 400)


    def test_get_user(self):
        response = self.client.get('/v1/users/foo')
        
        self.assertEquals(response.status_code, 200)


    def test_get_user_not_found(self):
        response = self.client.get('/v1/users/klaus')
        
        self.assertEquals(response.status_code, 404)


    """ Answer tests"""

    def test_answer_question(self):
        data = {'id': 'bc3b3701-b7', 'answer': 'C'}

        response = self.client.post('/v1/questions/answer',
                                    headers={'Authorization': 'JWT ' + self.token},
                                    data=json_util.dumps(data), 
                                    content_type='application/json')

        self.assertEquals(response.status_code, 200)


    def test_correct_answer_question(self):
        data = {'id': 'bc3b3701-b7', 'answer': 'C'}

        response = self.client.post('/v1/questions/answer',
                                    headers={'Authorization': 'JWT ' + self.token},
                                    data=json_util.dumps(data), 
                                    content_type='application/json')

        self.assertEquals(response.data, b'Resposta Correta')
        self.assertEquals(response.status_code, 200)


    def test_wrong_answer_question(self):
        data = {'id': 'bc3b3701-b7', 'answer': 'E'}

        response = self.client.post('/v1/questions/answer',
                                    headers={'Authorization': 'JWT ' + self.token},
                                    data=json_util.dumps(data), 
                                    content_type='application/json')

        self.assertEquals(response.data, b'Resposta Incorreta')
        self.assertEquals(response.status_code, 200)

    
    def test_find_answers(self):
        response_data = [{'answer': 'C', 'id': 'c14ca8e5-b7'}]

        response = self.client.get('/v1/questions/answer',
                                    headers={'Authorization': 'JWT ' + self.token},
                                    content_type='application/json')
        
        self.assertEquals(json.loads(response.data), response_data)
        self.assertEquals(response.status_code, 200)


    def tearDown(self):
        # apagar todos documentos
        self.database_cleanup()
