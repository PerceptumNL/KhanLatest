import exercise_models
import notifications


def update(user_data, user_exercise, threshold=False, isProf=False, gotBadge=False):
    if user_data == None:
        return False

    if not user_data.is_phantom:
        return False

    numquest = None

    if user_exercise != None:
        numquest = user_exercise.total_done
        prof = exercise_models.Exercise.to_display_name(user_exercise.exercise)

    numbadge = user_data.badges
    numpoint = user_data.points

    notification = None

    # First question
    if (numquest == 1):
        notification = notifications.PhantomNotification("Je hebt je eerste vraag beantwoord! Je moet[login]")
    # Every 10 questions, more than 20 every 5
    if (numquest != None and numquest % 10 == 0) or \
       (numquest != None and numquest > 20 and numquest % 5 == 0):
        notification = notifications.PhantomNotification("Je hebt %d vragen beantwoord! Je moet [login]" % numquest)
    #Proficiency
    if isProf:
        notification = notifications.PhantomNotification("Je bent gevorderd in %s. Je moet [login]" % prof)
    #First Badge
    if numbadge != None and len(numbadge) == 1 and gotBadge:
        achievements_url = "%sachievements" % user_data.profile_root
        notification = notifications.PhantomNotification(
                "Gefeliciteerd met het behalen van je eerste <a href='%s'>badge</a>! Je moet [login]" %
                        achievements_url)
    #Every badge after
    if numbadge != None and len(numbadge) > 1 and gotBadge:
        notification = notifications.PhantomNotification("Je hebt tot nu toe <a href='/profile'>%d badges</a> verdiend. Je moet [login]" % len(numbadge))
    #Every 2.5k points
    if numpoint != None and threshold:
        numpoint = 2500 * (numpoint / 2500) + 2500
        notification = notifications.PhantomNotification("Je hebt meer dan <a href='/profile'>%d punten</a> behaald! Je moet [login]" % numpoint)

    if notification:
        notification.push(user_data)
