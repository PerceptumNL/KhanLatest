"""Notifications are for notifying users of various important events.

Notification classes can be created for any type of event, such as earning a
badge or crossing a certain energy point threshold.

Senders of notifications follow the pattern of creating a notification object
and pushing it onto a user. Example:

    badge_notification = notifications.BadgeNotification(sweet_badge.name)
    badge_notification.push(monkey_user)

Consumers of notifications ask the notifier for all notes on a particular user.
Example:

    notification_dict = notifications.Notifier.pop()
    badge_notifications = notification_dict["badges"]

Notifications can choose to be persistent, in which case they will continue to
sit in a user's queue even after multiple Notifier.pop()s. If they aren't
persistent, a single pop will remove the notification from the queue (and it's
therefore up to the pop()er to handle the notification appropriately.

You can create a new Notification type by subclassing Notification -- see
BadgeNotification and PhantomNotification as examples. The process of queueing
and persisting these notifications should be somewhat abstracted away for users
of the above patterns. Famous last words.
"""
from google.appengine.ext import db

import request_cache
import user_models


class Notification(object):
    """Base Notification subclassed by specific types of user notifications.
    
    There are three required properties that must be defined by any
    implementing subclass:
    
        note_type (string description of notification type)
        persistent (true if this notification persists after pop)
        limit (how many notifications of this type can exist at once per user)
    """
    
    def push(self, user_data):
        """Push this notification onto the specific user's queue."""
        Notifier.push(user_data, self)

    @classmethod
    def clear(cls, user_data):
        """Clear notifications of this class's type for the specified user."""
        Notifier.clear(user_data, cls.note_type)

    @staticmethod
    def clear_all(user_data):
        """Clear all notifications for the specific user."""
        Notifier.clear_all(user_data)


class BadgeNotification(Notification):
    """Badge notifications are shown whenever a user earns a new badge."""

    note_type = "badges"  # description of notification type
    persistent = False  # whether or not this notification persists after pop
    limit = 2  # how many notifications of this type can exist at once per user

    def __init__(self, badge_name):
        if not badge_name:
            raise ValueError("Missing badge name for BadgeNotification")

        self.badge_name = badge_name


class PhantomNotification(Notification):
    """Phantom notifications are used to tease phantom users to login."""

    note_type = "phantoms"  # description of notification type
    persistent = True  # whether or not this notification persists after pop
    limit = 1  # how many notifications of this type can exist at once per user

    def __init__(self, text):
        if not text:
            raise ValueError("Missing text for PhantomNotification")

        self.text = text


class Notifier(object):
    """Notifier pushes, pops, and clears notifications for users."""

    @staticmethod
    @request_cache.cache()
    def pop():
        """Pop and return the current user's notifications."""
        return Notifier.pop_for_user_data(user_models.UserData.current())

    @staticmethod
    def pop_for_user_data(user_data):
        """Pop and return the specified user's notifications.
        
        TODO(kamens): it will be important to separate pop()ing one type of
        notification from other types in the future. Otherwise, consumers of,
        say, BadgeNotifications will find themselves responsible for handling
        MonkeyNotifications because they've been popped off the user's queue
        unwittingly. Our current usage pattern doesn't require this because we
        handle all notifications at once, so we'll add this when necessary.

        Args:
            user_data: The user_data receiving the notification
        """

        notifications = {}

        for cls in Notification.__subclasses__():
            notifications[cls.note_type] = []

        # Short-circuit early if this UserData doesn't have notifications.
        # Saves an unnecessary (and otherwise common) roundtrip.
        if not user_data or not user_data.has_notification:
            return notifications

        group = user_models.UserNotificationGroup.get_for_user_data(user_data)

        if not group.notifications:
            return notifications

        modified = False

        # Copy the UserNotificationGroup's notifications into our target
        # notifications object, and remove (pop) any notifications that are not
        # persistent.
        for key in group.notifications:

            notifications[key] = group.notifications[key]

            # If there are notifications of a non-persistent type, we can now
            # pop them off of the UserNotificationGroup's saved list of
            # notifications.
            if (len(notifications[key]) > 0 and 
                    not notifications[key][0].persistent):

                group.notifications[key] = []
                modified = True

        # If any notifications were removed during the pop, update
        # UserNotificationGroup so they won't show up again.
        if modified:
            user_data.has_notification = group.has_notification
            db.put([group, user_data])

        return notifications

    @staticmethod
    def push(user_data, notification):
        """Push a notification onto the specified user's notification queue.

        Note: This will not call .put() on user_data. This will need to be done
        by the caller of this function for user_data's has_notification
        property to be updated properly. We don't call put for performance
        reasons -- the caller will almost always be also calling put on its own
        if a notification is being pushed.
        
        Args:
            user_data: The user_data receiving the notification
            notification: Instance of a subclass of Notification
        """
        group = user_models.UserNotificationGroup.get_for_user_data(user_data)

        notifications = group.notifications or {}

        # Get the user's current list of queued notifications of the target
        # notification's type...
        notes_of_type = notifications.get(notification.note_type, [])

        # ...append the current notification...
        notes_of_type.append(notification)

        # ...and keep the list size limited appropriately according to this
        # notification's type.
        notes_of_type = notes_of_type[-notification.limit:]

        notifications[notification.note_type] = notes_of_type
        group.notifications = notifications
        group.put()

        # Update the user_data's has_notification cached flag. This will need
        # to be .put() somewhere higher in the stack. See docstring note.
        user_data.has_notification = True

    @staticmethod
    def clear(user_data, note_type):
        """Clear notifications of a specific type for the specified user."""
        group = user_models.UserNotificationGroup.get_for_user_data(user_data)
        if group and group.notifications and note_type in group.notifications:
            del group.notifications[note_type]
            group.put()

    @staticmethod
    def clear_all(user_data):
        """Clear all notifications for the specific user."""
        group = user_models.UserNotificationGroup.get_for_user_data(user_data)
        if group:
            group.notifications = {}
            group.put()
