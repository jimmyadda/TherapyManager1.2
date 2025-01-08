import base64
from collections import defaultdict
from email import encoders
from email.mime.base import MIMEBase
import hmac
import pathlib
from pydoc import text
from bs4 import BeautifulSoup
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from flask import Flask, abort, current_app, g, jsonify, send_file,flash,render_template,request,redirect, send_from_directory, session, url_for
import flask_login
import sqlite3
import datetime
import uuid
import hashlib
from werkzeug.utils import secure_filename
from flask_restful import Resource, Api
from mail import get_Mail_settings, send_notification, update_Mail_setting
from package.decorators import admin_only
from package.patient import Patients, Patient
from package.doctor import Doctors, Doctor
from package.appointment import Appointments, Appointment,RequestAppointments,RequestAppointment
from package.common import Common
from package.User import User
from package.client import ClientUser
from package.medicalnote import Medicalnote,Medicalnotes
from flask_mail import Mail, Message
from create_account import create_account
from package.database import DatabaseManager
from package.Myutils import render_ics
import json


app = Flask(__name__)

api = Api(app)
# Routes API
api.add_resource(Patients, '/patientapi')
api.add_resource(Patient, '/patientapi/<int:id>')
api.add_resource(Doctors, '/doctorapi')
api.add_resource(Doctor, '/doctorapi/<int:id>')
api.add_resource(Appointments, '/appointmentapi')
api.add_resource(Appointment, '/appointmentapi/<int:id>')
api.add_resource(RequestAppointments, '/appointmentrequestapi')
api.add_resource(RequestAppointment, '/appointmentrequestapi/<int:id>')
api.add_resource(Medicalnotes, '/medicalnoteapi')
api.add_resource(Medicalnote, '/medicalnoteapi/<int:id>')
api.add_resource(Common, '/common') 


with open('Translate.json',encoding="utf8") as Translate_file:
    Translate_data = json.load(Translate_file)

#Settings
with open('config.json') as config_file:
    config_data = json.load(config_file)
Globalsetting = config_data['Global'] 
  
#mail_settings = config_data['mail_settings'] old version


# Initialize DatabaseManager
db_manager = DatabaseManager()
# Ensure the default database is created at startup
db_manager.create_default_database()

SECRET_KEY = 'AvivimSecretKey'
app.config['SECRET_KEY'] = SECRET_KEY
path = os.getcwd()

UPLOAD_FOLDER = os.path.join(path, 'uploads')
if not os.path.isdir(UPLOAD_FOLDER):
    os.mkdir(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


#Logs
handler = logging.FileHandler('LogFile.log') # creates handler for the log file
app.logger.addHandler(handler) # Add it to the built-in logger
app.logger.setLevel(logging.DEBUG)         # Set the log level to debug
logger = app.logger
#Log in 
login_manager = flask_login.LoginManager()
login_manager.init_app(app)
#region Main App
base_db_path = "./databases/"

@login_manager.user_loader
def load_user(userid):  #or client patid
    user=None
    clientKey = session['client_key']
    users = database_read(f"select * from accounts where userid='{userid}';",client_key=clientKey)
    client = database_read(f"select * from patient where pat_id='{userid}';")
    print(users,userid)

    if len(users)==1:        
        user = User(users[0]['userid'],users[0]['email'],users[0]['name'],users[0]['client_key'])
    if len(client)==1:
        user = ClientUser(client[0]['pat_id'],client[0]['pat_email'],client[0]['pat_first_name'],client[0]['client_key'])
    if user:
        user.id = userid
        return user
    else:
        return None

def generate_client_key(user_id):
    # Use SHA-256 to generate a consistent hash
    return f"client_{hashlib.sha256(user_id.encode()).hexdigest()}" 
 
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
    #connection.commit()
    conn.commit()
    #db.close()
    #connection.close()

    return row_affected

def database_read(sql,data=None,client_key=None):
    if data:
        if "userid" in data:
            client_key = generate_client_key(data['userid'])
            session['client_key'] =  client_key
    if client_key :#'client_key' in session:
         Curr_ClientKey = client_key  #Curr_ClientKey = session['client_key']
    else:
        Curr_ClientKey = Globalsetting['DEFAULT_CLIENT_KEY']

    conn = db_manager.connect_to_db(client_key=Curr_ClientKey)  # Connect to the client's database
    print(Curr_ClientKey,conn)
    db = conn.cursor()   
    if data:
         db.execute(sql, data)
    else:
         db.execute(sql)
    records = db.fetchall()    
    rows = [dict(record) for record in records]

    #db.close()
    #connection.close()
    return rows

@app.teardown_appcontext
def close_db(exception=None):
    """
    Close the database connection at the end of each request.
    """
    db_manager.close_db_connection(exception)


#region index,login,register
@app.route("/")
def index_page():    
    default_user = db_manager.get_db_connection()
    default_user = db_manager.get_db_path()
    if 'default' in default_user:
        client_key = Globalsetting['DEFAULT_CLIENT_KEY']
    else:
        client_key = session['client_key']

    if flask_login.current_user.is_authenticated:
        print("is_authenticated")
        logger.info(str(flask_login.current_user.get_dict()) + " Has Logged in")   
        user = flask_login.current_user.get_dict()
        #dump sql con
        apps = Appointments()
        appointments= apps.get()   
        return render_template('/index.html',Translate_data=Translate_data,user=user,appointments=appointments)
    else:
        return redirect("/login")

@app.route("/register", methods=['GET'])
def registration_page():
    return render_template('register.html', alert="")

@app.route("/register", methods=['POST'])
def registration_request():
    form = dict(request.values)    
    folderid="0"
    if 'folderid' in request.values:
        folderid = request.values['folderid']
    id="1"
    if 'id' in request.values:
        id = request.values['id']
    reg_email = request.values['email']
    if reg_email:
        # Generate a unique client_key (e.g., UUID or hash)
        #client_key = f"client_{hash(form['userid'])}"
        client_key = generate_client_key(form['userid'])         
        form['client_key'] = client_key
        # Check if the client key/database already exists
        db_path = db_manager.get_db_path(client_key)
        if os.path.exists(db_path):
            return {"error": f"Client with key '{client_key}' already exists."}, 400
        # Create the client-specific database
        db_manager.create_client_database(client_key)  
        session['client_key'] =  client_key
        #create new connection
        checkconn= db_manager.connect_to_db(client_key)
        ok = create_account(form)
        session['formData'] = form
        print('ok:' ,ok)
        if ok == 1: 
            user = load_user(form['userid'])
            print("user",user)
            logger.info("New User Created: "+ user.name)                    
            logged = flask_login.login_user(user) 
            print("logged",logged)           
            return redirect('/') 
        else:
            return redirect(f"/error") 
    else:
         return render_template('/register.html',alert = "Please insert valid email to register!")

@app.route("/login", methods=['GET'])
def login_page():
    return render_template('login.html',alert ="")

@app.route("/login", methods=['POST'])
def login_request():    
    form = dict(request.values)
    client_key = generate_client_key(form['userid'])    
    form['client_key'] = client_key
        
    users = database_read("select * from accounts where userid=:userid",form,client_key=client_key)    
    formid = form['userid']
    if users :
        if len(users) == 1: #user name exist, password not checked
            salt = users[0]['salt']
            saved_key = users[0]['password']
            generated_key = hashlib.pbkdf2_hmac('sha256',form['password'].encode('utf-8'),salt.encode('utf-8'),10000).hex()

            if saved_key == generated_key: #password match
                user = load_user(formid)
                print("Login", user)
                logger.info(f"Login successfull - '{formid}'  date: {str(datetime.datetime.now())}")
                # Store client_key in the session
                session['client_key'] = user.client_key            
                flask_login.login_user(user)
                return redirect('/') 
            else: #password incorrect
                logger.info(f"Login Failed - '{formid}'  date: {str(datetime.datetime.now())}")
                return render_template('/login.html',alert = "Invalid user/password. please try again.") 
        else: #user name does not exist
            logger.info(f"Login Failed - '{formid}'  date: {str(datetime.datetime.now())}")
            return render_template('/login.html',alert = "Invalid user/password. please try again.")
    
@app.route("/logout")
@flask_login.login_required
def logout_page():
    session.pop('client_key', None)
    flask_login.logout_user()
    return redirect("/")

#endregion

#region General Route

@app.route("/error")
def error_page():
    return "there was an Error"

@app.route("/calendar")
@flask_login.login_required
def calendar_page():
    user = flask_login.current_user.get_dict()
    apps = Appointments()
    appointments = apps.get() 
    return render_template('calendar.html',user=user,appointments=appointments)

@app.route('/send-mail', methods=['GET',"POST"])
def send_appointment(notification=''):
    user = flask_login.current_user.get_dict()    
    #Mail settings
    client_key = user['client_key']
    mail_settings = get_Mail_settings(client_key)
    app.config.update(mail_settings)
    mail = Mail(app)
    data = dict(request.values)
    pat_data =  database_read(f"select * from patient where pat_id= '{data['id']}';",client_key=client_key)
    doc_id = data['doc_id']
    doc_data =  database_read(f"select * from doctor where doc_id= '{doc_id}';",client_key=client_key)
    pat_id = pat_data[0]['pat_id']
    pat_email = pat_data[0]['pat_email']
    doc_fullname = doc_data[0]['doc_first_name']+" " + doc_data[0]['doc_last_name'] 
    pat_fullname = pat_data[0]['pat_first_name']+" "+pat_data[0]['pat_last_name']
    doc_address = doc_data[0]['doc_address']
    #gmail_url = add Appointment to calendar
    subject = "פגישת טיפול עם  : " + doc_fullname
    sender_email= str(mail_settings['MAIL_USERNAME'])
    receiver_email = pat_email
    
    #Build Msg
    # Email content
    Portal_url = request.host_url + f"/clients/client_login"
    appointmentDuration = data['appointment_date']

    format = "%Y-%m-%dT%H:%M:%S.%fZ"
    Varformat = "%Y-%m-%d %H:%M:%S"

    date_obj = datetime.datetime.strptime(appointmentDuration, Varformat)
    time_change = datetime.timedelta(minutes=75) 
    appointmentEnd = date_obj + time_change 
     
    notification = 'נשמח לראותך '
    email_body = '''
                <div id='App_mail' style="text-align: right;direction: rtl;" >
                <b>נושא :</b> {Subject}<br>
                <b>מטופל :</b> {Patient}<br>
                <b>תאריך פגישה :</b> {Appointment Date}<br>
                <br>
                <b></b><br>
                {note}
                </div>
                <!-- Button code -->
                ''' 
            # Email data
    email_data = {
            'Subject': subject,    
            'Patient': pat_fullname,
            'Appointment Date': data['appointment_date'],
            'note': notification
            }          
    
    email_content = email_body.format(**email_data)
    email_content += f"<br><p><a href={Portal_url}>Log In to Portal</a></p>"

   

    # Create MIME message ICS File
    desc = u'פגישת טיפול'
    ics = render_ics(
            title=u'פגישת טיפול',
            description=desc,
            location= doc_address,
            start= date_obj,
            end= appointmentEnd,
            created=None,
            admin='Karin Adda',
            admin_mail=sender_email
        )
    message = MIMEMultipart()    
    message['From'] = sender_email
    message['To'] = receiver_email    
    message['Subject'] = str(subject)
    message.attach(MIMEText(email_content,'html',_charset='utf-8')) 
    message.attach(MIMEText(email_content,'text/calendar',_charset='utf-8'))    
    #calendar
    
    attachment = MIMEBase('text', 'calendar; name=calendar.ics; method=REQUEST; charset=UTF-8')
    attachment.set_payload(ics.encode('utf-8'))
    encoders.encode_base64(attachment)
    attachment.add_header('Content-Disposition', 'attachment; filename=%s' % "calendar.ics")
    
    message.attach(attachment)
    # Connect to the SMTP server and send the email
    with smtplib.SMTP(mail_settings['MAIL_SERVER'], 587) as server:
        server.starttls()
        server.login(mail_settings['MAIL_USERNAME'], mail_settings['MAIL_PASSWORD'])        
        server.sendmail(sender_email, receiver_email, message.as_string().encode("UTF-8"))
        server.close()
    print('Email sent!')
    return redirect(f"/appointment")

@app.route('/admin/mail-settings', methods=['GET', 'POST'])
@admin_only
def mail_settings():

    client_key = session['client_key']
    db_manager = DatabaseManager(client_key)
    conn = db_manager.connect_to_db(client_key)

    if request.method == 'POST':
        # Update each setting from the form data
        for key in ['MAIL_SERVER', 'MAIL_PORT', 'MAIL_USE_TLS', 'MAIL_USERNAME', 'MAIL_PASSWORD']:
            if key in request.form:
                update_Mail_setting(key, request.form[key])        
        flash("Mail settings updated successfully!", "success")
        return redirect(url_for('mail_settings'))

    # Fetch current settings to display in the form
    settings = get_Mail_settings(client_key)
    conn.close()
    return render_template('mail_settings.html', settings=settings)

@app.route('/SendNotification', methods=['POST'])
def Send_mail_Notification():
    data = dict(request.values)
    client_key = session['client_key']
    patien_id = database_read(f"select pat_id from patient WHERE pat_email ='{data['pat_email']}' order by pat_date desc LIMIT 1;",client_key=client_key)
    patien_data =  database_read(f"select * from patient WHERE pat_email ='{data['pat_email']}' order by pat_date desc LIMIT 1;",client_key=client_key)
    clinic_data =  database_read(f"select * from clinicinfo LIMIT 1;",client_key=client_key)
    data['client_key'] = client_key
    data['pat_id'] = patien_id[0]['pat_id']
    data['patien_data'] = patien_data
    data['clinic_data'] = clinic_data
    send_notification(data)
    return "ok"

@app.route('/admin/clinic-info', methods=['GET'])
@admin_only
def get_clinic_info():
    client_key = session['client_key']
    db_manager = DatabaseManager(client_key)
    conn = db_manager.connect_to_db(client_key)
    clinic_info = {}
    result = database_read("SELECT name, address, phone, email, website FROM clinicinfo LIMIT 1",client_key=client_key)
    if not result:
        return render_template('clinic-info.html', clinic=None, error="Clinic information not found"), 404
    return render_template('clinic-info.html', clinic=result[0])

@app.route('/admin/clinic-info', methods=['POST'])
@admin_only
def update_clinic_info():
    client_key = session['client_key']
    db_manager = DatabaseManager(client_key)
    conn = db_manager.connect_to_db(client_key)
    data = dict(request.values)
    cursor = conn.cursor()
  # Validate the input
    required_fields = ['name', 'address', 'phone', 'email']
    for field in required_fields:
        if field not in data or not data[field]:
             jsonify({"error": f"{field} is required"}), 400
    name =  data.get('name')
    address =  data.get('address')
    phone =  data.get('phone')
    email =  data.get('email')
    website =  data.get('website')
    # Construct the raw SQL update query
    clinic = database_read("SELECT * FROM clinicinfo LIMIT 1",client_key=client_key)
    if clinic:
        #Update
        query = f"UPDATE clinicinfo SET name ='{name}',address = '{address}',phone = '{phone}',email = '{email}',website = '{website}' WHERE id = 1"
        updateClinic = database_write(query,data)
        print(query,updateClinic)
        if updateClinic == 1 :
            flash("Clinic information updated successfully!", "success")
            return render_template('clinic-info.html', clinic=data)
    else:
      query = f"INSERT into  clinicinfo (name,address,phone,email,website) VALUES('{name}','{address}','{phone}','{email}','{website}');"
      ok = database_write(query,data)
      if ok == 1:
          flash("New Clinic information updated successfully!", "success")
          return render_template('clinic-info.html', clinic=data)

@app.route('/admin/adminPanel', methods=['GET'])
@admin_only
def admin_panel():
    return render_template('adminPanel.html')

#endregion

#region file add/delete/upload handeling

@app.route("/new-folder", methods=["POST"])
@flask_login.login_required
def create_new_folder():
    form = dict(request.values)
    id = str(uuid.uuid1())
    form['id'] = id
    sql = f"INSERT into folders (userid,id,name) VALUES (:userid,:id,:name);"
    ok = database_write(sql,form)
    if ok == 1:
       return "OK" 
    else:
       return "ERROR"

@app.route('/upload', methods=['POST'])
def upload(): 
        user = flask_login.current_user.get_dict() 
        data=  dict(request.values)
        clientKey = user['client_key'][:10]
        UPLOAD_FOLDER = os.path.join(path, 'uploads',clientKey)
        print(UPLOAD_FOLDER)
        if not os.path.isdir(UPLOAD_FOLDER):
            print("no dir")
            os.mkdir(UPLOAD_FOLDER)
        app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER 

        id = data['id']
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash('No file selected for uploading')
            return redirect(request.url)
        if file :                           
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            create = datetime.datetime.now().strftime("%Y-%m-%d")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            sql = f"INSERT into Patientfiles (pat_id,filename,filepath,createdate,userid) VALUES ('{id}','{filename}','{filepath}','{create}','{user['userid']}');"
            
            print("Upload_Sql",sql)
            ok = database_write(sql,data)
            if ok == 1:
               print('File successfully uploaded')
               return redirect(f"/patientform?id={id}")            
            else:
               return "ERROR"
        else:
            print('Allowed file types are txt, pdf, png, jpg, jpeg, gif')
            return redirect(request.url)

@app.route("/upload", methods=['GET'])
def upload_page():
    id = request.args.get('id')
    user = flask_login.current_user.get_dict()
    client_key = session['client_key'] 
    patientdata = database_read(f"select * from patient where pat_id= '{id}';",client_key = client_key)
    print("patientdata",patientdata)
    return render_template('upload.html',patientdata=patientdata)

@app.route('/delete_file', methods=['DELETE'])
@flask_login.login_required
def delete_file():
    user = flask_login.current_user.get_dict()
    data=  dict(request.values)
    clientKey = user['client_key'][:10]
    print("data",data)
    id = data['id']
    filename =  data['filename']
    sql = f"Delete from Patientfiles where pat_id ='{id}' and filename = '{filename}';"
    ok = database_write(sql,data)
    if ok == 1:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.remove(filepath)
        print('File successfully Deleted')
        return render_template('patientform.html')                         
    else:
        return "ERROR" 

@app.route('/download_file/<path:filename>',methods=['GET',"POST"])
@flask_login.login_required
def download_file(filename):
    user = flask_login.current_user.get_dict()
    data=  dict(request.values)   
    client_key = session['client_key'] 
    myfile =  database_read(f"select * from Patientfiles where filename= '{filename}';" ,client_key = client_key)
    if myfile:
        str_path = myfile[0]['filepath']
        for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
            for name in files:            
                # As we need to get the provided python file, 
                # comparing here like this
                if name == filename:  
                    path = os.path.abspath(os.path.join(root, name))
                    uploads = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
                    return send_from_directory(uploads, filename)
    else:
         return "Error"

@app.route('/delete_folder', methods=['DELETE'])
@flask_login.login_required
def delete_folder():    
    data=  dict(request.values)
    user = flask_login.current_user.get_dict() 
    id = data['folderid']
    sql = f"Delete from folders where id = '{id}';"
    print(sql)
    ok = database_write(sql,data)
    if ok == 1:
        print('project successfully Deleted')
        #Log
        logger.info(f"Project deleted - '{data['foldername']}' has been Sent by: {user['userid']} date: {str(datetime.datetime.now())}")
        return "OK"            
    else:
        return "ERROR" 
    
#endregion
   
#region Therapy Routes
@app.route("/doctor", methods=['GET'])
@admin_only
def doctor_Page():
    id = request.args.get('id')
    user = flask_login.current_user.get_dict()
    return render_template('doctor.html',Translate_data=Translate_data,user=user)

@app.route("/patient", methods=['GET'])
def patient_Page():
    id = request.args.get('id')
    user = flask_login.current_user.get_dict()
    return render_template('patient.html',Translate_data=Translate_data,user=user)

@app.route("/appointment", methods=['GET'])
@admin_only
def appointment_Page():
        id = request.args.get('id')
        user = flask_login.current_user.get_dict()
        return render_template('appointment.html',Translate_data=Translate_data,user=user)

@app.route("/patientform", methods=['GET'])
def patient_folder_Load():
    id = request.args.get('id')
    client_key = session['client_key']
    messages = database_read(f"select * from messages where pat_id= '{id}';",client_key=client_key)
    user = flask_login.current_user.get_dict()    
    patientdata = database_read(f"select * from patient where pat_id= '{id}';",client_key=client_key)
    tasksfiles = database_read(f"select * from Patientfiles where pat_id= '{id}';",client_key=client_key) #id = pat_id
    data = request.values
    if 'id' in request.values:
     id = request.values['id']
     #json.loads(data)
    if 'noteid' in request.values:
        noteid = request.values['noteid']
        med = Medicalnote()
        mednote = med.get(noteid)
    pat_id = data['id']
    apps = Appointments()
    appointments = apps.getappointmentsbypatient(pat_id)    
    notes = Medicalnotes()
    pat_mednotes = notes.getnotebypatient(pat_id)    
    length = len(pat_mednotes)
    for i in range(length):
        # GET ONLY TEXT from DB
        test= pat_mednotes[i]['body']       
        data = json.loads(test)        
        content_html = data.get('content', '')
        soup = BeautifulSoup(content_html, 'html.parser')
        text = soup.get_text() 
        # Get text and split by <br> tag
        text_list = [tag.get_text() for tag in soup.find_all(['div', 'br'])] 
        if len(text_list)> 1:     
            text_with_separators = ','.join(text_list)       
            pat_mednotes[i]["text"]=text_with_separators 
        else:
            pat_mednotes[i]["text"]=text
    session['patientdata'] = patientdata
    print("patientdata",patientdata)
    return render_template('patientform.html',Translate_data=Translate_data,user=user,patientdata=patientdata,messages=messages,appointments=appointments,pat_mednotes=pat_mednotes,tasksfiles=tasksfiles, alert="")

@app.route("/patientform", methods=["POST"])
@flask_login.login_required
def update_patien():
    user = flask_login.current_user.get_dict()
    client_key =  user['client_key']
    form = dict(request.values)
    id = form['pat_id']
    sql = "UPDATE patient SET pat_first_name =:pat_first_name, pat_last_name =:pat_last_name, pat_ph_no =:pat_ph_no, pat_address=:pat_address, pat_email =:pat_email, pat_insurance_no =:pat_insurance_no where pat_id =:pat_id"
    ok = database_write(sql,form)   
    if ok == 1:
        patientdata = database_read(f"select * from patient where pat_id= '{id}';",client_key=client_key)
        message = 'Success'
        return render_template('patientform.html',user=user,patient=patientdata,message=message)
    else:
       return "ERROR"

@app.route("/patientnotes" , methods=['GET'])
@flask_login.login_required
def patientnotes_page():
    user = flask_login.current_user.get_dict()
    data = request.values
    if 'id' in request.values:
     id = request.values['id']
     #json.loads(data)
    if 'noteid' in request.values:
        noteid = request.values['noteid']
        med = Medicalnote()
        mednote = med.get(noteid)
    pat_id = data['id']
    apps = Appointments()
    appointments = apps.get() 
    notes = Medicalnotes()
    pat_mednotes = notes.getnotebypatient(pat_id)
    #TEST GET ONLY TEXT
    test= pat_mednotes[0]['body']
    data = json.loads(test)
    content_html = data.get('content', '')
    soup = BeautifulSoup(content_html, 'html.parser')
    text = soup.get_text()
    print("text",text) 
    # Get text and split by <br> tag
    text_list = [tag.get_text() for tag in soup.find_all(['div'])]
    if len(text_list)>0:
        text_with_separators = ','.join(text_list)
        pat_mednotes[0]["text"]=text_with_separators
    else:
        pat_mednotes[0]["text"]=text
    return render_template('patientnotes.html',Translate_data=Translate_data,user=user,pat_mednotes=pat_mednotes)

@app.route("/medicalnote" , methods=['GET'])
@flask_login.login_required
@admin_only
def medicalnote_page():
    user = flask_login.current_user.get_dict()
    data = request.values
    client_key = session['client_key']
    pat_id = data['id']
    apps = Appointments()
    appointments = apps.get() 
    texteditor = ""
    pat_mednotes=""
    if 'noteid' in request.values:
        noteid = request.values['noteid']
        med = Medicalnote()
        mednote = med.get(noteid)
        # notes = Medicalnotes()
        # pat_mednotes = notes.getnotebypatient(pat_id)   
        pat_mednotes = database_read(f"select * from medrecords where pat_id= '{pat_id}' and rec_id = '{noteid}';",client_key=client_key)
        print("pat_mednotes",pat_mednotes)
        texteditor = pat_mednotes[0]['body']
        y = json.loads(texteditor)
        texteditor = y
        session['textineditor'] = texteditor['content']
    else:
        session['textineditor'] = " "
    return render_template('medicalnote.html',Translate_data=Translate_data,user=user,appointments=appointments,pat_mednotes=pat_mednotes,texteditor=texteditor)

@app.route("/medicalnote" , methods=['POST'])
@flask_login.login_required
def updatemedicalnote():
    user = flask_login.current_user.get_dict()
    data = dict(request.values)
    client_key = session['client_key']
    id = data['pat_id']
    contentbdy = data['content']
    if 'noteid' in request.values:
        noteid = request.values['noteid']
        #update
        print("update:", noteid)
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        sql = f"update medrecords SET pat_id= '{id}', create_date= '{now}' ,body = '{contentbdy}' where rec_id = '{noteid}';"
        ok = database_write(sql,data)
        if ok == 1:
            return render_template('medicalnote.html',user=user,data=data)
        else:
            return "ERROR"
    else:
        #New   
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        sql = f"INSERT into medrecords (pat_id,create_date,body) VALUES  ('{id}','{now}','{contentbdy}');"
        ok = database_write(sql,data)
        if ok == 1:
            return render_template('medicalnote.html',user=user,data=data)
        else:
            return "ERROR"

@app.route('/templates', methods=['GET'])
def get_templates_options():
    client_key = session['client_key']
    template = database_read(f"select rec_id,appointment_type from recordstamplates;",client_key=client_key)
    print("template",template)
    return jsonify({'templates': template})

@app.route('/Addappointment_type', methods=['POST'])
def create_type():
    data = request.json
    print("/Addappointment_type",data)

    if not data.get('name'):
        return jsonify({"error": "Name is required"}), 400
    new_type = data['name']    
    try:
        sql = f"INSERT into recordstamplates (appointment_type) VALUES  ('{new_type}');"
        ok = database_write(sql,data)
    except:
        return jsonify({"error": "Type already exists"}), 400
    return jsonify({"message": "appointment type created"}), 201

# Load template by appointment type
@app.route('/api/templates/<appointment_type>', methods=['GET'])
def get_template(appointment_type):
    client_key = session['client_key']
    #template = DocumentTemplate.query.filter_by(appointment_type=appointment_type).first()
    template = database_read(f"select tamplate from recordstamplates where appointment_type= '{appointment_type}';",client_key=client_key)
    if template:
        return jsonify({'template_text': template})
    return jsonify({'error': 'Template not found'}), 404

# Save or update a template
@app.route('/api/templates', methods=['POST'])
def save_template():
    data = request.json
    page_data = dict(request.values)    
    client_key = session['client_key']
    appointment_type = data.get('appointment_type')
    template_text = data.get('template_text')
    
    if not appointment_type or not template_text:
        return jsonify({'error': 'Missing required fields'}), 400
    
    template =  database_read(f"select * from recordstamplates where appointment_type= '{appointment_type}';",client_key=client_key)
    if template: #update
        sql = f"update recordstamplates SET tamplate= '{template_text}' where appointment_type = '{appointment_type}';"
        Update = database_write(sql,data) 
        if Update == 1:
          jsonify({'message': 'Template saved successfully'}) 
          return render_template('medicalnote.html',data=page_data)       
    else: #insert
        sql = f"INSERT into recordstamplates (appointment_type,tamplate) VALUES  ('{appointment_type}','{template_text}');"
        ok = database_write(sql,data)
        jsonify({'message': 'Template saved successfully'})
        return render_template('medicalnote.html',data=page_data)
    
@app.route("/message" , methods=['GET'])
@flask_login.login_required
def message_page():
    user = flask_login.current_user.get_dict()
    data = request.values
    client_key = session['client_key']
    pat_id = data['patid']
    app_id = 0
    if 'app_id' in request.values:
        app_id =  data['app_id']
    if 'mark' in request.values:
        sql = f"update messages SET status=1 where rec_id = '{recid}';"
        ok = database_write(sql,data)
        if ok == 1:
            return redirect(f"/portal?patid={pat_id}")  
        else:
            return "ERROR"
        
    if 'rec_id' in request.values:
        recid = request.values['rec_id']   
        pat_messages = database_read(f"select * from messages where pat_id= '{pat_id}' and rec_id = '{recid}';",client_key=client_key)
    else:
        pat_messages = database_read(f"select * from messages where pat_id= '{pat_id}' ;",client_key=client_key)
        return render_template('message.html',user=user,pat_messages=pat_messages)

@app.route("/message" , methods=['POST'])
@flask_login.login_required
def updatemessages():
    user = flask_login.current_user.get_dict()
    data = dict(request.values)
    id = data['pat_id']
    app_id = 0
    if 'app_id' in request.values:
        app_id =  data['app_id']
    msg = data['msg']
    if 'rec_id' in request.values:
        recid = request.values['rec_id']
        #update
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        sql = f"update messages SET pat_id= '{id}', create_date= '{now}' ,message = '{msg}',app_id='{app_id}' where rec_id = '{recid}';"
        ok = database_write(sql,data)
        if ok == 1:
            return render_template('medicalnote.html',user=user,data=data)
        else:
            return "ERROR"
    else:
        #New   
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        sql = f"INSERT into messages (pat_id,create_date,message,app_id,status) VALUES  ('{id}','{now}','{msg}','{app_id}','0');"
        ok = database_write(sql,data)
        if ok == 1:
            return render_template('message.html',user=user,data=data)
        else:
            return "ERROR"
#endregion

#region Clients Routes

# Function to generate the signature
def generate_signature(pat_id, client_key):
    data = f"{pat_id}:{client_key}"
    return hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()

# Function to validate the signature
def is_valid_signature(pat_id, client_key, signature):
    expected_signature = generate_signature(pat_id, client_key)
    return hmac.compare_digest(expected_signature, signature)   
     
@app.route("/clients/client_login", methods=['GET'])
def clientlogin_page():
    return render_template('/clientlogin.html',alert = "")      

@app.route("/clients/client_login", methods=['POST'])
def clientlogin_request():
    client_key = session["client_key"]
    form = dict(request.values)
    breakpoint()
    users = database_read(f"select * from patient where pat_email='{form['pat_mail']}' and pat_insurance_no='{form['pat_id']}';",client_key)
    print(users)
    print('users',users[0]['pat_id'])
    clientid= users[0]['pat_id']
    if len(users) >= 1: #user name exist, password not checked
        user = load_user(clientid)        
        flask_login.login_user(user)  
        return redirect(f"/portal?patid={clientid}") 
    else: #Invalid Email 
           return render_template('/clientlogin.html',alert = "Invalid Email/ID Number. please try again.")      
    
@app.route("/portal",methods=["GET"])
def get_portal():
    # Extract query parameters
    pat_id = request.args.get("pat_id")
    client_key = request.args.get("client_key")
    signature = request.args.get("signature")
    print(pat_id,client_key,signature)
    appointment_dates= {}
    if not pat_id or not client_key or not signature:
        return jsonify({"error": "Missing required parameters"}), 400

    # Validate the signature
    if not is_valid_signature(pat_id, client_key, signature):
        return jsonify({"error": "Invalid signature"}), 403
    #user = flask_login.current_user.get_dict()
    session['client_key'] = client_key 
    patientdata = database_read(f"select * from patient where pat_id= '{pat_id}';",None,client_key=client_key)
    patientmessages = database_read(f"select * from messages where status = 0 and pat_id= '{pat_id}';",None,client_key=client_key)
    lastappointment = database_read(f"SELECT *  FROM appointment where pat_id='{pat_id}' and appointment_date < DATETIME('now') order by appointment_date desc LIMIT 1;",None,client_key=client_key)
    nextappointment = database_read(f"SELECT *  FROM appointment where pat_id='{pat_id}' and appointment_date >= DATETIME('now') order by appointment_date  asc LIMIT 1;",None,client_key=client_key)
    patfiles = database_read(f"select * from Patientfiles where pat_id= '{pat_id}';",None,client_key=client_key) #id = pat_id
    if lastappointment:
        appointment_dates["lastappointment"] = lastappointment[0]["appointment_date"]
    if nextappointment:
        appointment_dates["nextappointment"] = nextappointment[0]["appointment_date"]
    apps = Appointments()
    appointments = apps.getappointmentsbypatient(pat_id)
    allappointments = apps.get()
    session['patientdata'] = patientdata
    return render_template('portal.html',patientdata=patientdata,patientmessages=patientmessages,allappointments=allappointments,appointments=appointments,appointment_dates=appointment_dates,patfiles=patfiles,alert="")


@app.route("/checkdate",methods=["POST"])
#@flask_login.login_required
def chekappointmentdate():
    data=  dict(request.values)
    #handel...
    print(data)
    #user = flask_login.current_user.get_dict() 
    id = data['pat_id']
    datetocheck = data['appointmentdate']    
    appoinmentindate = database_read(f"SELECT *  FROM appointment where appointment_date='{datetocheck}' order by appointment_date desc LIMIT 1;")
    if len(appoinmentindate) >= 1:
       return "ERROR"             
    else:
        return "OK" 

@app.route("/postmsg",methods=["GET","POST"])
def postmsg():
    data=  dict(request.values)
    app_id = data['app_id']
    appointment = RequestAppointment()
    patapp = appointment.get(app_id)
    if patapp:
        pat_id=patapp[0]['pat_id']
        app_date = patapp[0]['appointment_date']
        msg="בקשתך לטיפול בתאריך : {app_date}  לא אושרה יש לבקש תאריך נוסף, יום נפלא".format(app_date=app_date)
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        sql = f"INSERT into messages (pat_id,create_date,message,app_id) VALUES  ('{pat_id}','{now}','{msg}','{app_id}');"
        ok = database_write(sql,data)
        print('msg sent!',ok)
        return redirect(f"/appointment")  
    else:
        return "No Patient appointment"    
#endregion



#dev 
#app.run(debug=True)

#production  - remark above
if __name__ == "__main__":
    app.run(host="0.0.0.0", port = 80, debug=True)