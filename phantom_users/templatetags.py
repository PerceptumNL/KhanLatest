import shared_jinja
import notifications


def login_notifications(user_data, continue_url):

    text = None
    notifications_dict = notifications.Notifier.pop()

    # Add any new login notifications for phantom users
    phantom_texts = [n.text for n in notifications_dict["phantoms"]]

    if phantom_texts:
        text = phantom_texts[0]

    return login_notifications_html(text, user_data, 
            continue_url)


def login_notifications_html(text, user_data, continue_url="/"):
    context = {"login_notification": text,
               "continue": continue_url,
               "user_data": user_data}

    return shared_jinja.get().render_template(
        "phantom_users/notifications.html", **context)
