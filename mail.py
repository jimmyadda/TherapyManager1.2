import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import hashlib
import hmac
import json
import sqlite3
from flask import redirect, request, session
import flask_login
from flask_mail import Mail, Message
import os
import smtplib
import logging

from package.database import DatabaseManager
SECRET_KEY = 'AvivimSecretKey'



def get_Mail_settings(Pclient_key):
    client_key = Pclient_key
    db_manager = DatabaseManager(client_key)
    conn = db_manager.connect_to_db(client_key)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()    
    return {row[0]: row[1] for row in rows}

def update_Mail_setting(key, value):
    client_key = session['client_key']
    db_manager = DatabaseManager(client_key)
    conn = db_manager.connect_to_db(client_key)
    cursor = conn.cursor()
    cursor.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
    conn.commit()

# Function to generate the signature
def generate_signature(pat_id, client_key):
    data = f"{pat_id}:{client_key}"
    return hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    
def generate_patient_portal_url(base_url, pat_id, client_key):
    signature = generate_signature(pat_id, client_key)
    return f"{base_url}?pat_id={pat_id}&client_key={client_key}&signature={signature}"

###globals
path = os.getcwd()
database_filename = "Tasker.db"
#Mail Settings
#with open('config.json') as config_file:


#DB functions
def database_write(sql,data=None):
    client_key = session['client_key']
    db_manager = DatabaseManager(client_key)
    conn = db_manager.connect_to_db(client_key)
    db = conn.cursor()

    row_affected = 0
    if data:
        row_affected = db.execute(sql, data).rowcount
    else:
        row_affected = db.execute(sql).rowcount
    conn.commit()
    db.close()
    conn.close()

    return row_affected

def database_read(sql,data=None):
    client_key = session['client_key']
    db_manager = DatabaseManager(client_key)
    conn = db_manager.connect_to_db(client_key)
    db = conn.cursor()

    if data:
         db.execute(sql, data)
    else:
         db.execute(sql)
    records = db.fetchall()    
    rows = [dict(record) for record in records]

    db.close()
    conn.close()
    return rows

def send_mail(notification='',PclineKey=None):
    form = session['formData']
    user = flask_login.current_user.get_dict() 
    
    mail_settings = get_Mail_settings(PclineKey)

    task_url = request.host_url + f"/main?folderid={form['folderid']}&id={form['id']}"
    assignTo_mail = database_read(f"select email from accounts WHERE name ='{form['assignto']}' order by name;")
    Project_data= database_read(f"select name from folders WHERE id ='{form['folderid']}' order by name;")
    #Create Main
    projname= Project_data[0]['name']
    subject="Task Number : [#" +form['id']+" ] -" +form['title']
    sender_email= str(mail_settings['MAIL_USERNAME'])
    receiver_email = str(assignTo_mail[0]['email'])
    #Build Msg
    # Email content
    email_body = '''
                <b>Subject:</b> {Subject}<br>
                <b>Reported By:</b> {Reported By}<br>
                <b>Assigned To:</b> {Assigned To}<br>
                <b>Project:</b> {Project}<br>
                <b>TaskID:</b> {TaskID}<br>
                <b>Category:</b> {Category}<br>
                <b>Priority:</b> {Priority}<br>
                <b>Status:</b> {Status}<br>
                <b>Date Created:</b> {Date Created}<br>
                <br>
                <b>Description:</b><br>
                {Description}
                '''
        # Email data
    email_data = {
        'Subject': subject,    
        'Reported By': user['userid'],
        'Assigned To': form['assignto'],
        'Project': projname,
        'TaskID': form['id'],
        'Category': form['category'],
        'Priority': form['priority'],
        'Status': form['status'],
        'Date Created': form['created'],
        'Description': form['desc']
        }
    email_content = email_body.format(**email_data)
    email_content += f"<br><p><a href={task_url}>Go to Task</a></p>"
    # Create MIME message
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email    
    message['Subject'] = str(subject)
    message.attach(MIMEText(email_content, 'html',_charset='utf-8'))

    # Connect to the SMTP server and send the email
    with smtplib.SMTP(mail_settings['MAIL_SERVER'], 587) as server:
        server.starttls()
        server.login(mail_settings['MAIL_USERNAME'], mail_settings['MAIL_PASSWORD'])
        server.sendmail(sender_email, receiver_email, message.as_string().encode("UTF-8"))
        server.close()
    print('Email sent!')
    #Log
    return redirect(f"/main?folderid={form['folderid']}&id={form['id']}")

def send_notification(data):
    form = data
    notification = "Wellcome to our clinic" 
    client_key = session['client_key']
    mail_settings = get_Mail_settings(client_key)
    print(mail_settings)
    subject="Notification Mail"
    assignTo_mail = form['pat_email']
    #url
    base_url = request.host_url + "/portal"
    pat_id = form['pat_id']
    client_key = form['client_key']
    patient_url = generate_patient_portal_url(base_url, pat_id, client_key)


    sender_email= str(mail_settings['MAIL_USERNAME'])
    receiver_email = str(assignTo_mail) 
    email_body = '''
                <b>Subject:</b> {Subject}<br>                              
                <br>
                <b>Note:</b><br>
                {note}
                ''' 
    # Email data
    email_data = {
            'Subject': subject,    
            'note': notification
            } 
    email_content = email_body.format(**email_data)
    email_content += f"<br><p><a href={patient_url}>Go to patient page</a></p>"
    # Create MIME message
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email    
    message['Subject'] = str(subject)
    message.attach(MIMEText(email_content, 'html',_charset='utf-8'))

    # Connect to the SMTP server and send the email
    with smtplib.SMTP(mail_settings['MAIL_SERVER'], 587) as server:
        server.starttls()
        server.login(mail_settings['MAIL_USERNAME'], mail_settings['MAIL_PASSWORD'])
        server.sendmail(sender_email, receiver_email, message.as_string().encode("UTF-8"))
        server.close()
    print('Email sent!')
    return "ok"