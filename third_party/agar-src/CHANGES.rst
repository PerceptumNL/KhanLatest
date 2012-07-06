Changes
-------
* **0.6** -- 2012-01-01

  * Removed alias for agar.url_for, use agar.uri_for

  * Removed templatetag for url_for, use uri_for
  
  * Moved agar.templatetags.webapp2 to agar.django.templatetags
  
* **0.5.1** -- 2011-11-22

  * `agar.test`_

    * Added `WebTest.assertBadRequest()`_

    * Added optional ``method`` parameter to  `MockUrlfetchTest.set_response()`_

  * `agar.templatetags`_

    * Added `create_logout_url`_
    
* **0.5** -- 2011-11-15

  * `agar.test`_

    * Added optional ``challenge`` parameter to `WebTest.assertUnauthorized()`_.

  * `agar.django.templates`_

    * Added `render_template_to_string()`_.

  * Added `agar.counter`_.

* **0.4** -- 2011-11-08

  * `agar.auth`_

    * **Breaking Changes**

      * The `AuthConfig`_ configuration ``authenticate`` has been renamed to `DEFAULT_AUTHENTICATE_FUNCTION`_.

      * The `authenticate function`_ is now passed the current `RequestHandler`_ rather than the
        `Request`_. The `Request`_ can still be accessed from the `RequestHandler`_ via ``handler.request``.

      * The `authentication_required`_ decorator no longer aborts with status ``403`` when the
        `authenticate function`_ returns ``None``. Instead, the decorator will simply set the `Request`_ ``user``
        attribute (or any configured `AUTHENTICATION_PROPERTY`_) to ``None``. This is useful for handlers where
        authentication is optional. Users can update their `authenticate function`_ to call `handler.abort()`_
        if they wish to keep the previous behavior.

    * Updated `DEFAULT_AUTHENTICATE_FUNCTION`_ to retain ``403`` behavior out of the box.

  * `agar.env`_

    * Use `get_application_id()`_ instead of ``os.environ.get('APPLICATION_ID')``.

  * `agar.image`_

    * Fixed `get_serving_url()`_ caching bug.

  * `agar.test`_

    * Added `BaseTest.get_tasks()`_.

    * Added `BaseTest.assertTasksInQueue()`_.

    * Added `BaseTest.clear_datastore()`_.

    * Added `WebTest.assertUnauthorized()`_.

    * Added `WebTest.put()`_.

    * Added `WebTest.delete()`_.

* **0.2** (First Public Release) -- 2011-10-14

  * Updated docs

* **0.1** (Development Version Only) -- 2011-09-21


.. Links

.. _Request: http://webapp-improved.appspot.com/api/webapp2.html#webapp2.Request
.. _RequestHandler: http://webapp-improved.appspot.com/api/webapp2.html#webapp2.RequestHandler
.. _handler.abort(): http://webapp-improved.appspot.com/api/webapp2.html#webapp2.RequestHandler.abort

.. _agar: http://packages.python.org/agar/agar.html
.. _agar.auth: http://packages.python.org/agar/agar.html#module-agar.auth
.. _agar.env: http://packages.python.org/agar/agar.html#module-agar.env
.. _agar.image: http://packages.python.org/agar/agar.html#module-agar.image
.. _agar.counter: http://packages.python.org/agar/agar.html#module-agar.counter
.. _agar.templatetags: http://packages.python.org/agar/agar.html#module-agar.templatetags
.. _agar.django.templates: http://packages.python.org/agar/agar.html#module-agar.django.templates
.. _render_template_to_string(): http://packages.python.org/agar/agar.html#agar.django.templates.render_template_to_string
.. _create_logout_url: http://packages.python.org/agar/agar.html#agar.templatetags.webapp2.create_logout_url

.. _get_application_id(): http://code.google.com/appengine/docs/python/appidentity/functions.html#get_application_id
.. _get_serving_url(): http://packages.python.org/agar/agar.html#agar.image.Image.get_serving_url

.. _agar.test: http://packages.python.org/agar/agar.html#module-agar.test
.. _AuthConfig: http://packages.python.org/agar/agar.html#agar.auth.AuthConfig
.. _authentication_required: http://packages.python.org/agar/agar.html#agar.auth.authentication_required
.. _authenticate function: http://packages.python.org/agar/agar.html#agar.auth.AuthConfig.authenticate
.. _AUTHENTICATION_PROPERTY: http://packages.python.org/agar/agar.html#agar.auth.AuthConfig.AUTHENTICATION_PROPERTY
.. _DEFAULT_AUTHENTICATE_FUNCTION: http://packages.python.org/agar/agar.html#agar.auth.AuthConfig.DEFAULT_AUTHENTICATE_FUNCTION
.. _BaseTest.clear_datastore(): http://packages.python.org/agar/agar.html#agar.test.BaseTest.clear_datastore
.. _BaseTest.get_tasks(): http://packages.python.org/agar/agar.html#agar.test.BaseTest.get_tasks
.. _BaseTest.assertTasksInQueue(): http://packages.python.org/agar/agar.html#agar.test.BaseTest.assertTasksInQueue
.. _WebTest.assertUnauthorized(): http://packages.python.org/agar/agar.html#agar.test.WebTest.assertUnauthorized
.. _WebTest.assertBadRequest(): http://packages.python.org/agar/agar.html#agar.test.WebTest.assertBadRequest
.. _WebTest.put(): http://packages.python.org/agar/agar.html#agar.test.WebTest.put
.. _WebTest.delete(): http://packages.python.org/agar/agar.html#agar.test.WebTest.delete

.. _MockUrlfetchTest.set_response(): http://packages.python.org/agar/agar.html#agar.test.MockUrlfetchTest.set_response

