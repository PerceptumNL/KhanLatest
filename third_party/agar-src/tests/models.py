from google.appengine.ext import db
from google.appengine.ext import blobstore

class Model2(db.Model):

    model2_prop = db.StringProperty()
    
    @property
    def my_method(self):
        return "I say blah!"

class Model1(db.Model):
    string = db.StringProperty()
    bytestring = db.ByteStringProperty()
    boolean = db.BooleanProperty()
    integer = db.IntegerProperty()
    float_ = db.FloatProperty()
    datetime = db.DateTimeProperty()
    date = db.DateProperty()
    time = db.TimeProperty()
    list_ = db.ListProperty(long)
    stringlist = db.StringListProperty()
    reference = db.ReferenceProperty(reference_class=Model2, collection_name="references")
    selfreference = db.SelfReferenceProperty(collection_name="models")
    blobreference = blobstore.BlobReferenceProperty()
    user = db.UserProperty()
    blob = db.BlobProperty()
    text = db.TextProperty()
    category = db.CategoryProperty()
    link = db.LinkProperty()
    email = db.EmailProperty()
    geopt = db.GeoPtProperty()
    im = db.IMProperty()
    phonenumber = db.PhoneNumberProperty()
    postaladdress = db.PostalAddressProperty()
    rating = db.RatingProperty()
