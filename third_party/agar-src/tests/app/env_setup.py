
def setup_django(settings='settings', version='1.2', ):
    """
    Sets up the django libraries.

    :param settings: The name of the settings file. Default: ``'settings'``.
    :param version: The django version to set up. Default: ``'1.2'``.
    """
    import os
    os.environ['DJANGO_SETTINGS_MODULE'] = settings
    from google.appengine.dist import use_library
    use_library('django', version)
    from django.conf import settings
    _ = settings.TEMPLATE_DIRS
