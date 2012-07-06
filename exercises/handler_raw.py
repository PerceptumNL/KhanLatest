import urllib

import request_handler
import user_util
import exercises.file_contents


class RawExercise(request_handler.RequestHandler):
    @user_util.open_access
    def get(self):
        path = self.request.path
        exercise_file = urllib.unquote(path.split('/', 3)[3])
        self.response.headers["Content-Type"] = "text/html"
        contents = exercises.file_contents.raw_exercise_contents(exercise_file)
        self.response.out.write(contents)
