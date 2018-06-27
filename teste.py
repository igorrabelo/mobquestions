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


    def setUp(self):
        client = MongoClient(MONGO_URI_TESTS)
        db = MONGO_URI_TESTS.split('/')[-1]        
        self.col_users = client[db].users
        self.col_questions = client[db].questions
        self.col_tokens = client[db].tokens  # para os refresh tokens

        test_user = {'username': 'foo', 'name': 'Foo', 'password': generate_password_hash('123'), 'email':'foo@gmail.com'}        
        self.col_users.insert_one(test_user)

        # insert questions
        with open('data.json') as f:
            content = f.readlines()
            
        content = [x.strip() for x in content] 
        for line in content:
            obj = json_util.dumps(line)            
            self.col_questions.insert_one(json_util.loads(line))

        


    def test_create_user(self):
        data = {'username': 'mark', 'name': 'Mark', 'password': '123', 'email':'mark@gmail.com'}
        response = self.client.post('/users', 
                                    data=json_util.dumps(data), 
                                    content_type='application/json')
        self.assertEquals(response.status_code, 201)


    def test_signin(self):
        data = {'username': 'foo', 'password': '123'}
        response = self.client.post('/signin', 
                                    data=json.dumps(data), 
                                    content_type='application/json')
        response_data = json_util.dumps(response.data)
        self.token = response_data['access_token']
        self.assertEquals(response.status_code, 200)


    def test_create_user_no_username(self):
        data = {'name': 'Mark', 'password': '123', 'email':'mark@gmail.com'}
        response = self.client.post('/users', 
                                    data=json_util.dumps(data), 
                                    content_type='application/json')
        self.assertEquals(response.status_code, 400)


    def test_get_user(self):
        response = self.client.get('/users/mark')
        self.assertEquals(response.status_code, 200)


    def test_get_user_not_found(self):
        response = self.client.get('/users/klaus')
        self.assertEquals(response.status_code, 404)


    def tearDown(self):
        # apagar todos documentos
        self.col_users.delete_many({})
        self.col_questions.delete_many({})
        self.col_tokens.delete_many({})


if __name__ == '__main__':
    unittest.main()
