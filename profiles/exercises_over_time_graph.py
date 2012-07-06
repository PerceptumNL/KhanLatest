import exercise_models


class ExerciseData(object):
        def __init__(self, name, exid, days_until_proficient, proficient_date):
            self.name = name
            self.display_name = exercise_models.Exercise.to_display_name(name)
            self.exid = exid
            self.days_until_proficient = days_until_proficient
            self.proficient_date = proficient_date


def exercises_over_time_graph_context(user_data):

    if not user_data:
        return {}

    user_exercises = []

    for ue in (exercise_models.UserExercise.all()
               .filter('user =', user_data.user)
               .filter('proficient_date >', None)
               .order('proficient_date')):
        days_until_proficient = (ue.proficient_date - user_data.joined).days   
        proficient_date = ue.proficient_date.strftime('%m/%d/%Y')
        data = ExerciseData(ue.exercise, ue.exercise, days_until_proficient,
                            proficient_date)
        user_exercises.append(data)

    return {
        'user_exercises': user_exercises,
        }
