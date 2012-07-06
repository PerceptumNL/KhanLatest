from webob import Request
from agar.test import BaseTest, WebTest

import main


class TestWebTest(BaseTest, WebTest):

    APPLICATION = main.application

    def test_get(self):
        response = self.get("/")
        self.assertOK(response)

    def test_delete(self):
        response = self.delete("/")
        self.assertEqual(405, response.status_int)

    def test_assertUnauthorized(self):
        request = Request.blank("/")
        request.status_int = 401

        self.assertUnauthorized(request)

    def test_assertUnauthorized_challenge(self):
        request = Request.blank("/")
        request.status_int = 401
        request.headers['WWW-Authenticate'] = "hello world"

        self.assertUnauthorized(request, challenge='hello world')

    def test_assertBadRequest(self):
        request = Request.blank("/")
        request.status_int = 400

        self.assertBadRequest(request)

