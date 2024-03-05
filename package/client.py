from flask_restful import Resource, Api, request
from package.model import conn



class ClientUser(Resource):
    def __init__(self,pat_id,email,name):
        self.email = email
        self.name = name
        self.id = pat_id

        
    def get_client_user_dict(self):
        return{'pat_id': self.id,'email': self.email, 'name': self.name}