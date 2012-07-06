.. _agar:

====
agar
====
.. automodule:: agar

---------
agar.auth
---------
.. automodule:: agar.auth
    :members: authenticate_abort_403, authentication_required, https_authentication_required, AuthConfig

-----------
agar.config
-----------
.. automodule:: agar.config
.. autoclass:: agar.config.Config
    :members: _prefix, get_config, get_config_as_dict

------------
agar.counter
------------
.. automodule:: agar.counter
.. autoclass:: agar.counter.WriteBehindCounter()
    :members:
    :exclude-members: count
.. autoclass:: agar.counter.TimedWriteBehindCounter()
    :members:
    :exclude-members: normalize_ts, get_ts_name, count, timestamp
.. autoclass:: agar.counter.HourlyWriteBehindCounter()
    :members: get_value, flush_counter, incr
    :exclude-members: normalize_ts, get_ts_name, count, timestamp
.. autoclass:: agar.counter.DailyWriteBehindCounter()
    :members: get_value, flush_counter, incr
    :exclude-members: normalize_ts, get_ts_name, count, timestamp

----------
agar.dates
----------
.. automodule:: agar.dates
    :members:

-----------
agar.django
-----------
.. automodule:: agar.django

^^^^^^^^^^^^^^^^^^^^^^
agar.django.decorators
^^^^^^^^^^^^^^^^^^^^^^
.. automodule:: agar.django.decorators
    :members:

^^^^^^^^^^^^^^^^^
agar.django.forms
^^^^^^^^^^^^^^^^^
.. automodule:: agar.django.forms
    :members:

^^^^^^^^^^^^^^^^^^^^^
agar.django.templates
^^^^^^^^^^^^^^^^^^^^^
.. automodule:: agar.django.templates
    :members:

^^^^^^^^^^^^^^^^^^^^^^^^
agar.django.templatetags
^^^^^^^^^^^^^^^^^^^^^^^^
.. automodule:: agar.django.templatetags

.. autofunction:: agar.django.templatetags.uri_for
.. autofunction:: agar.django.templatetags.on_production_server
.. autofunction:: agar.django.templatetags.create_logout_url
.. autofunction:: agar.django.templatetags.create_login_url

--------
agar.env
--------
.. automodule:: agar.env
    :members:

----------
agar.image
----------
.. automodule:: agar.image
.. autoclass:: agar.image.Image()
    :members:
    :exclude-members: create, get, get_or_insert, gql, all, dynamic_properties, entity_type, fields, from_entity, get_by_id, get_by_key_name, has_key, instance_properties, is_saved, key, kind, parent, parent_key, properties, put, save, to_xml
    :inherited-members:

    .. automethod:: create(blob_info=None, data=None, filename=None, url=None, mime_type=None, parent=None, key_name=None)

.. autoclass:: agar.image.NdbImage()
    :members:
    :exclude-members: create, allocate_ids, get_by_id, get_or_insert, to_dict, allocate_ids_async, create_new_entity, get_by_id_async, get_or_insert_async, populate, put, put_async, query
    :inherited-members:

    .. automethod:: create(blob_info=None, data=None, filename=None, url=None, mime_type=None, parent=None, key_name=None)

.. autoclass:: agar.image.ImageConfig
    :members:

---------
agar.json
---------
.. autoclass:: agar.json.JsonRequestHandler
    :members:
    :undoc-members:

.. autoclass:: agar.json.MultiPageHandler
    :members:
    :undoc-members:

.. autoclass:: agar.json.CorsMultiPageHandler
    :members:

-----------
agar.models
-----------
.. automodule:: agar.models

.. autoclass:: agar.models.NamedModel
    :members:
    :exclude-members: create_new_entity

    .. automethod:: create_new_entity(key_name=None, parent=None, \*\*kwargs)

.. autoclass:: DuplicateKeyError
.. autoclass:: ModelException

-------------
agar.sessions
-------------
.. automodule:: agar.sessions
    :members:

---------
agar.test
---------

.. automodule:: agar.test

.. autoclass:: agar.test.BaseTest
    :members:

.. autoclass:: agar.test.MockUrlfetchTest
    :members:

.. autoclass:: agar.test.WebTest
    :members:

--------
agar.url
--------
.. automodule:: agar.url

.. autofunction:: agar.url.uri_for

.. autoclass:: agar.url.UrlConfig
    :members:

.. Links

.. _Google App Engine python: http://code.google.com/appengine/docs/python/overview.html
.. _Key: http://code.google.com/appengine/docs/python/datastore/keyclass.html
.. _key().name(): http://code.google.com/appengine/docs/python/datastore/keyclass.html#Key_name
.. _Model: http://code.google.com/appengine/docs/python/datastore/modelclass.html
.. _Query: http://code.google.com/appengine/docs/python/datastore/queryclass.html
.. _Blobstore: http://code.google.com/appengine/docs/python/blobstore/
.. _BlobInfo: http://code.google.com/appengine/docs/python/blobstore/blobinfoclass.html
.. _BlobKey: http://code.google.com/appengine/docs/python/blobstore/blobkeyclass.html
.. _BlobReader: http://code.google.com/appengine/docs/python/blobstore/blobreaderclass.html
.. _Image: http://code.google.com/appengine/docs/python/images/imageclass.html
.. _Image.format: http://code.google.com/appengine/docs/python/images/imageclass.html#Image_format
.. _Image.width: http://code.google.com/appengine/docs/python/images/imageclass.html#Image_width
.. _Image.height: http://code.google.com/appengine/docs/python/images/imageclass.html#Image_height
.. _Image.get_serving_url: http://code.google.com/appengine/docs/python/images/functions.html#Image_get_serving_url
.. _google.appengine.api.lib_config: http://code.google.com/p/googleappengine/source/browse/trunk/python/google/appengine/api/lib_config.py
.. _users.get_current_user: http://code.google.com/appengine/docs/python/users/functions.html

.. _django: http://www.djangoproject.com/
.. _django forms: http://docs.djangoproject.com/en/dev/topics/forms/
.. _django form class: http://docs.djangoproject.com/en/1.3/ref/forms/api/#django.forms.Form
.. _django template tags: http://docs.djangoproject.com/en/dev/howto/custom-template-tags/

.. _webapp2: http://code.google.com/p/webapp-improved/
.. _webapp2 configuration: http://webapp-improved.appspot.com/guide/app.html#guide-app-config
.. _webapp2 extras: http://webapp-improved.appspot.com/#api-reference-webapp2-extras
.. _webapp2_extras.sessions: http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html
.. _webapp2_extras.sessions.SessionStore: http://webapp-improved.appspot.com/api/webapp2_extras/sessions.html#webapp2_extras.sessions.SessionStore
.. _webapp2.WSGIApplication: http://webapp-improved.appspot.com/api/webapp2.html#webapp2.WSGIApplication
.. _webapp2.Request: http://webapp-improved.appspot.com/api/webapp2.html#webapp2.Request
.. _webapp2.Response: http://webapp-improved.appspot.com/api/webapp2.html#webapp2.Response
.. _webapp2.RequestHandler: http://webapp-improved.appspot.com/api/webapp2.html#webapp2.RequestHandler
.. _webapp2.RequestHandler.abort: http://webapp-improved.appspot.com/api/webapp2.html#webapp2.RequestHandler.abort
.. _webapp2.uri_for: http://webapp-improved.appspot.com/api/webapp2.html#webapp2.uri_for
.. _webapp2.abort: http://webapp-improved.appspot.com/api/webapp2.html#webapp2.abort

.. _uuid4: http://docs.python.org/library/uuid.html#uuid.uuid4

.. _mime type: http://en.wikipedia.org/wiki/Internet_media_type

.. _WebTest: http://webtest.pythonpaste.org/
.. _gaetestbed: http://github.com/jgeewax/gaetestbed
.. _testbed: http://code.google.com/appengine/docs/python/tools/localunittesting.html
.. _images: http://code.google.com/appengine/docs/python/images/
.. _PIL: http://www.pythonware.com/products/pil/
.. _urlfetch: http://code.google.com/appengine/docs/python/urlfetch/
.. _Task: http://code.google.com/appengine/docs/python/taskqueue/tasks.html#Task
.. _User: http://code.google.com/appengine/docs/python/users/userclass.html
