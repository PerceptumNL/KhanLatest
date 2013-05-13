import backup_model
import json
import request_handler
import logging
import facebook_util
import user_util
import base64
import user_models
from datetime import datetime

from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore
from google.appengine.ext import db
from third_party.mapreduce import base_handler
from third_party.mapreduce import mapreduce_pipeline
from third_party.mapreduce import operation as op
from third_party.mapreduce import shuffler


class FileMetadata(db.Model):
  """A helper class that will hold metadata for the user's blobs.

  Specifially, we want to keep track of who uploaded it, where they uploaded it
  from (right now they can only upload from their computer, but in the future
  urlfetch would be nice to add), and links to the results of their MR jobs. To
  enable our querying to scan over our input data, we store keys in the form
  'user/date/blob_key', where 'user' is the given user's e-mail address, 'date'
  is the date and time that they uploaded the item on, and 'blob_key'
  indicates the location in the Blobstore that the item can be found at. '/'
  is not the actual separator between these values - we use '..' since it is
  an illegal set of characters for an e-mail address to contain.
  """

  __SEP = ".."
  __NEXT = "./"

  owner = db.UserProperty()
  filename = db.StringProperty()
  uploadedOn = db.DateTimeProperty()
  source = db.StringProperty()
  blobkey = db.StringProperty()
  wordcount_link = db.StringProperty()
  index_link = db.StringProperty()
  phrases_link = db.StringProperty()

  @staticmethod
  def getFirstKeyForUser(username):
    """Helper function that returns the first possible key a user could own.

    This is useful for table scanning, in conjunction with getLastKeyForUser.

    Args:
      username: The given user's e-mail address.
    Returns:
      The internal key representing the earliest possible key that a user could
      own (although the value of this key is not able to be used for actual
      user data).
    """

    return db.Key.from_path("FileMetadata", username + FileMetadata.__SEP)

  @staticmethod
  def getLastKeyForUser(username):
    """Helper function that returns the last possible key a user could own.

    This is useful for table scanning, in conjunction with getFirstKeyForUser.

    Args:
      username: The given user's e-mail address.
    Returns:
      The internal key representing the last possible key that a user could
      own (although the value of this key is not able to be used for actual
      user data).
    """

    return db.Key.from_path("FileMetadata", username + FileMetadata.__NEXT)

  @staticmethod
  def getKeyName(username, date, blob_key):
    """Returns the internal key for a particular item in the database.

    Our items are stored with keys of the form 'user/date/blob_key' ('/' is
    not the real separator, but __SEP is).

    Args:
      username: The given user's e-mail address.
      date: A datetime object representing the date and time that an input
        file was uploaded to this app.
      blob_key: The blob key corresponding to the location of the input file
        in the Blobstore.
    Returns:
      The internal key for the item specified by (username, date, blob_key).
    """

    sep = FileMetadata.__SEP
    return str(username + sep + str(date) + sep + blob_key)

class UserProblemLogHistory(backup_model.BackupModel):
    """Information about a single user with a single problem in an exercise."""
    user = db.UserProperty()
    user_id = db.StringProperty()  # Stable unique identifying string for a user
    execises = db.ListProperty(str, indexed=False)
    hour = db.DateTimeProperty(auto_now_add=False)
    count = db.IntegerProperty()

    @classmethod
    def insert(cls, user_id, exercises, hour, count):
        logging.error(user_id)
        user_data = user_models.UserData.get_from_user_id(user_id)
        pb=cls(user=user_data.user, user_id=user_id, exercises=exercises, hour=hour, count=count)
        logging.error("put")
        pb.put()
        logging.error("putted")


def problemlog_per_user_hour_map(problemlog):
    """Word count map function."""
    logging.error(problemlog)
    logging.error(problemlog.user_id)
    
    yield (problemlog.backup_timestamp.strftime("%d/%m/%y %H:00"), json.dumps({   
            "user_id": problemlog.user_id, 
            "exercise": problemlog.exercise 
        }))

def problemlog_per_user_hour_reduce(key, values):
    """Word count reduce function."""
    user_dict = {}
    logging.error(json.dumps(key))
    logging.error(json.dumps(values))
    for v in values:
        v = json.loads(v)
        user_id = v["user_id"]
        exercise = v["exercise"]
        if not user_id in user_dict:
            user_dict[user_id] = { "exercises": [exercise], "count": 0 }
        elif user_id in user_dict and not exercise in user_dict[user_id]["exercises"]:
            user_dict[user_id]["exercises"].append(exercise)
        user_dict[user_id]['count'] += 1

        
    for user_id, values in user_dict.items():
        logging.error(user_id + " " +  json.dumps(values))
        UserProblemLogHistory.insert(user_id, values['exercises'], datetime.strptime(key, "%d/%m/%y %H:%M"), values['count'])
    
    yield "%s: %s\n" % (key, json.dumps(values))

def problemlog_history_map(problemlog):
    """Word count map function."""
    yield (problemlog.backup_timestamp.strftime("%d/%m/%y"), "")


def problemlog_history_reduce(key, values):
    """Word count reduce function."""
    yield "%s: %d\n" % (key, len(values))
    #yield (key, len(values))

class ProblemLogHistoryPipeline(base_handler.PipelineBase):
  """A pipeline to run Word count demo.

  Args:
    blobkey: blobkey to process as string. Should be a zip archive with
      text files inside.
  """
  def run(self, filekey='YQaa=='):
    logging.debug("filename is %s" % filekey)
    output = yield mapreduce_pipeline.MapreducePipeline(
        "ProblemLogPerUserHour",
        "analytics.problemlog_per_user_hour_map",
        "analytics.problemlog_per_user_hour_reduce",
        "third_party.mapreduce.input_readers.DatastoreInputReader",
        "third_party.mapreduce.output_writers.BlobstoreOutputWriter",
        mapper_params={
            "entity_kind": 'exercise_models.ProblemLog',
        },
        reducer_params={
            "mime_type": "text/plain",
        },
        shards=64)
    yield StoreOutput("ProblemLogPerUserHourHistory", filekey, output)


  #def run(self, filekey='YQaa=='):
  #  logging.debug("filename is %s" % filekey)
  #  output = yield mapreduce_pipeline.MapreducePipeline(
  #      "ProblemLogPerUserHour",
  #      "analytics.problemlog_per_user_hour",
  #      "analytics.problemlog_history_reduce",
  #      "third_party.mapreduce.input_readers.DatastoreInputReader",
  #      "third_party.mapreduce.output_writers.BlobstoreOutputWriter",
  #      mapper_params={
  #          "entity_kind": 'exercise_models.ProblemLog',
  #      },
  #      reducer_params={
  #          "mime_type": "text/plain",
  #      },
  #      queue_name="problemlog-per-user-hour-statistics-mapreduce-queue",
  #      shards=64)
  #  yield StoreOutput("ProblemLogHistory", filekey, output)

class StoreOutput(base_handler.PipelineBase):
  """A pipeline to store the result of the MapReduce job in the database.

  Args:
    mr_type: the type of mapreduce job run (e.g., WordCount, Index)
    encoded_key: the DB key corresponding to the metadata of this job
    output: the blobstore location where the output of the job is stored
  """

  def run(self, mr_type, encoded_key, output):
    logging.error(output)
    logging.error(output[0])
    #encoded_key = "ahJkZXZ-bWFwcmVkdWNlLWRlbW9yWAsSDEZpbGVNZXRhZGF0YSJGdGVzdEBleGFtcGxlLmNvbS4uMjAxMy0wNS0xMiAxNDoxNToyOC4wNTkxMjQuLlIzU1V1bFVlTlRSbGN1d21OaVZ1M2c9PQw"
    #logging.debug("output is %s" % str(output))
    #key = db.Key(encoded=encoded_key)
    #m = FileMetadata.get(key)

    #m.wordcount_link = output[0]
    #m.index_link = output[0]
    #m.phrases_link = output[0]

    #m.put()

class ViewAnalytics(request_handler.RequestHandler):
    @user_util.developer_required
    def get(self):
        self.render_jinja2_template('analytics.html', {
        })

class ProblemLogHistory(request_handler.RequestHandler):
     @user_util.developer_required
     def get(self):
        #filekey = self.request.get("filekey")
        #blob_key = self.request.get("blobkey")
    
        #if self.request.get("word_count"):
        #  pipeline = WordCountPipeline(filekey, blob_key)
        #elif self.request.get("index"):
        #  pipeline = IndexPipeline(filekey, blob_key)
        #else:
        pipeline = ProblemLogHistoryPipeline()
        pipeline.start()
        self.redirect(pipeline.base_path + "/status?root=" + pipeline.pipeline_id)

