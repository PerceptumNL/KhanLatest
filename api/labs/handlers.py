#!/usr/bin/env python

from third_party.flask import request

from api.route_decorator import route
from api.api_util import api_invalid_param_response
from api.api_util import api_forbidden_response
from api.api_util import api_not_found_response
from api.api_util import api_success_no_content_response
from api.auth.decorators import login_required
from api.auth.decorators import open_access
from api.decorators import jsonify, jsonp
from api.v1 import get_visible_user_data_from_request

import gandalf.bridge

from google.appengine.ext import db

import scratchpads.models as scratchpad_models
from user_models import UserData

# TODO(jlfwong): Have API endpoint for retrieving an arbitrary scratchpad
# revision, not just the latest


@route("/api/labs/scratchpads/<int:scratchpad_id>", methods=["GET"])
@open_access
@jsonp
@jsonify
def get_scratchpad(scratchpad_id):
    scratchpad = scratchpad_models.Scratchpad.get_by_id(scratchpad_id)
    if scratchpad:
        return scratchpad
    else:
        return api_not_found_response(
            "No scratchpad with id %s" % scratchpad_id)


def dict_keys_to_strings(d):
    """Convert the keys of the provided dict to be strings.

    This is especially useful for converting request.json's keys to be regular
    strings instead of unicode strings so that they can be unpacked as **kwargs
    to functions.
    """
    return dict((str(k), v) for (k, v) in d.iteritems())


@route("/api/labs/scratchpads", methods=["POST"])
@open_access
@jsonp
@jsonify
def create_scratchpad():
    """Create a new Scratchpad and associated ScratchpadRevision.

    The POST data should be a JSON-encoded dict, which is passed verbatim to
    Scratchpad.create as keyword arguments.
    """
    if not gandalf.bridge.gandalf("scratchpads"):
        return api_forbidden_response(
            "Forbidden: You don't have permission to do this")

    if not request.json:
        return api_invalid_param_response("Bad data supplied: Not JSON")

    # TODO(jlfwong): Support phantom users
    user = UserData.current()

    if not (user and user.developer):
        # Certain fields are only modifiable by developers
        for field in scratchpad_models.Scratchpad._developer_only_fields:
            if request.json.get(field):
                return api_forbidden_response(
                    "Forbidden: Only developers can change the %s" % field)

    try:
        # Convert unicode encoded JSON keys to strings
        create_args = dict_keys_to_strings(request.json)
        if user:
            create_args['user_id'] = user.user_id
        return scratchpad_models.Scratchpad.create(**create_args)
    except (db.BadValueError, db.BadKeyError), e:
        return api_invalid_param_response("Bad data supplied: " + e.message)


@route("/api/labs/scratchpads/<int:scratchpad_id>", methods=["PUT"])
@login_required
@jsonp
@jsonify
def update_scratchpad(scratchpad_id):
    """Update a pre-existing Scratchpad and create a new ScratchpadRevision.

    The POST data should be a JSON-encoded dict, which is passsed verbatim to
    Scratchpad.update as keyword arguments.
    """
    if not gandalf.bridge.gandalf("scratchpads"):
        return api_forbidden_response(
            "Forbidden: You don't have permission to do this")

    if not request.json:
        return api_invalid_param_response("Bad data supplied: Not JSON")

    user = UserData.current()
    scratchpad = scratchpad_models.Scratchpad.get_by_id(scratchpad_id)

    if not scratchpad or scratchpad.deleted:
        return api_not_found_response(
            "No scratchpad with id %s" % scratchpad_id)

    if not user.developer:
        # Certain fields are only modifiable by developers
        for field in scratchpad_models.Scratchpad._developer_only_fields:
            if request.json.get(field):
                return api_forbidden_response(
                    "Forbidden: Only developers can change the %s" % field)

    # The user can update the scratchpad if any of the following are true:
    #  1. The scratchpad is tutorial/official and the user is a developer
    #  2. The scratchpad was created by the user
    if scratchpad.category in ("tutorial", "official") and user.developer:
        pass
    elif scratchpad.user_id != user.user_id:
        # Only the creator of a scratchpad can update it
        return api_forbidden_response(
            "Forbidden: Scratchpad owned by different user")

    try:
        # Convert unicode encoded JSON keys to strings
        update_args = dict_keys_to_strings(request.json)
        if 'id' in update_args:
            # Backbone passes the id in update calls - ignore it
            del update_args['id']
        return scratchpad.update(**update_args)
    except (db.BadValueError, db.BadKeyError), e:
        return api_invalid_param_response("Bad data supplied: " + e.message)


@route("/api/labs/scratchpads/<int:scratchpad_id>", methods=["DELETE"])
@login_required
@jsonp
def delete_scratchpad(scratchpad_id):
    """Mark a pre-existing Scratchpad as deleted.

    An empty request body is expected."""

    if not gandalf.bridge.gandalf("scratchpads"):
        return api_forbidden_response(
            "Forbidden: You don't have permission to do this")

    user = UserData.current()
    scratchpad = scratchpad_models.Scratchpad.get_by_id(scratchpad_id)

    if not scratchpad or scratchpad.deleted:
        return api_not_found_response(
            "No scratchpad with id %s" % scratchpad_id)

    # Users can only delete scratchpad they created
    # EXCEPTION: Developres can delete any scratchpad
    if not user.developer and scratchpad.user_id != user.user_id:
        return api_forbidden_response(
            "Forbidden: Scratchpad owned by different user")

    scratchpad.deleted = True
    scratchpad.put()

    return api_success_no_content_response()


@route("/api/labs/user/scratchpads", methods=["GET"])
@open_access
@jsonp
@jsonify
def get_user_scratchpads():
    if not gandalf.bridge.gandalf("scratchpads"):
        return api_forbidden_response(
            "Forbidden: You don't have permission to do this")

    user_data = (get_visible_user_data_from_request() or
                 UserData.pre_phantom())
    return list(scratchpad_models.Scratchpad
        .get_for_user_data(user_data)
        .run(batch_size=1000))
