#Python 2.7

from flask_restful import Resource, Api, request
from package.model import conn



class Appointments(Resource):
    """This contain apis to carry out activity with all appiontments"""

    def get(self):
        """Retrive all the appointment and return in form of json"""

        appointment = conn.execute("SELECT p.*,d.*,a.* from appointment a LEFT JOIN patient p ON a.pat_id = p.pat_id LEFT JOIN doctor d ON a.doc_id = d.doc_id ORDER BY appointment_date DESC").fetchall()
        return appointment

    def getappointmentsbypatient(self,patid):
        """Retrive list of all the appointment of patient"""
        patappointments = conn.execute("SELECT p.*,m.*,d.* from appointment m LEFT JOIN patient p ON m.pat_id = p.pat_id LEFT JOIN doctor d ON m.doc_id = d.doc_id where m.pat_id = ? ORDER BY m.appointment_date DESC", (patid,)).fetchall()
        return patappointments 
    
    def post(self):
        """Create the appoitment by assiciating patient and docter with appointment date"""

        appointment = request.get_json(force=True)
        pat_id = appointment['pat_id']
        doc_id = appointment['doc_id']
        appointment_date = appointment['appointment_date']
        



        appointment['app_id'] = conn.execute('''INSERT INTO appointment(pat_id,doc_id,appointment_date)
            VALUES(?,?,?)''', (pat_id, doc_id,appointment_date)).lastrowid
        conn.commit()
        return appointment

    
class Appointment(Resource):
    """This contain all api doing activity with single appointment"""

    def get(self,id):
        """retrive a singe appointment details by its id"""

        appointment = conn.execute("SELECT * FROM appointment WHERE app_id=?",(id,)).fetchall()
        return appointment


    def delete(self,id):
        """Delete teh appointment by its id"""
        conn.execute("DELETE FROM appointment WHERE app_id=?",(id,))
        conn.commit()
        return {'msg': 'sucessfully deleted'}

    def put(self,id):
        """Update the appointment details by the appointment id"""

        appointment = request.get_json(force=True)
        pat_id = appointment['pat_id']
        doc_id = appointment['doc_id']
        conn.execute("UPDATE appointment SET pat_id=?,doc_id=? WHERE app_id=?",
                     (pat_id, doc_id, id))
        conn.commit()
        return appointment
    

class RequestAppointments(Resource):
    """This contain apis to carry out activity with all appiontments"""

    def get(self):
        """Retrive all the appointment and return in form of json"""

        appointment = conn.execute("SELECT p.*,d.*,a.* from pendingappointment a LEFT JOIN patient p ON a.pat_id = p.pat_id LEFT JOIN doctor d ON a.doc_id = d.doc_id where status = 0 ORDER BY appointment_date DESC").fetchall()
        return appointment

    def getappointmentsbypatient(self,patid):
        """Retrive list of all the appointment of patient"""
        patappointments = conn.execute("SELECT p.*,m.*,d.* from pendingappointment m LEFT JOIN patient p ON m.pat_id = p.pat_id LEFT JOIN doctor d ON m.doc_id = d.doc_id where where status = 0 and m.pat_id = ? ORDER BY m.appointment_date DESC", (patid,)).fetchall()
        return patappointments 
    
    def post(self):
        """Create the appoitment by assiciating patient and docter with appointment date"""

        appointment = request.get_json(force=True)
        pat_id = appointment['pat_id']
        doc_id = appointment['doc_id']
        appointment_date = appointment['appointment_date']
        



        appointment['app_id'] = conn.execute('''INSERT INTO pendingappointment(pat_id,doc_id,appointment_date)
            VALUES(?,?,?)''', (pat_id, doc_id,appointment_date)).lastrowid
        conn.commit()
        return appointment

class RequestAppointment(Resource):
    """This contain all api doing activity with single appointment"""

    def get(self,id):
        """retrive a singe appointment details by its id"""

        appointment = conn.execute("SELECT * FROM pendingappointment WHERE where status = 0 and app_id=?",(id,)).fetchall()
        return appointment


    def delete(self,id):
        """Delete teh appointment by its id"""
        conn.execute("DELETE FROM pendingappointment WHERE app_id=?",(id,))
        conn.commit()
        return {'msg': 'sucessfully deleted'}

    def approve(self,id):
        """approve teh appointment by its id"""
        conn.execute('''INSERT INTO appointment(pat_id,doc_id,appointment_date)
            (SELECT pat_id,doc_id,appointment_date FROM pendingappointment where pat_id=?)''',(id,))
        conn.commit()

        conn.execute("update pendingappointment set status = 1 WHERE app_id=?",(id,))
        conn.commit()
        return {'msg': 'sucessfully deleted'}

    def put(self,id):
        """Update the appointment details by the appointment id"""

        appointment = request.get_json(force=True)
        pat_id = appointment['pat_id']
        doc_id = appointment['doc_id']
        conn.execute("UPDATE pendingappointment SET pat_id=?,doc_id=? WHERE app_id=?",
                     (pat_id, doc_id, id))
        conn.commit()
        return appointment