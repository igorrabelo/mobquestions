from flask import request, jsonify, g

from functools import wraps
from datetime import datetime, timedelta

import json

import jwt
from jwt.exceptions import DecodeError, ExpiredSignature


token_timeout = 5 # time in minutes
jwt_algorithm = 'HS256'
SECRET_KEY = 'super-secret'

def jwt_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if not request.headers.get('Authorization'):
			return jsonify(message='Missing authorization header'), 401
		try:
			payload = parse_token(request)
			if payload['refresh']:
				return jsonify('Token is not an access token.'), 401
			g.token = request.headers.get('Authorization').split()[1]
			g.parsed_token = payload
		except DecodeError:
			return jsonify(message='Token is invalid'), 401
		except ExpiredSignature:
			return jsonify(message='Token has expired'), 401
		return f(*args, **kwargs)
	return decorated_function


def jwt_refresh_required(f):
	@wraps(f)
	def decorated_function(*args, **kwargs):
		if not request.headers.get('Authorization'):
			return jsonify(message='Missing authorization header'), 401
		try:
			payload = parse_token(request)
			if not payload['refresh']:
				return jsonify('Token is not a refresh token.'), 401
			g.token = request.headers.get('Authorization').split()[1]
			g.parsed_token = payload
		except DecodeError:
			return jsonify(message='Token is invalid'), 401
		except ExpiredSignature:
			return jsonify(message='Token has expired'), 401
		return f(*args, **kwargs)
	return decorated_function



def create_access_token(user):
	payload = {
		'username': user['username'],
		'refresh': False,
		# issued at
		'iat': datetime.utcnow(),
		# expiry
		'exp': datetime.utcnow() + timedelta(minutes=token_timeout)
	}
	token = jwt.encode(payload, SECRET_KEY, algorithm=jwt_algorithm)
	return token.decode('unicode_escape')


def create_refresh_token(user):
	payload = {
		'username': user['username'],
		'refresh': True,
		# issued at
		'iat': datetime.utcnow(),
	}
	token = jwt.encode(payload, SECRET_KEY, algorithm=jwt_algorithm)
	return token.decode('unicode_escape')
	

def parse_token(req):
	token = req.headers.get('Authorization').split()[1]
	return jwt.decode(token, SECRET_KEY, algorithms=jwt_algorithm)
