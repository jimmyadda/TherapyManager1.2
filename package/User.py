from flask import Flask, send_file,flash,render_template,request,redirect, send_from_directory, session
import flask_login


class User(flask_login.UserMixin):
    def __init__(self,userid,email,name):
        self.email = email
        self.name = name
        self.id = userid
    def get_dict(self):
        return{'userid': self.id,'email': self.email, 'name': self.name}
    

    