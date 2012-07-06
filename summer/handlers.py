import os

# use json in Python 2.7, fallback to simplejson for Python 2.5
try:
    import json
except ImportError:
    import simplejson as json

import datetime
import math
import logging
import urllib, urllib2
import csv
import StringIO
import tarfile

import request_handler
import user_util
from app import App
from google.appengine.ext import db
from google.appengine.api import mail

import facebook_util
from user_models import UserData
from summer.models import SummerPaypalTransaction, SummerStudent, SummerParentData

PAYPAL_URL = "https://www.paypal.com/cgi-bin/webscr"

FROM_EMAIL = "no-reply@khan-academy.appspotmail.com"

class PaypalIPN(request_handler.RequestHandler):
    @user_util.open_access
    def post(self):
        self.get()

    @user_util.open_access
    def get(self):
        logging.info("Accessing %s" % self.request.path)
        txn_id = self.request.get('txn_id')
        student_email = self.request.get('custom')

        charset = self.request.get('charset')
        parameters = dict((arg, self.request.get(arg).encode(charset)) for arg in self.request.arguments())
        parameters['cmd'] = "_notify-validate"
        req = urllib2.Request(PAYPAL_URL, urllib.urlencode(parameters))
        req.add_header("Content-type", "application/x-www-form-urlencoded")

        response = urllib2.urlopen(req)
        status = response.read()
        if status == "VERIFIED":
            query = SummerPaypalTransaction.all()
            query.filter('transaction_id = ', txn_id)
            paypal_txn = query.get()

            if paypal_txn is None:
                paypal_txn = SummerPaypalTransaction()
                paypal_txn.transaction_id = txn_id
                paypal_txn.status = "Initiated"

            paypal_txn.student_email = student_email
            if 'payment_status' in parameters:
                paypal_txn.status = parameters['payment_status']

            query = SummerStudent.all()
            query.filter('email = ', paypal_txn.student_email)
            student = query.get()

            if student is None:
                logging.error("Student not found in DB for email <%s>" % student_email)
            else:
                if 'mc_gross' in parameters:
                    total_amount = int(parameters['mc_gross'])
                    if total_amount >= 1000:
                        # This is tuition
                        parent = SummerParentData.all().filter('email =', student.parent_email).get()
                        number_of_students = 0
                        students = []
                        for skey in parent.students:
                            s = SummerStudent.get(skey)
                            if s.accepted and not s.tuition_paid:
                               students.append(s)
                               number_of_students += 1

                        fee_per_student = int(total_amount/number_of_students)
                        if fee_per_student < 1000:
                            # Tuition is paid using the student's account
                            student.tuition = parameters['mc_gross']

                            if paypal_txn.status == "Completed":
                                student.tuition_paid = True
                            else:
                                student.tuition_paid = False

                            student.put()

                        else:
                            # Tuition paid using parent's account. This works because
                            # if paying via parent, then tuition for all students have
                            # to be paid together
                            for student in students:
                                student.tuition = str(fee_per_student)

                                if paypal_txn.status == "Completed":
                                    student.tuition_paid = True
                                else:
                                    student.tuition_paid = False

                                student.put()
                    else:
                        student.processing_fee = parameters['mc_gross']

                        if paypal_txn.status == "Completed":
                            student.processing_fee_paid = True
                        else:
                            student.processing_fee_paid = False

                        student.put()

            paypal_txn.put()
        else:
            logging.error("Paypal did not verify the IPN response transaction id <%s>" % txn_id)

        return

class PaypalAutoReturn(request_handler.RequestHandler):
    @user_util.open_access
    def post(self):
        self.get()

    @user_util.open_access
    def get(self):
        logging.info("Accessing %s" % self.request.path)
        student_email = self.request.get('student_email')
        user_email = self.request.get('user_email')
        txn_id = self.request.get('tx')

        query = SummerPaypalTransaction.all()
        query.filter('transaction_id = ', txn_id)
        paypal_txn = query.get()

        if paypal_txn is None:
            paypal_txn = SummerPaypalTransaction()
            paypal_txn.transaction_id = txn_id
            paypal_txn.student_email = student_email
            paypal_txn.status = "Initiated"

        values = {
            "cmd" : "_notify-synch",
            "tx" : txn_id,
            "at" : App.paypal_token_id
        }

        try:
            data = urllib.urlencode(values)
            req = urllib2.Request(PAYPAL_URL, data)
            response = urllib2.urlopen(req)
            output = response.read().split('\n')
        except Exception, e:
            logging.error("Error getting transaction info from Paypal <%s>" % e)
        else:
            query = SummerStudent.all()
            query.filter('email = ', student_email)
            student = query.get()
            if student is None:
                logging.error("Student not found in DB for email <%s>" % student_email)
            else:
                count = len(output) - 1
                paypal_attr = {}
                if output[0] == "SUCCESS":
                    for i in range(1,count):
                        nvp = output[i].split('=')
                        paypal_attr[nvp[0]] = nvp[1]

                    if 'payment_status' in paypal_attr:
                        paypal_txn.status = paypal_attr['payment_status']

                    if 'mc_gross' in paypal_attr:
                        total_amount = int(paypal_attr['mc_gross'])
                        if total_amount >= 1000:
                            # This is tuition
                            parent = SummerParentData.all().filter('email =', student.parent_email).get()

                            number_of_students = 0
                            students = []
                            for skey in parent.students:
                                s = SummerStudent.get(skey)
                                if s.accepted and not s.tuition_paid:
                                    students.append(s)
                                    number_of_students += 1

                            fee_per_student = int(total_amount/number_of_students)
                            if fee_per_student < 1000:
                                # Tuition is paid using student's account
                                student.tuition = paypal_attr['mc_gross']

                                if paypal_txn.status == "Completed":
                                    student.tuition_paid = True
                                else:
                                    student.tuition_paid = False

                                student.put()

                            else:
                                # Tuition paid using parent's account. This works because
                                # if paying via parent, then tuition for all students have
                                # to be paid together
                                for student in students:
                                    student.tuition = str(fee_per_student)

                                    if paypal_txn.status == "Completed":
                                        student.tuition_paid = True
                                    else:
                                        student.tuition_paid = False

                                    student.put()
                        else:
                            student.processing_fee = paypal_attr['mc_gross']

                            if paypal_txn.status == "Completed":
                                student.processing_fee_paid = True
                            else:
                                student.processing_fee_paid = False

                            student.put()

                    paypal_txn.put()
                else:
                    logging.error("Transaction %s for %s didn't succeed" % (txn_id, student_email))
                    student.processing_fee_paid = False

        self.redirect("/summer/application-status")

class GetStudent(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        student_email = self.request.get('student_email')
        logging.info("Accessing %s; student %s" % (self.request.path, student_email))
        query = SummerStudent.all()
        query.filter('email = ', student_email)
        student = query.get()
        if student is None:
            output_str = json.dumps(student)
        else:
            output_str = json.dumps(student.to_dict())

        self.response.set_status(200)
        callback = self.request.get('callback')
        if callback:
            self.response.out.write("%s(%s)" % (callback, output_str))
        else:
            self.response.out.write(output_str)

        return

class UpdateStudentStatus(request_handler.RequestHandler):
    @user_util.developer_required
    def get(self):
        template_values = {}
        self.render_jinja2_template('summer/uploadstatusfile.html', template_values)

    @user_util.developer_required
    def post(self):
        template_values = {}
        user_data = UserData.current()

        status_file = StringIO.StringIO(self.request_string('status_file'))
        reader = csv.reader(status_file)
        student_list = []
        for line in reader:
            student_email = line[0]
            student_status = line[1]
            student_comment = line[2]

            student = SummerStudent.all().filter('email =', student_email).get()
            if student is None:
                logging.error("Student %s not found" % student_email)
                continue

            student.application_status = student_status
            student.comment = student_comment
            if student_status == "Accepted":
                student.accepted = True

            student_list.append(student)

        db.put(student_list)

        self.response.out.write("OK")
        self.response.set_status(200)


class Download(request_handler.RequestHandler):
    def authenticated_response(self):
        user_data = UserData.current()
        user_email = user_data.user_email

        template_values = {
                "authenticated" : True,
                "user_email" : user_email,
        }

        sio = StringIO.StringIO()
        sw = csv.writer(sio)
        properties = [p for p in SummerStudent().properties()]
        sw.writerow(properties)
        for student in SummerStudent.all().fetch(5000):
            try:
                row = []
                for p in properties:
                    v = getattr(student, p)
                    if isinstance(v, basestring):
                        v = v.encode("utf-8")
                    row.append(v)
                sw.writerow(row)
            except Exception, e:
                logging.error("Unable to write row for student %s" % student.email)

        pio = StringIO.StringIO()
        pw = csv.writer(pio)
        properties = [p for p in SummerParentData().properties()]
        pw.writerow(properties)
        for parent in SummerParentData.all().fetch(5000):
            try:
              row = []
              for p in properties:
                  v = getattr(parent, p)
                  if isinstance(v, basestring):
                      v = v.encode("utf-8")
                  row.append(v)
              pw.writerow(row)
            except Exception, e:
                logging.error("Unable to write row for parent %s" % parent.email)

        f = StringIO.StringIO()
        tf = tarfile.open(fileobj=f, mode='w:gz')

        # All SummerStudents
        tinfo = tarfile.TarInfo(name="student_data.csv")
        tinfo.size = sio.len
        sio.seek(0)
        tf.addfile(tarinfo=tinfo, fileobj=sio)

        # All parents
        tinfo = tarfile.TarInfo(name="parent_data.csv")
        tinfo.size = pio.len
        pio.seek(0)
        tf.addfile(tarinfo=tinfo, fileobj=pio)

        tf.close()

        self.response.headers['Content-Type'] = "application/x-tar"
        self.response.headers['Content-Disposition'] = "attachment; filename=summer.tgz"

        self.response.out.write(f.getvalue())
        return

    @user_util.developer_required
    def get(self):
        template_values = {}
        user_data = UserData.current()

        if user_data is not None:
            return self.authenticated_response()

        else:
            template_values = {
                "authenticated" : False,
            }

        self.add_global_template_values(template_values)
        self.render_jinja2_template('summer/summer_process.html', template_values)

class Tuition(request_handler.RequestHandler):
    def authenticated_response(self):
        user_data = UserData.current()
        user_email = user_data.user_email
        nickname = ""
        if facebook_util.is_facebook_user_id(user_email):
            nickname = facebook_util.get_facebook_nickname(user_email)

        query = SummerStudent.all()
        query.filter('email = ', user_email)
        student = query.get()

        students = []
        is_parent = False

        if student is None:
            query = SummerParentData.all()
            query.filter('email = ', user_email)
            parent = query.get()
            if parent is None:
                return None

            is_parent = True
            number_of_students = 0
            for student_key in parent.students:
                student = SummerStudent.get(student_key)
                students.append(student)
                if student.accepted and not student.tuition_paid:
                    number_of_students += 1

        else:
            number_of_students = 1
            students.append(student)

        template_values = {
            "authenticated" : True,
            "is_parent" : is_parent,
            "students" : students,
            "number_of_students": json.dumps(number_of_students),
            "student" : students[0],
            "user_email" : user_email,
            "nickname" : nickname,
        }

        return template_values

    @user_util.manual_access_checking
    def post(self):
        self.get()

    @user_util.manual_access_checking
    def get(self):
        template_values = {}
        user_data = UserData.current()

        if user_data is not None:
            user_email = user_data.user_email
            template_values = self.authenticated_response()
            if template_values is None:
                nickname = user_email
                if facebook_util.is_facebook_user_id(user_email):
                    nickname = facebook_util.get_facebook_nickname(user_email)

                response = "User " + nickname + " not registered for Discovery Lab. Please login to Khan Academy as another user"
                self.response.out.write(response)
                return

            make_payment = self.request.get('make_payment')
            if make_payment:
                total_payment = self.request.get('total_payment')
                for student in template_values['students']:
                    email_in_request = self.request.get(student.email)
                    if email_in_request != student.email:
                        logging.error("Email <%s> expected in requst but not found" % student.email)

                    student.tuition = str(int(total_payment)/int(template_values['number_of_students']))
                    student.extended_care = False
                    if self.request.get('extended_care'):
                        student.extended_care = True

                    student.put()

                if template_values['is_parent']:
                    parent = SummerParentData.all().filter('email =', user_email).get()
                else:
                    parent = SummerParentData.all().filter('email =', template_values['student'].parent_email).get()

                payee_phone_a = ""
                payee_phone_b = ""
                payee_phone_c = ""
                phone_parts = parent.phone.split("-")
                if phone_parts is not None:
                    payee_phone_a = phone_parts[0]
                    payee_phone_b = phone_parts[1]
                    payee_phone_c = phone_parts[2]

                template_values['total_payment'] = total_payment
                template_values['authenticated'] = True
                template_values['make_payment'] = True
                template_values['parent'] = parent
                template_values['payee'] = parent
                template_values['payee_phone_a'] = payee_phone_a
                template_values['payee_phone_b'] = payee_phone_b
                template_values['payee_phone_c'] = payee_phone_c

        else:
            template_values = {
                "authenticated" : False,
            }

        self.add_global_template_values(template_values)
        self.render_jinja2_template('summer/summer_tuition.html', template_values)


class Status(request_handler.RequestHandler):
    def authenticated_response(self):
        user_data = UserData.current()
        user_email = user_data.user_email
        nickname = ""
        if facebook_util.is_facebook_user_id(user_email):
            nickname = facebook_util.get_facebook_nickname(user_email)

        query = SummerStudent.all()
        query.filter('email = ', user_email)
        student = query.get()

        students = []
        is_parent = False

        if student is None:
            query = SummerParentData.all()
            query.filter('email = ', user_email)
            parent = query.get()
            if parent is None:
                return None

            is_parent = True
            for student_key in parent.students:
                students.append(SummerStudent.get(student_key))

        else:
            students.append(student)

        template_values = {
            "authenticated" : True,
            "is_parent" : is_parent,
            "students" : students,
            "user_email" : user_email,
            "nickname" : nickname,
        }

        return template_values

    @user_util.manual_access_checking
    def get(self):
        template_values = {}
        user_data = UserData.current()

        if user_data is not None:
            template_values = self.authenticated_response()
            if template_values is None:
                self.redirect("/summer/application")
                return

        else:
            template_values = {
                "authenticated" : False,
            }

        self.add_global_template_values(template_values)
        self.render_jinja2_template('summer/summer_status.html', template_values)

class Application(request_handler.RequestHandler):
    def authenticated_response(self):
        user_data = UserData.current()
        user_email = user_data.user_email
        nickname = ""
        if facebook_util.is_facebook_user_id(user_email):
            nickname = facebook_util.get_facebook_nickname(user_email)

        students = []
        is_parent = False
        query = SummerStudent.all()
        query.filter('email = ', user_email)
        student = query.get()

        if student is not None:
            students.append(student)
        else:
            query = SummerParentData.all()
            query.filter('email = ', user_email)
            parent = query.get()
            if parent is not None:
                is_parent = True
                for student_key in parent.students:
                    students.append(SummerStudent.get(student_key))

        if len(students) > 0:
            applied = True
            student_email = self.request.get('student_email')
            query = SummerStudent.all()
            query.filter('email = ', student_email)
            student = query.get()
            if student is None:
                logging.error("Student <%s> not expected to be NULL in datastore, but it is" % student_email)
                student = students[0]

            query = SummerParentData.all()
            query.filter('email = ', student.parent_email)
            parent = query.get()
            assert(parent != None)

            student_js = json.dumps(student.to_dict())
            parent_js = json.dumps(parent.to_dict())
        else:
            applied = False
            student = None
            parent = None
            student_js = json.dumps(student)
            parent_js = json.dumps(parent)

        template_values = {
            "authenticated" : True,
            "applied" : applied,
            "is_parent" : is_parent,
            "is_parent_js" : json.dumps(is_parent),
            "students" : students,
            "student" : student,
            "student_js" : student_js,
            "parent" : parent,
            "parent_js" : parent_js,
            "user_email_js" : json.dumps(user_email),
            "user_email" : user_email,
            "nickname" : nickname,
        }

        return template_values

    @user_util.open_access
    def post(self):
        self.get()

    @user_util.open_access
    def get(self):
        template_values = {}
        user_data = UserData.current()

        if user_data is not None:
            user_email = user_data.user_email
            nickname = ""
            if facebook_util.is_facebook_user_id(user_email):
                nickname = facebook_util.get_facebook_nickname(user_email)

            application_filled = self.request.get('application_filled')
            make_payment = self.request.get('make_payment')

            if make_payment:
                student_email = self.request.get('student_email')
                is_parent_str = self.request.get('is_parent')

                query = SummerStudent.all()
                query.filter('email = ', student_email)
                student = query.get()

                if student is None:
                    output_str = 'Please <a href="/summer/application">apply</a> first' % student_email
                    self.response.out.write(output_str)
                    return

                if student.processing_fee_paid:
                    self.redirect("/summer/application-status")
                    return

                query = SummerParentData.all()
                query.filter('email = ', student.parent_email)
                parent = query.get()

                if parent is None:
                    logging.error("Unexpected NULL parent for student <%s> with parent <%s>" %
                                   (student_email, student.parent_email))

                if is_parent_str == "True":
                    is_parent = True
                else:
                    is_parent = False

                payee_phone_a = ""
                payee_phone_b = ""
                payee_phone_c = ""
                phone_parts = parent.phone.split("-")
                if phone_parts is not None:
                    payee_phone_a = phone_parts[0]
                    payee_phone_b = phone_parts[1]
                    payee_phone_c = phone_parts[2]

                template_values = {
                    "authenticated" : True,
                    "make_payment" : True,
                    "is_parent" : is_parent,
                    "is_parent_js" : json.dumps(is_parent),
                    "student" : student,
                    "student_js" : json.dumps(student.to_dict()),
                    "payee" : parent,
                    "payee_phone_a" : payee_phone_a,
                    "payee_phone_b" : payee_phone_b,
                    "payee_phone_c" : payee_phone_c,
                    "user_email" : user_email,
                    "nickname" : nickname,
                }

            elif not application_filled:
                template_values = self.authenticated_response()

            else:
                first_name = self.request.get('first_name')
                student_email = self.request.get('student_email')

                query = SummerStudent.all()
                query.filter('email = ', student_email)
                student = query.get()
                if student is None:
                    student = SummerStudent()
                    student.email = student_email
                    student.applier_email = user_email
                    student.processing_fee_paid = False
                    student.tuition_paid = False

                student.first_name = first_name
                student.last_name = self.request.get('last_name')

                student.date_of_birth = self.request.get('date_of_birth')

                if self.request.get('gender') == "Female":
                    student.is_female = True
                else:
                    student.is_female = False

                student.grade = self.request.get('grade')
                student.school = self.request.get('school')
                student.school_zipcode = self.request.get('school_zip')

                student.session_1 = self.request.get('session_1')
                student.session_2 = self.request.get('session_2')
                student.session_3 = self.request.get('session_3')

                session_choices = { "0":[], "1":[], "2":[], "3":[] }
                session_choices[student.session_1].append("Session 1")
                session_choices[student.session_2].append("Session 2")
                session_choices[student.session_3].append("Session 3")

                student.no_choice = session_choices["0"]
                student.first_choice = session_choices["1"]
                student.second_choice = session_choices["2"]
                student.third_choice = session_choices["3"]

                student.answer_why = self.request.get('answer_why')
                student.answer_how = self.request.get('answer_how')

                student.processing_fee = self.request.get('fee')

                student.tuition = 'TBD'

                student.application_year = '2012'
                student.application_status = 'Processing'

                if user_email == student_email:
                    is_parent = False
                    student.self_applied = True
                else:
                    is_parent = True
                    student.self_applied = False

                student.parent_relation = self.request.get('relation')
                student.parent_email = self.request.get('parent_email')

                student.put()

                query = SummerParentData.all()
                query.filter('email = ', student.parent_email)
                parent = query.get()
                if parent is None:
                    parent = SummerParentData()
                    parent.email = student.parent_email

                parent.first_name = self.request.get('parent_first_name')
                parent.last_name = self.request.get('parent_last_name')
                parent.address_1 = self.request.get('parent_address_1')
                parent.address_2 = self.request.get('parent_address_2')
                parent.city = self.request.get('parent_city')
                parent.state = self.request.get('parent_state')
                parent.zipcode = self.request.get('parent_zip')
                parent.country = self.request.get('parent_country')
                parent.phone = self.request.get('parent_phone')
                parent.comments = self.request.get('parent_comments')

                if student.key() not in parent.students:
                    parent.students.append(student.key())

                parent.put()

                if student.processing_fee_paid:
                    self.redirect("/summer/application-status")
                    return

                payee_phone_a = ""
                payee_phone_b = ""
                payee_phone_c = ""
                phone_parts = parent.phone.split("-")
                if phone_parts is not None:
                    payee_phone_a = phone_parts[0]
                    payee_phone_b = phone_parts[1]
                    payee_phone_c = phone_parts[2]

                # Only send email if the user's email is a valid one
                if not facebook_util.is_facebook_user_id(parent.email):
                    mail.send_mail( \
                        sender = FROM_EMAIL, \
                        to = parent.email, \
                        subject = "Khan Academy Discovery Lab Application", \
                        body = """Dear %s,
                
We have received your application for %s %s for the Khan Academy Discovery Lab 2012. Please ensure you have paid the $5.00 processing fee for the application.

We will notify you about the status of the application as soon as possible, no later than March 1st, 2012. You can always check the status of the application any time at http://www.khanacademy.org/summer/application-status.

Thank you!
Khan Academy Discovery Lab""" % (parent.first_name, student.first_name, student.last_name))

                template_values = {
                    "authenticated" : True,
                    "make_payment" : True,
                    "is_parent" : is_parent,
                    "is_parent_js" : json.dumps(is_parent),
                    "student" : student,
                    "student_js" : json.dumps(student.to_dict()),
                    "parent" : parent,
                    "parent_js" : json.dumps(parent.to_dict()),
                    "payee" : parent,
                    "payee_phone_a" : payee_phone_a,
                    "payee_phone_b" : payee_phone_b,
                    "payee_phone_c" : payee_phone_c,
                    "user_email" : user_email,
                    "nickname" : nickname,
                }

        else:
            template_values = {
                "authenticated" : False,
                "applied" : False
            }

        self.add_global_template_values(template_values)
        self.render_jinja2_template('summer/summer.html', template_values)
