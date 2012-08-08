import user_models
import exercise_models
import request_handler
from knowledgemap_util import deserializeMapCoords, serializeMapCoords
from exercises.exercise_util import exercise_graph_dict_json
from layout import topics_layout
from api.jsonify import jsonify
import user_util


class ViewKnowledgeMap(request_handler.RequestHandler):

    @user_util.open_access
    def get(self):
        user_data = (user_models.UserData.current() or
                     user_models.UserData.pre_phantom())
        user_exercise_graph = exercise_models.UserExerciseGraph.get(user_data)

        if user_data.reassess_from_graph(user_exercise_graph):
            user_data.put()

        show_review_drawer = (not user_exercise_graph.has_completed_review())

        template_values = {
            # TODO: should be camel cased once entire knowledgemap.js codebase
            # is switched to camel case
            'map_coords': jsonify(
                deserializeMapCoords(user_data.map_coords),
                camel_cased=False),
            'topic_graph_json': jsonify(
                topics_layout(user_data, user_exercise_graph),
                camel_cased=False),
            'graph_dict_data': exercise_graph_dict_json(
                user_data, user_exercise_graph),
            'user_data': user_data,
            'selected_nav_link': 'practice',
            'show_review_drawer': show_review_drawer,
        }

        if show_review_drawer:
            template_values['review_statement'] = 'Bemeester je kennis'
            template_values['review_call_to_action'] = "Aan de slag"

        self.render_jinja2_template('viewexercises.html', template_values)


class SaveMapCoords(request_handler.RequestHandler):

    @user_util.open_access
    def get(self):
        return

    @user_util.login_required
    def post(self):
        user_data = user_models.UserData.current()

        try:
            lat = self.request_float("lat")
            lng = self.request_float("lng")
            zoom = self.request_int("zoom")
        except ValueError:
            # If any of the above values aren't present in request,
            # don't try to save.
            return

        user_data.map_coords = serializeMapCoords(lat, lng, zoom)
        user_data.put()
