import base64
from collections import defaultdict
from email import encoders
from email.mime.base import MIMEBase
import pathlib
from bs4 import BeautifulSoup
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from time import sleep
from flask import Flask, send_file,flash,render_template,request,redirect, send_from_directory, session
import flask_login
import sqlite3
import datetime
import uuid
import hashlib
from werkzeug.utils import secure_filename
from flask_restful import Resource, Api
from package.patient import Patients, Patient
from package.doctor import Doctors, Doctor
from package.appointment import Appointments, Appointment,RequestAppointments,RequestAppointment
from package.common import Common
from package.User import User
from package.client import ClientUser
from package.medicalnote import Medicalnote,Medicalnotes
from flask_mail import Mail, Message
from create_account import create_account
from mail import send_notification
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


#Settings
with open('config.json') as config_file:
    config_data = json.load(config_file)
Globalsetting = config_data['Global'] 
  
mail_settings = config_data['mail_settings']

database_filename = str(Globalsetting['database']) #"TherapyManager.db"
app.config['SECRET_KEY'] = 'AvivimSecretKey'
path = os.getcwd()

UPLOAD_FOLDER = os.path.join(path, 'uploads')
if not os.path.isdir(UPLOAD_FOLDER):
    os.mkdir(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


app.config.update(mail_settings)
mail = Mail(app)
#Logs
handler = logging.FileHandler('LogFile.log') # creates handler for the log file
app.logger.addHandler(handler) # Add it to the built-in logger
app.logger.setLevel(logging.DEBUG)         # Set the log level to debug
logger = app.logger
#Log in 
login_manager = flask_login.LoginManager()
login_manager.init_app(app)


#region Main App

@login_manager.user_loader
def load_user(userid):  #or client patid
    users = database_read(f"select * from accounts where userid='{userid}';")
    client = database_read(f"select * from patient where pat_id='{userid}';")
    
    if len(users)==1:        
        user = User(users[0]['userid'],users[0]['email'],users[0]['name'])
    else:
        user = ClientUser(client[0]['pat_id'],client[0]['pat_email'],client[0]['pat_first_name'])
    print("userloader", user)
    if user:
        user.id = userid
        return user
    else:
        return None

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

@app.route("/")
def index_page():    
    if flask_login.current_user.is_authenticated:
        print("is_authenticated")
        logger.info(str(flask_login.current_user.get_dict()) + " Has Logged in")   
        user = flask_login.current_user.get_dict()
        apps = Appointments()
        appointments= apps.get()   
        return render_template('/index.html',user=user,appointments=appointments)
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
        ok = create_account(form)
        session['formData'] = form
        print('ok:' ,ok)
        if ok == 1:            
            user = load_user(form['userid'])
            logger.info("New User Created: "+ user.name)           
            flask_login.login_user(user)            
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
    users = database_read("select * from accounts where userid=:userid",form)
    formid = form['userid']
    print("formid",formid)

    if len(users) == 1: #user name exist, password not checked
        salt = users[0]['salt']
        saved_key = users[0]['password']
        generated_key = hashlib.pbkdf2_hmac('sha256',form['password'].encode('utf-8'),salt.encode('utf-8'),10000).hex()

        if saved_key == generated_key: #password match
            user = load_user(formid)
            logger.info(f"Login successfull - '{formid}'  date: {str(datetime.datetime.now())}")
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
    flask_login.logout_user()
    return redirect("/")

@app.route("/main")
@flask_login.login_required
def main_page():
    folderid="0"
    if 'folderid' in request.values:
        folderid = request.values['folderid']
    id="1"
    if 'id' in request.values:
        id = request.values['id']

    user = flask_login.current_user.get_dict()    
    task_users = database_read(f"select name,email from accounts  order by name;")
    folders = database_read(f"select * from folders order by name;")
    tasks = database_read(f"select * from tasks where folderid= '{folderid}' AND status != 'CLOSE';")
    maintask = database_read(f"select * from tasks where id= '{id}';") #AND userid='{user['userid']}'
    closedtasks = database_read(f"select * from tasks where status = 'CLOSE';")
    tasksfiles = database_read(f"select * from tasksfiles where id= '{id}';")
    TaskNotes = database_read(f"select * from TasksNotes where id= '{id}';")
    TaskCategories = database_read(f"select * from categories;")
    if len(maintask) == 1:
        maintask = maintask[0]
    else:
        maintask={}
    return render_template('main.html',user=user,folders=folders,tasks=tasks,maintask=maintask,folderid=folderid,id=id,task_users=task_users,tasksfiles=tasksfiles,TaskNotes=TaskNotes,TaskCategories=TaskCategories,closedtasks=closedtasks)

@app.route("/save_task", methods=['POST'])
@flask_login.login_required
def task_update():
    user = flask_login.current_user.get_dict()
    form = dict(request.values)
    id = form['id']
    folderid = form['folderid']
    session['formData'] = form
    change_in_task=""
    if 'submit-close' in form:
        form['status']= 'CLOSE'  #status open or close
        change_in_task= "Task was Closed"
        #Log
        logger.info(f"Task '{id}' has been closed by: {user['userid']} date: {str(datetime.datetime.now())}")
        #sendmail
        ok = send_notification(change_in_task) 
    if 'submit-reopen' in form:
        form['status']= 'OPEN'  #status open or close
        change_in_task= "Task was Reopened"
        #Log
        logger.info(f"Task '{id}' has been Reopened by: {user['userid']} date: {str(datetime.datetime.now())}")
        #sendmail
        ok = send_notification(change_in_task)         
    if 'submit-delete' in form:
        database_write(f"delete from tasks where id='{id}';")
        change_in_task= "Task was Deleted"
        #Log
        logger.info(f"Task '{id}' has been delete by: {user['userid']} date: {str(datetime.datetime.now())}")
        #mail
        ok = send_notification(change_in_task) 
        return redirect(f"/main?folderid={folderid}")
    if id == "": #new TASK
        id = str(uuid.uuid1())
        form['id'] = id
        form['status'] = 'OPEN'
        form['created'] = datetime.datetime.now().strftime("%Y-%m-%d")
        sql = """insert into tasks 
        (userid,folderid,id,title,due,reminder,created,category,priority,status,desc,assignto) values 
        (:userid,:folderid,:id,:title,:due,:reminder,:created,:category,:priority,:status,:desc,:assignto);"""
        ok = database_write(sql,form)
        if ok == 1:
            return redirect(f"/main?folderid={folderid}&id{id}") 
        else:
            return redirect(f"/error?folderid={folderid}&id{id}")         
    else: #existing task Noraml Update
        maintask = database_read(f"select * from tasks where id= '{id}' ;")  #AND userid='{user['userid']}'          
        sql = "UPDATE tasks SET title =:title, due =:due, reminder =:reminder, category =:category, priority =:priority, status=:status, desc =:desc, assignto =:assignto where id =:id"
        ok = database_write(sql,form)
        if ok == 1:
           ## SEND Notification mail'##
           if maintask[0].get('assignto') != form.get('assignto'):
             #Log
            logger.info(f"Task : '{form['id']}' is now assinged to: {form.get('assignto')}  by: {user['userid']} date: {str(datetime.datetime.now())}")
            #send Email
            session['formData'] = form
            assinged_notif = f"Task : '{form['id']}' was now assinged to: {form.get('assignto')}  by: {user['userid']}"
            notif_sent = send_notification(assinged_notif) 
            if notif_sent:
                return redirect(f"/main?folderid={folderid}&id={id}") 
            else:
                return redirect(f"/error?folderid={folderid}&id={id}") 
           else:
            return redirect(f"/main?folderid={folderid}&id={id}") 
        else:
            return redirect(f"/error?folderid={folderid}&id={id}") 
    return "ok"

#endregion

#General Routes
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
    patientdata = database_read(f"select * from patient where pat_id= '{id}';")
    print("patientdata",patientdata)
    return render_template('upload.html',patientdata=patientdata)

@app.route('/delete_file', methods=['DELETE'])
@flask_login.login_required
def delete_file():
    user = flask_login.current_user.get_dict()
    data=  dict(request.values)
    print("data",data)
    id = data['id']
    print("id",id)
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
    myfile =  database_read(f"select * from Patientfiles where filename= '{filename}';")
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
    print(data)
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
    
@app.route('/send-mail', methods=['GET',"POST"])
def send_appointment(notification=''):
    user = flask_login.current_user.get_dict() 
    data = dict(request.values)
    pat_data =  database_read(f"select * from patient where pat_id= '{data['id']}';")
    doc_id = data['doc_id']
    doc_data =  database_read(f"select * from doctor where doc_id= '{doc_id}';")
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

    appointmentDuration = data['appointment_date']
    print(appointmentDuration)
    format = "%Y-%m-%dT%H:%M:%S.%fZ"
    Varformat = "%Y-%m-%d %H:%M:%S"
    
    #print(appointmentDuration.strftime("%Y-%m-%dT%H:%M:%SZ"))
    date_obj = datetime.datetime.strptime(appointmentDuration, Varformat)
    time_change = datetime.timedelta(minutes=75) 
    appointmentEnd = date_obj + time_change 
    print(date_obj,appointmentEnd) 
   
    
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

    # desc = """רציתי ליצור קשר כדי לקבוע את פגישת הטיפול הבאה שלנו,
    # להמשיך את עבודתנו יחד במסע הרווחה הרגשית.
    # בנוסף, אם יש נושאים או תחומים ספציפיים שבהם תרצה להתמקד במהלך הפגישה הבאה שלנו,
    # אנא אל תהסס ליידע אותי. ההשקעה שלך חשובה,
    #   אני רוצה להבטיח שהמפגשים שלנו יהיו מותאמים לצרכים ולמטרות שלך.
    # אני מחכה בקוצר רוח לפגישה הבאה שלנו.
    # להמשך עבודתנו המשותפת.בינתיים,
    #   אם יש לך שאלות או חששות,
    #   אנא אל תהסס לפנות.בברכה ,
    #   קארין עדה"""

    desc = u'פגישת טיפול'

    # Create MIME message
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
    print(ics)

    message = MIMEMultipart()    
    message['From'] = sender_email
    message['To'] = receiver_email    
    message['Subject'] = str(subject)
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
#endregion

#Therapy Routes
#region Therapy Routes
@app.route("/doctor", methods=['GET'])
def doctor_Page():
    id = request.args.get('id')
    user = flask_login.current_user.get_dict()
    mytasks = database_read(f"select ts.*,fol.name as foldername from tasks as ts left join folders as fol on ts.folderid = fol.id where assignto= '{user['name']}'")
    closedtasks = database_read(f"select ts.*,fol.name as foldername from tasks as ts left join folders as fol on ts.folderid = fol.id where  status = 'CLOSE';")
    print(closedtasks)
    return render_template('doctor.html',user=user)

@app.route("/patient", methods=['GET'])
def patient_Page():
    id = request.args.get('id')
    user = flask_login.current_user.get_dict()
    mytasks = database_read(f"select ts.*,fol.name as foldername from tasks as ts left join folders as fol on ts.folderid = fol.id where assignto= '{user['name']}'")
    closedtasks = database_read(f"select ts.*,fol.name as foldername from tasks as ts left join folders as fol on ts.folderid = fol.id where  status = 'CLOSE';")
    print(closedtasks)
    return render_template('patient.html',user=user)

@app.route("/appointment", methods=['GET'])
def appointment_Page():
    id = request.args.get('id')
    user = flask_login.current_user.get_dict()
    return render_template('appointment.html',user=user)

@app.route("/patientform", methods=['GET'])
def patient_folder_Load():
    id = request.args.get('id')
    user = flask_login.current_user.get_dict()    
    patientdata = database_read(f"select * from patient where pat_id= '{id}';")
    tasksfiles = database_read(f"select * from Patientfiles where pat_id= '{id}';") #id = pat_id
    data = request.values
    if 'id' in request.values:
     id = request.values['id']
     #json.loads(data)
    if 'noteid' in request.values:
        noteid = request.values['noteid']
        med = Medicalnote()
        mednote = med.get(noteid)
    pat_id = data['id']
    print("pat_id",pat_id)
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
        text_list = [tag.get_text() for tag in soup.find_all('div')]
        text_with_separators = ','.join(text_list)
        pat_mednotes[i]["text"]=text_with_separators   
    print("appointments:",appointments)
    session['patientdata'] = patientdata
    return render_template('patientform.html',user=user,patientdata=patientdata,appointments=appointments,pat_mednotes=pat_mednotes,tasksfiles=tasksfiles, alert="")

@app.route("/patientform", methods=["POST"])
@flask_login.login_required
def update_patien():
    user = flask_login.current_user.get_dict()
    form = dict(request.values)
    id = form['pat_id']
    print("patientform",form)
    sql = "UPDATE patient SET pat_first_name =:pat_first_name, pat_last_name =:pat_last_name, pat_ph_no =:pat_ph_no, pat_address=:pat_address, pat_email =:pat_email, pat_insurance_no =:pat_insurance_no where pat_id =:pat_id"
    ok = database_write(sql,form)
    ok=1    
    if ok == 1:
        patientdata = database_read(f"select * from patient where pat_id= '{id}';")
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
    # Get text and split by <br> tag
    text_list = [tag.get_text() for tag in soup.find_all('div')]
    text_with_separators = ','.join(text_list)
    pat_mednotes[0]["text"]=text_with_separators
    return render_template('patientnotes.html',user=user,pat_mednotes=pat_mednotes)

@app.route("/medicalnote" , methods=['GET'])
@flask_login.login_required
def medicalnote_page():
    user = flask_login.current_user.get_dict()
    data = request.values
    pat_id = data['id']
    apps = Appointments()
    appointments = apps.get() 
    texteditor = ""
    pat_mednotes=""
    if 'noteid' in request.values:
        noteid = request.values['noteid']
        print("noteid",noteid)
        med = Medicalnote()
        mednote = med.get(noteid)
        # notes = Medicalnotes()
        # pat_mednotes = notes.getnotebypatient(pat_id)   
        pat_mednotes = database_read(f"select * from medrecords where pat_id= '{pat_id}' and rec_id = '{noteid}';")
        print("pat_mednotes",pat_mednotes)
        texteditor = pat_mednotes[0]['body']
        y = json.loads(texteditor)
        texteditor = y
        session['textineditor'] = texteditor['content']
    else:
        session['textineditor'] = " "
    return render_template('medicalnote.html',user=user,appointments=appointments,pat_mednotes=pat_mednotes,texteditor=texteditor)

@app.route("/medicalnote" , methods=['POST'])
@flask_login.login_required
def updatemedicalnote():
    user = flask_login.current_user.get_dict()
    data = dict(request.values)
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
        print("insert:", id)   
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        sql = f"INSERT into medrecords (pat_id,create_date,body) VALUES  ('{id}','{now}','{contentbdy}');"
        ok = database_write(sql,data)
        if ok == 1:
            return render_template('medicalnote.html',user=user,data=data)
        else:
            return "ERROR"
#endregion

#region Clients Routes
        
@app.route("/clients/client_login", methods=['GET'])
def clientlogin_page():
    return render_template('/clientlogin.html',alert = "")      

@app.route("/clients/client_login", methods=['POST'])
def clientlogin_request():
    form = dict(request.values)
    users = database_read("select * from patient where pat_email=:pat_mail and pat_insurance_no=:pat_id",form)
    print('users',users[0]['pat_id'])
    clientid= users[0]['pat_id']
    if len(users) >= 1: #user name exist, password not checked
        user = load_user(users[0]['pat_id'])
        print("user",user)
        flask_login.login_user(user)  
        return redirect(f"/portal?patid={clientid}") 
    else: #Invalid Email 
           return render_template('/clientlogin.html',alert = "Invalid Email. please try again.")      
    
@app.route("/portal",methods=["GET"])
@flask_login.login_required
def get_portal():
    appointment_dates= {}
    id = request.args.get('patid')
    user = flask_login.current_user.get_dict()
    patientdata = database_read(f"select * from patient where pat_id= '{id}';")
    lastappointment = database_read(f"SELECT *  FROM appointment where pat_id='{id}' and appointment_date < DATETIME('now') order by appointment_date desc LIMIT 1;")
    nextappointment = database_read(f"SELECT *  FROM appointment where pat_id='{id}' and appointment_date >= DATETIME('now') order by appointment_date  asc LIMIT 1;")
    if lastappointment:
        appointment_dates["lastappointment"] = lastappointment[0]["appointment_date"]
    if nextappointment:
        appointment_dates["nextappointment"] = nextappointment[0]["appointment_date"]
    print(patientdata)
    apps = Appointments()
    appointments = apps.getappointmentsbypatient(id)
    return render_template('portal.html',user=user,patientdata=patientdata,appointments=appointments,appointment_dates=appointment_dates,alert="")

#endregion



#dev 
app.run(debug=True)

#production  - remark above
if __name__ == "__main__":
    app.run(host="0.0.0.0", port = 80, debug=True)