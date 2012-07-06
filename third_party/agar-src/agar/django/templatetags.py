"""
The ``agar.templatetags.webapp2`` module contains `django template tags`_.
"""

from django.template import Node, TemplateSyntaxError

from google.appengine.ext.webapp import template

# Get the template Library
register = template.create_template_register()


class URLNode(Node):
    def __init__(self, route_name, args, kwargs, asvar):
        self.route_name = route_name
        self.args = args
        self.kwargs = kwargs
        self.asvar = asvar

    def render(self, context):
        args = [arg.resolve(context) for arg in self.args]
        kwargs = dict([(str(k), v.resolve(context))
                       for k, v in self.kwargs.items()])
        url = None
        try:
            from agar.url import uri_for
            url = uri_for(self.route_name, *args, **kwargs)
        except Exception, e:
            if self.asvar is None:
                raise e
        url = url or ''
        if self.asvar:
            context[self.asvar] = url
            return ''
        else:
            return url


@register.tag(name='uri_for')
def uri_for(parser, token):
    """
    Returns a URL matching given the route name with its parameters.

    See :py:func:`~agar.url.uri_for` for more detailed parameter information.

    For example::

        {% uri_for route_name arg1,arg2,name1=value1 %}

        {% uri_for get_client id=client.id %}

        {% uri_for get_client id=client.id,_full=True %}
    """
    bits = token.split_contents()
    if len(bits) < 2:
        raise TemplateSyntaxError("'%s' takes at least one argument"
                                  " (route name)" % bits[0])
    routename = bits[1]
    args = []
    kwargs = {}
    asvar = None

    if len(bits) > 2:
        bits = iter(bits[2:])
        for bit in bits:
            if bit == 'as':
                asvar = bits.next()
                break
            else:
                for arg in bit.split(","):
                    if '=' in arg:
                        k, v = arg.split('=', 1)
                        k = k.strip()
                        kwargs[k] = parser.compile_filter(v)
                    elif arg:
                        args.append(parser.compile_filter(arg))
    return URLNode(routename, args, kwargs, asvar)


@register.tag(name='on_production_server')
def on_production_server():
    """
    Returns whether the code is running on a production server. See :py:func:`~agar.env.on_production_server` for
    more information.

    For example::

        {% if on_production_server %}
            <do something>
        {% endif %}
    """
    from agar.env import on_production_server
    return on_production_server


class LogoutURLNode(Node):
    def __init__(self, logout_url):
        self.logout_url = logout_url

    def render(self, context):
        from google.appengine.api.users import create_logout_url
        return create_logout_url(self.logout_url)


@register.tag(name='create_logout_url')
def create_logout_url(parser, token):
    """
    Creates a Google Account logout url and callback to a route_name.

    For example::

        {% create_logout_url route_name %}
    """
    try:
        tag_name, dest_url = token.split_contents()
    except ValueError:
        raise TemplateSyntaxError("%r tag requires a single argument" % token.contents.split()[0])
    return LogoutURLNode(dest_url)


class LoginURLNode(Node):
    def __init__(self, login_url):
        self.login_url = login_url

    def render(self, context):
        from google.appengine.api.users import create_login_url
        return create_login_url(self.login_url)


@register.tag(name='create_login_url')
def create_login_url(parser, token):
    """
    Creates a Google Account login url and callback to a route_name.

    For example::

        {% create_login_url route_name %}
    """
    try:
        tag_name, dest_url = token.split_contents()
    except ValueError:
        raise TemplateSyntaxError("%r tag requires a single argument" % token.contents.split()[0])
    return LoginURLNode(dest_url)
