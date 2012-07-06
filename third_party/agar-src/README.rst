agar
====

Agar is a set of utilities for `Google App Engine python`_, , created as part of the `Substrate Project`_.

Resources
---------

* `Documentation`_
* `PyPI Package`_
* `Source Code Repository`_

Requirements
------------

Agar requires the Google App Engine SDK, `webapp2`_, `webapp2_extras`_,
`pytz`_, `restler`_, and `basin`_. Versions of these (except the Google App
Engine SDK) are located in the ``lib`` directory.

Installation
------------

To install Agar, download the source and add the ``agar`` directory to
your Google App Engine project. It must be on your path.

Tests
-----

Agar comes with a set of tests. Running Agar's tests requires
`unittest2`_ and `WebTest`_ (included in the ``lib`` directory). To run them,
execute::

     $ ./run_tests.py

Testing
-------

Google App Engine now includes testbed to make local unit testing
easier. This obsoletes the now-unsupported GAE TestBed
library. However, it had several useful helper functions, many of
which have been re-implemented in Agar. To use them, you must use
`unittest2`_ and inherit from `agar.tests.BaseTest`_ or `agar.tests.WebTest`_.

License
-------

Agar is licensed under the MIT License. See ``LICENSE.txt`` for details.

Contributing
------------

To contribute to the Agar project, fork the repository, make your
changes, and submit a pull request.

.. Links

.. _Substrate Project: http://pypi.python.org/pypi/substrate

.. _Documentation: http://packages.python.org/agar
.. _PyPI Package: http://pypi.python.org/pypi/agar
.. _Source Code Repository: http://bitbucket.org/gumptioncom/agar

.. _Google App Engine python: http://code.google.com/appengine/docs/python/overview.html
.. _webapp2: http://code.google.com/p/webapp-improved/
.. _webapp2_extras: http://webapp-improved.appspot.com/#api-reference-webapp2-extras
.. _pytz: http://pytz.sourceforge.net/
.. _basin: http://pypi.python.org/pypi/basin
.. _unittest2: http://pypi.python.org/pypi/unittest2
.. _WebTest: http://webtest.pythonpaste.org/
.. _restler: http://packages.python.org/substrate/restler.html

.. _agar.tests.BaseTest: http://packages.python.org/agar/agar.html#agar.test.BaseTest
.. _agar.tests.WebTest: http://packages.python.org/agar/agar.html#agar.test.WebTest
