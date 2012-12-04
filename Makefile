SHELL := /bin/bash
SETTINGS := gae_login.mk

VE = ./deploy/env
PATH := ${VE}/bin:tools/google_appengine:${PATH}
PYTHONPATH := ./tools/google_appengine

APPDIR = ./tools/google_appengine
APPCFG = ./$(APPDIR)/appcfg.py
APPDEV = ./$(APPDIR)/dev_appserver.py

COLOR_LIGHT_BLUE = '\e[1;34m'
COLOR_NC = '\e[0m' 

help:
	@echo
	@echo "Some make commands you can run (eg 'make deploy'):"
	@echo
	@echo "MOST USEFUL:"
	@echo "   deploy: create package and upload to the App Engine"
	@echo "   check: run 'small' and 'medium' tests, and linter"
	@echo "   clean: safe remove of auto-generated files (.pyc, virtualenv, etc)"
	@echo "   install_deps: install packages needed for development"
	@echo
	@echo "ALSO USEFUL:"
	@echo "   handlebars/jinja/exercises/js/css/less: used by deploy"
	@echo

deploy: install_deps package_deploy upload_deploy notify

package_deploy:
	@PYTHONPATH=${PYTHONPATH} python deploy/deploy.py

#NOTIFY := `which notify-send`

notify: 
#ifneq ($(wildcard $(NOTIFY)),) 
#	@notify-send "Depoyment complete!" 
#else
#    @echo "bla"
#endif

-include $(SETTINGS)

CONFIGFILE:=app.yaml

read_version:
	@echo `sed '/^ *#/d;s/:/ /;' < "$(CONFIGFILE)" | while read key val; \
	do \
		if [ "$$key" == "version" ]; then \
			VERSION=$$val; \
			export VERSION; \
			echo "Current app.yaml version: $$val"; \
			break; \
		fi \
	done` 

upload_deploy: read_version
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
		echo -e "PASS=$${PASS}\nEMAIL=$${EMAIL}" > ${SETTINGS}; \
		echo "Uploading version ..."; \
		echo $${PASS} | python $(APPCFG) --passin -e $${EMAIL} update . ; \
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

# Install dependencies required for development.c
create_env:
	@if [ ! -d $(VE) ]; \
	then \
		echo "Creating virtual environment in $(VE)..."; \
		virtualenv $(VE); \
		echo "Done."; \
	else \
		echo "Existing virtual environment in $(VE)."; \
	fi

install_deps: create_env
	@echo "Initialize and update Git submodules..."
	@git submodule init
	@git submodule update
	@echo "Done."

	@echo "Installing PIP packages..."
	@source deploy/env/bin/activate
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

run-local: install_deps
	python $(APPDEV) --high_replication --use_sqlite --allow_skipped_files --datastore_path=testutil/test_db.sqlite . 

clear-local:
	rm testutil/test_db.sqlite
	python $(APPDEV) --high_replication --use_sqlite --allow_skipped_files --datastore_path=testutil/test_db.sqlite . 

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

