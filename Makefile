-include gae_login.mk
SHELL := /bin/bash

VE = ./deploy/env

PATH := ${VE}/bin:tools/google_appengine:${PATH}
PYTHONPATH := ./tools/google_appengine

APPDIR = ./tools/google_appengine
APPCFG = ./$(APPDIR)/appcfg.py
APPDEV = ./$(APPDIR)/dev_appserver.py

COLOR_LIGHT_BLUE = '\e[1;34m'
COLOR_NC = '\e[0m' #

help:
	@echo
	@echo "Some make commands you can run (eg 'make deploy'):"
	@echo
	@echo "MOST USEFUL:"
	@echo "   deploy: create package and upload to the App Engine"
#	@echo "   check: run 'small' and 'medium' tests, and linter"
	@echo "   clean: safe remove of auto-generated files (.pyc, virtualenv, etc)"
	@echo "   install_deps: install packages needed for development"
	@echo
	@echo "ALSO USEFUL:"
	@echo "   handlebars/jinja/exercises/js/css/less: used by deploy"
	@echo
#	@echo "   allcheck: run all tests (including 'large') and linter"
#	@echo "   allclean: remove all non-source-controlled files"
#	@echo "   lint: run lint checks over the entire source tree"
#	@echo "   quickcheck: run 'small' tests and linter"
#	@echo "   safeupdate: hg pull && hg update -c"
#	@echo "   secrets_encrypt: to update secrets.py.cast5"
#	@echo "   test: run 'small' and 'medium' tests, but no linter"

deploy: install_deps package_deploy upload_deploy
	@if [ $? -eq 1 ];then \
		notify-send "Depoyment complete!" \
	fi

package_deploy:
	@PYTHONPATH=${PYTHONPATH} python deploy/deploy.py

upload_deploy:
	@if [ -z $(PASS) ] | [ -z $(EMAIL) ]; \
	then \
		echo "Please proceed to enter the user/pass"; \
		read -p "User email: " EMAIL; \
		if [ -z $${EMAIL} ]; \
		then \
		    echo "Email empty"; \
		    exit 1; \
		fi; \
		read -p "Password: " PASS; \
		if [ -z $${PASS} ]; \
		then \
		    echo "Password empty"; \
		    exit 1; \
		fi; \
		echo -e "PASS=$${PASS}\nEMAIL=$${EMAIL}" > credentials.mk; \
		echo "Uploading version ..."; \
		echo $${PASS} | python $${APPCFG} --passin -e $${EMAIL} update . ; \
	else \
		echo "Uploading version ..."; \
		echo $(PASS) | python $(APPCFG) --passin -e $(EMAIL) update . ; \
	fi
	
# Not as thorough as 'make allclean', but a lot safer.  Feel free to
# add stuff here as you notice it not getting cleaned properly.
clean:
	find . \( -name '*.pyc' -o -name '*.pyo' \
	    -o -name '*.orig' \
	    -o -name 'combined.js' \
	    -o -name 'combined.css' \
	    -o -name 'compressed.js' \
	    -o -name 'compressed.css' \
	    -o -name 'hashed-*.js' \
	    -o -name 'hashed-*.css' \
	    -o -name '*.handlebars.js' \
	    -o -name 'compiled_templates' \
	    -o -name 'node_modules' \
            \) -print0 | xargs -0 rm -rf
	rm -rf $(VE)
	rm -rf $(APPDIR)

# Install dependencies required for development.
VE:
VE-install: VE
	@which virtualenv > /dev/null
	@if test -d ; \
	then \
		echo "Found 'virtualenv'"; \
	else \
		echo "Please install virtualenv"; \
		echo " easy_install virtualenv"; \
	fi

VE-prepare: VE-install
	@$(ls $(VE) > /dev/null)
	@if [ -d $(VE) ]; \
    then \
		echo "Existing virtual environment in $(VE)"; \
    else \
		echo "Creating new virtual environment in $(VE)"; \
		virtualenv $(VE); \
    fi

install_deps: VE-prepare
	@echo "Initialize and update Git submodules..."
	@git submodule init
	@git submodule update
	@echo "Done."
	@echo "Installing PIP packages..."
	@pip install -r deploy/requirements.txt --exists-action=i
	@echo "Done."
	@if [ ! -d $(APPDIR) ]; \
	then \
		echo "Downloading the Google App Engine..."; \
		python tools/appengine_download.py tools/; \
		echo "Done."; \
	else \
		echo "Existing Google AppEngine in $(APPDIR)"; \
	fi

run-local:
	python $(APPDEV) --high_replication --use_sqlite --allow_skipped_files --datastore_path=testutil/test_db2.sqlite . 

# Run tests.  If COVERAGE is set, run them in coverage mode.  If
# MAX_TEST_SIZE is set, only tests of this size or smaller are run.
MAX_TEST_SIZE = medium
COVERAGE_OMIT = *_test.py
COVERAGE_OMIT += */google_appengine/*
COVERAGE_OMIT += third_party/*
COVERAGE_OMIT += gae_bingo/*
COVERAGE_OMIT += gae_mini_profiler/*
COVERAGE_OMIT += pymeta_grammar__*
COVERAGE_OMIT += tools/*
test:
	if test -n "$(COVERAGE)"; then  \
	   coverage run --omit="`echo '$(COVERAGE_OMIT)' | tr ' ' ,`" \
	      tools/runtests.py --max-size="$(MAX_TEST_SIZE)" --xml && \
	   coverage xml && \
	   coverage html; \
	else \
	   python tools/runtests.py --max-size="$(MAX_TEST_SIZE)"; \
	fi

# Run lint checks
lint:
	third_party/khan_linter/runlint.py

# Run unit tests with XML test and code coverage reports

# Run the tests we want to run before committing.  Once you've run
# these, you can be confident (well, more confident) the commit is a
# good idea.
check: lint test ;

# Run the subset of tests that are fast
quickcheck:
	$(MAKE) MAX_TEST_SIZE=small check

# Run *all* the tests
allcheck:
	$(MAKE) MAX_TEST_SIZE=large check

# Compile handlebars templates
handlebars:
	python deploy/compile_handlebar_templates.py

# Compile jinja templates
jinja:
	python deploy/compile_templates.py

# Pack exercise files
exercises:
	ruby khan-exercises/build/pack.rb

# Compress javascript
js:
	python deploy/compress.py js

# Compress css
css:
	python deploy/compress.py css

# Package less stylesheets
less:
	python deploy/compile_less.py

# 'private' task for echoing instructions
_pwd_prompt:
	@echo "Get the password from here:"
	@echo "https://www.dropbox.com/home/Khan%20Academy%20All%20Staff/Secrets"

# to create secrets.py
secrets_decrypt: _pwd_prompt
	openssl cast5-cbc -d -in secrets.py.cast5 -out secrets.py && chmod 600 secrets.py

# for updating secrets.py
secrets_encrypt: _pwd_prompt
	openssl cast5-cbc -e -in secrets.py -out secrets.py.cast5

# aliases for the sake of remembering word order
decrypt_secrets: secrets_decrypt ;
encrypt_secrets: secrets_encrypt ;

