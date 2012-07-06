from __future__ import absolute_import

from google.appengine.ext import db


class SummerPaypalTransaction(db.Model):
    transaction_id = db.StringProperty()
    student_email = db.StringProperty()
    status = db.StringProperty()


class SummerStudent(db.Model):
    email = db.StringProperty()
    applier_email = db.StringProperty()
    application_year = db.StringProperty()
    application_status = db.StringProperty()
    accepted = db.BooleanProperty(default=False)

    first_name = db.StringProperty()
    last_name = db.StringProperty()
    date_of_birth = db.StringProperty()
    is_female = db.BooleanProperty()
    grade = db.StringProperty()
    school = db.StringProperty()
    school_zipcode = db.StringProperty()

    parent_email = db.StringProperty()
    parent_relation = db.StringProperty()

    first_choice = db.StringListProperty()
    second_choice = db.StringListProperty()
    third_choice = db.StringListProperty()
    no_choice = db.StringListProperty()
    session_1 = db.StringProperty()
    session_2 = db.StringProperty()
    session_3 = db.StringProperty()

    answer_why = db.TextProperty()
    answer_how = db.TextProperty()

    processing_fee = db.StringProperty()
    processing_fee_paid = db.BooleanProperty()

    extended_care = db.BooleanProperty()
    lunch = db.BooleanProperty()
    
    tuition = db.StringProperty()
    tuition_paid = db.BooleanProperty()

    comment = db.StringProperty()

    scholarship_applied = db.BooleanProperty()
    scholarship_granted = db.BooleanProperty()
    scholarship_amount = db.StringProperty()

    self_applied = db.BooleanProperty()

    def to_dict(self):
        return dict([(p, getattr(self, p)) for p in self.properties()])


class SummerParentData(db.Model):
    first_name = db.StringProperty()
    last_name = db.StringProperty()
    email = db.StringProperty()
    address_1 = db.StringProperty()
    address_2 = db.StringProperty()
    city = db.StringProperty()
    state = db.StringProperty()
    zipcode = db.StringProperty()
    country = db.StringProperty()
    phone = db.StringProperty()
    comments = db.TextProperty()
    students = db.ListProperty(db.Key)

    def to_dict(self):
        return dict([(p, unicode(getattr(self, p)))
                     for p in self.properties()])
