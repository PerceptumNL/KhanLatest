#!/usr/bin/env python

from env_setup import setup_django
setup_django()

from django import forms

from agar.django.decorators import validate_service
from agar.django.forms import StrictRequestForm
from agar.json import MultiPageHandler
from agar.json import config as agar_json_config

from restler import serializers

from webapp2 import WSGIApplication, Route

from tests.models import Model1


V1_SERVICE_STRATEGY = serializers.ModelStrategy(Model1)
V1_SERVICE_STRATEGY = V1_SERVICE_STRATEGY + ['string', 'boolean', 'phonenumber']
V2_SERVICE_STRATEGY = V1_SERVICE_STRATEGY - ["boolean", "phonenumber"]


def create_sample_data(page_size=agar_json_config.DEFAULT_PAGE_SIZE):
    count = Model1.all().count()
    while count < page_size + 1:
        model1 = Model1(string='test entry %s'% count)
        model1.put()
        count += 1

class V1ApiForm(StrictRequestForm):
    page_size = forms.IntegerField(required=False, min_value=1, max_value=agar_json_config.MAX_PAGE_SIZE)

    def clean_page_size(self):
        return self.cleaned_data['page_size'] or agar_json_config.DEFAULT_PAGE_SIZE

class V1ApiHandlerService(MultiPageHandler):
    @validate_service(V1ApiForm)
    def get(self):
        form_data = self.request.form.cleaned_data
        page_size = form_data['page_size']
        create_sample_data(page_size)
        return self.json_response(self.fetch_page(Model1.all()), V1_SERVICE_STRATEGY)

class V2ApiHandlerService(MultiPageHandler):
    def get(self):
        create_sample_data()
        return self.json_response(self.fetch_page(Model1.all()), V2_SERVICE_STRATEGY)

# Application
def get_application():
    from agar.env import on_production_server
    return WSGIApplication(
        [
            Route('/api/v1/model1', V1ApiHandlerService, name='api-v1'),
            Route('/api/v2/model1', V2ApiHandlerService, name='api-v2')
        ],
        debug=not on_production_server
    )
application = get_application()

def main():
    from google.appengine.ext.webapp import util
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
