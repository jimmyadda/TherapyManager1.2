from functools import wraps
import json
import sqlite3
import flask_login

#Settings
with open('config.json') as config_file:
    config_data = json.load(config_file)
Globalsetting = config_data['Global'] 
  
mail_settings = config_data['mail_settings']

database_filename = str(Globalsetting['database']) #"TherapyManager.db"

def database_write(sql,data=None):
    connection = sqlite3.connect(database_filename)
    connection.row_factory = sqlite3.Row
    db = connection.cursor()
    row_affected = 0
    if data:
        row_affected = db.execute(sql, data).rowcount
    else:
        row_affected = db.execute(sql).rowcount
    connection.commit()
    db.close()
    connection.close()

    return row_affected

def database_read(sql,data=None):
    connection = sqlite3.connect(database_filename)
    connection.row_factory = sqlite3.Row
    db = connection.cursor()

    if data:
         db.execute(sql, data)
    else:
         db.execute(sql)
    records = db.fetchall()    
    rows = [dict(record) for record in records]

    db.close()
    connection.close()
    return rows


def admin_only(func):    
    @wraps(func)
    def decorated_function(*args, **kws):
            admin_users = database_read("select * from accounts")
            user = flask_login.current_user.get_dict()
            is_admin= False
            
            if 'userid' in user:
                if any(tag['userid'] == user['userid'] for tag in admin_users):
                    print("in admin user")
                    is_admin= True

            if 'pat_id' in user:
                if any(tag['userid'] == user['pat_id'] for tag in admin_users):
                    print("in admin clientuser")
                    is_admin = True

            if is_admin:
                return func(*args, **kws)
            else:
                return 'This Page is For Admin only', 403

    return decorated_function