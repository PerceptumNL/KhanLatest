help:
	@echo "Some make commands you can run (eg 'make allclean'):"
	@echo
	@echo "MOST USEFUL:"
	@echo "   check: run 'small' and 'medium' tests, and linter"
	@echo "   clean: safe remove of auto-generated files (.pyc, etc)"
	@echo "   refresh: safeupdate + install_deps: can be run in cron!"
	@echo "   secrets_decrypt: to create secrets.py"
	@echo
	@echo "ALSO USEFUL:"
	@echo "   allcheck: run all tests (including 'large') and linter"
	@echo "   allclean: remove all non-source-controlled files"
	@echo "   handlebars/jinja/exercises/js/css/less: used by deploy"
	@echo "   install_deps: install packages needed for development"
	@echo "   lint: run lint checks over the entire source tree"
	@echo "   quickcheck: run 'small' tests and linter"
	@echo "   safeupdate: hg pull && hg update -c"
	@echo "   secrets_encrypt: to update secrets.py.cast5"
	@echo "   test: run 'small' and 'medium' tests, but no linter"

# Not as thorough as 'make allclean', but a lot safer.  Feel free to
# add stuff here as you notice it not getting cleaned properly.
# TODO(csilvers): move all generated files into their own directory.
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


# Run hg purge & git clean, but exclude secrets and other dev env files
# Requires Mercurial PurgeExtension. Add to your .hgrc it not installed:
#   [extensions]
#   hgext.purge=
# Note that this is dangerous! -- if you have new files that haven't
# been 'hg add'ed yet, this command will nuke them!
allclean:
	hg purge --all \
	   --exclude 'secrets*.py' \
	   --exclude '.tags*' \
	   --exclude 'deploy/node_modules'
	cd khan-exercises && git clean -xdf

# Install dependencies required for development.
install_deps:
	pip install -r requirements.txt

# Attempt to update (abort if uncommitted changes found).
safeupdate:
	hg pull
	hg update -c

# Update to the latest source and installed dependencies.
# Run this as a cron job to keep your source tree up-to-date.
refresh: safeupdate install_deps ;

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
