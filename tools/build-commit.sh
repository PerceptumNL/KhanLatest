#!/bin/bash

# This script is intended to be run by the Jenkins CI server at the
# root of a workspace where the website code is checked out into a
# subdirectory.

: ${BASE_PYTHON:=python}
: ${MAKE:=make}
: ${VIRTUALENV:=/usr/local/bin/virtualenv}
# python and pip are available, thanks to the virtualenv

: ${APPENGINE_ROOT:=/usr/local/google_appengine}
: ${VIRTUALENV_ROOT:=env}
: ${WEBSITE_ROOT:=website}

# Set up the environment for subprocesses

export PATH="env/bin:$PATH:$APPENGINE_ROOT"

# Set up a virtualenv with the necessary packages

if [ -d "$VIRTUALENV_ROOT" ]; then
    echo "Virtualenv already exists"
else
    echo "Creating new virtualenv"
    "$VIRTUALENV" --python="$BASE_PYTHON" --no-site-packages "$VIRTUALENV_ROOT"
fi

source "$VIRTUALENV_ROOT/bin/activate"
pip install -r "$WEBSITE_ROOT/requirements.txt"

# Run commit build verifications

cd "$WEBSITE_ROOT"
"$MAKE" check COVERAGE=1 MAX_TEST_SIZE=large
