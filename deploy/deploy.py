import datetime
import getpass
import optparse
import os
import re
import subprocess
import sys
import threading
import urllib2
import webbrowser

sys.path.append(os.path.abspath("."))
import compress
import npm

try:
    import secrets
    hipchat_deploy_token = secrets.hipchat_deploy_token
    sleep_secret = secrets.sleep_secret
except Exception, e:
    print 'Exception raised by "import secrets". Attempting to continue...'
    print repr(e)
    hipchat_deploy_token = None
    sleep_secret = None

try:
    import secrets_dev
    app_engine_username = getattr(secrets_dev, 'app_engine_username', None)
    app_engine_password = getattr(secrets_dev, 'app_engine_password', None)
except Exception, e:
    app_engine_username, app_engine_password = None, None

if hipchat_deploy_token:
    import hipchat.room
    import hipchat.config
    hipchat.config.manual_init(hipchat_deploy_token)


def popen_results(args):
    proc = subprocess.Popen(args, stdout=subprocess.PIPE)
    return proc.communicate()[0]


def popen_return_code(args, input=None):
    proc = subprocess.Popen(args, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    proc.communicate(input)
    return proc.returncode


def get_app_engine_credentials():
    if app_engine_username and app_engine_password:
        print "Using password for %s from secrets.py" % app_engine_username
        return (app_engine_username, app_engine_password)
    else:
        email = app_engine_username or raw_input("App Engine Email: ")
        password = getpass.getpass("Password for %s: " % email)
        return (email, password)


def send_hipchat_deploy_message(
        last_version, version, includes_local_changes, email, authors):
    """Send a summary of the deploy information to HipChat.

    Arguments:
        version:
            A string indicating the AppEngine version name of the deploy.
        includes_local_changes:
            A bool indicating whether or not the current file system
            is dirty and has changes that aren't checked into source control.
            These changes are included in the deploy.
        email:
            The email of the AppEngine account being used to deploy.
        authors:
            A list of code authors with changesets since the last deploy,
            and are likely to be interested in this deploy.
    """
    if hipchat_deploy_token is None:
        return

    app_id = get_app_id()
    if app_id != "khan-academy":
        # Don't notify hipchat about deployments to test apps
        print ('Skipping hipchat notification as %s looks like a test app' %
               app_id)
        return

    url = "http://%s.%s.appspot.com" % (version, app_id)

    hg_id = hg_version()
    hg_msg = hg_changeset_msg(hg_id.replace('+', ''))
    kiln_url = "https://khanacademy.kilnhg.com/Search?search=%s" % hg_id

    git_id = git_version()
    git_msg = git_revision_msg(git_id)
    github_url = "https://github.com/Khan/khan-exercises/commit/%s" % git_id

    authors_tmpl = ""
    if authors:
        email_to_hipchat = {
            'alpert@khanacademy.org': 'ben',
            'ben@eater.net': 'eater',
            'ben@khanacademy.org': 'kamens',
            'benkomalo@gmail.com': 'benkomalo',
            'csilvers@khanacademy.org': 'craig',
            'dmnd@desmondbrand.com': 'desmond',
            'jeresig@gmail.com': 'john',
            'joelburget@gmail.com': 'joel',
            'jp@julianpulgarin.com': 'julian',
            'sincerelyyourstom@gmail.com': 'tom',
            'subliminal@gmail.com': 'marcos',
            'tallnerd@gmail.com': 'james',
        }

        hipchat_authors = set()
        for author in authors:
            if author in email_to_hipchat:
                hipchat_authors.add('@' + email_to_hipchat[author])
            elif author.endswith('@khanacademy.org'):
                hipchat_authors.add('@' + author[:-len('@khanacademy.org')])
            else:
                hipchat_authors.add(author)

        kiln_range_url = ("https://khanacademy.kilnhg.com/Code/Website/Group/"
                          "stable?rev=%s%%3A%s" % (last_version, hg_id))
        authors_tmpl = ("<br>Devs with <a href='%s'>changesets in this "
                        "deploy</a>:<br> %s" % (
                            kiln_range_url,
                            ", ".join(sorted(hipchat_authors))))

    local_changes_warning = (" (with local changes)" if includes_local_changes
                             else "")
    changeset_id = "%s as " % hg_id if hg_id != version else ""
    message_tmpl = """
            %(changeset_id)sversion <a href='%(url)s'>%(version)s</a>.<br>
            &bull; website changeset: <a
            href='%(kiln_url)s'>%(hg_msg)s</a>%(local_changes_warning)s<br>
            &bull; khan-exercises revision: <a
            href='%(github_url)s'>%(git_msg)s</a>
            """ % {
                "changeset_id": changeset_id,
                "url": url,
                "version": version,
                "hg_id": hg_id,
                "kiln_url": kiln_url,
                "hg_msg": truncate(hg_msg, 60),
                "github_url": github_url,
                "git_msg": truncate(git_msg, 60),
                "local_changes_warning": local_changes_warning,
            }
    deployer_id = email
    if email in ['prod-deploy@khanacademy.org']:  # Check for role-accounts
        real_user = popen_results(['whoami']).strip()
        deployer_id = "%s (%s)" % (email, real_user)
    public_message = "Just deployed %s" % message_tmpl
    private_message = "%s just deployed %s%s" % (deployer_id, message_tmpl,
                                                 authors_tmpl)

    if version == 'khan-labs-test':
        hipchat_message(private_message, ["CS"])
    else:
        hipchat_message(public_message, ["Exercises"])
        hipchat_message(private_message, ["1s and 0s"])


def hipchat_message(msg, rooms):
    if hipchat_deploy_token is None:
        return

    for room in hipchat.room.Room.list():

        if room.name in rooms:

            result = ""
            msg_dict = {
                "room_id": room.room_id,
                "from": "Mr Monkey",
                "message": msg,
                "color": "purple",
            }

            try:
                result = str(hipchat.room.Room.message(**msg_dict))
            except:
                pass

            if "sent" in result:
                print "Notified Hipchat room %s" % room.name
            else:
                print "Failed to send message to Hipchat: %s" % msg


def truncate(s, n):
    if len(s) <= n:
        return s
    else:
        return s[:(n - 3)] + '...'


def get_app_id():
    f = open("app.yaml", "r")
    contents = f.read()
    f.close()

    app_re = re.compile("^application:\s+(.+)$", re.MULTILINE)
    match = app_re.search(contents)

    return match.groups()[0]


def hg_st():
    output = popen_results(['hg', 'st', '-mard', '-S'])
    return len(output) > 0


def hg_pull_up():
    # Pull latest
    popen_results(['hg', 'pull'])

    # Hg up and make sure we didn't hit a merge
    output = popen_results(['hg', 'up'])
    lines = output.split("\n")
    if len(lines) != 2 or lines[0].find("files updated") < 0:
        # Ran into merge or other problem
        return -1

    return dated_hg_version()


def get_changeset_authors(from_hg_version, to_hg_version=None):
    """Retrieve the list of changsets since a given HG version.

    Returns a set of email addresses of all authors with an associated
    changeset in the list.
    """
    if not to_hg_version:
        to_hg_version = 'tip'

    command = "hg log -r %s:%s --template {author}\\n" % (from_hg_version,
                                                           to_hg_version)
    raw_authors = popen_results(command.split(' ')).strip()
    authors = set()

    for author in raw_authors.split('\n'):
        if author.endswith('>'):
            # In the format "Joe Shmoe <email@domain.com>"
            email = re.split('[<>]', author)[1]
        else:
            email = author
        authors.add(email)
    return authors


def dated_hg_version():
    version = hg_version()

    # e.g. "0421" for April 21:
    date_prefix = datetime.date.today().strftime("%m%d")
    return "%s-%s" % (date_prefix, version)


def hg_version():
    # grab the tip changeset hash
    current_version = popen_results(['hg', 'identify', '-i']).strip()
    return current_version or -1


def hg_changeset_msg(changeset_id):
    # grab the summary and date
    output = popen_results(['hg', 'log', '--template', '{desc}',
                            '-r', changeset_id])
    return output.split('\n')[0]


def git_version():
    # grab the tip changeset hash
    return popen_results(['git', '--work-tree=khan-exercises/',
                          '--git-dir=khan-exercises/.git',
                          'rev-parse', 'HEAD']).strip()


def git_revision_msg(revision_id):
    return popen_results(['git', '--work-tree=khan-exercises/',
                          '--git-dir=khan-exercises/.git', 'show', '-s',
                          '--pretty=format:%s', revision_id]).strip()


def check_secrets():
    try:
        import secrets
    except ImportError:
        return False

    if not hasattr(secrets, 'verify_secrets_is_up_to_date'):
        print "Your secrets is too old; update it using the instructions in"
        print "password_for_secrets_py_cast5.txt at:"
        print "  https://www.dropbox.com/home/Khan%20Academy%20All%20Staff/Secrets"
        print
        return False

    fb_secret = getattr(secrets, 'facebook_app_secret', '')
    return fb_secret.startswith('050c')


def check_deps():
    """Check if npm and friends are installed"""
    return npm.check_dependencies()


def delete_orphan_pyc_files(rootdir):
    print "Deleting 'orphan' .pyc files"
    for (dirpath, unused_dirnames, filenames) in os.walk(rootdir):
        fileset = set(filenames)
        pyc_files = [f for f in fileset
                     if f.endswith('.pyc') or f.endswith('.pyo')]
        for f in pyc_files:
            if f[:-1] not in fileset:   # the .py file isn't present
                os.unlink(os.path.join(dirpath, f))


def compile_handlebar_templates():
    print "Compiling handlebar templates"
    return 0 == popen_return_code([sys.executable,
                                   'deploy/compile_handlebar_templates.py'])


def compile_less_stylesheets():
    print "Compiling less stylesheets"
    return 0 == popen_return_code([sys.executable,
                                   'deploy/compile_less.py'])


def compress_js():
    print "Compressing javascript"
    compress.compress_all_javascript()


def compress_css():
    print "Compressing stylesheets"
    compress.compress_all_stylesheets()


def compress_exercises():
    print "Compressing exercises"
    subprocess.check_call(["ruby", "khan-exercises/build/pack.rb"])


def compile_templates():
    print "Compiling jinja templates"
    return 0 == popen_return_code([sys.executable,
                                   'deploy/compile_templates.py'])


def run_tests(run_complete_test_suite):
    maketarget = 'allcheck' if run_complete_test_suite else 'check'
    print "Running tests (via make %s)" % maketarget
    return 0 == popen_return_code(['make', maketarget])


def prime_cache(version):
    try:
        resp = urllib2.urlopen("http://%s.%s.appspot.com/api/v1/autocomplete?q=calc" %
                               (version, get_app_id()))
        resp.read()
        resp = urllib2.urlopen("http://%s.%s.appspot.com/api/v1/topics/library/compact" %
                               (version, get_app_id()))
        resp.read()
        print "Primed cache"
    except Exception:
        print "Error when priming cache"


def start_many_instances(version):
    try:
        def _open_connection(version=version):
            urllib2.urlopen("http://%s.%s.appspot.com/sleep?key=%s" %
                            (version, get_app_id(), sleep_secret))
        num_instances = 100  # get a reasonable number of instances started up
        for _ in xrange(num_instances):
            # By sending 100 requests that all take 30 seconds to
            # complete (which the /sleep request does), we force
            # appengine to start up 100 instances to handle them all.
            # Then, when we become the default, viola!, there are
            # already 100 instances ready to serve requests.
            # We do this work in threads so as to be non-blocking.
            threading.Thread(target=_open_connection).start()
        print "Starting %s instances" % num_instances
    except Exception:
        print "Error starting multiple instances"


def _quiet_browser_open(url):
    """Opens a browser session without the default Python message to stdout."""
    savout = os.dup(1)
    os.close(1)
    os.open(os.devnull, os.O_RDWR)
    try:
        webbrowser.open(url)
    finally:
        os.dup2(savout, 1)


def open_browser_to_ka_version(version):
    _quiet_browser_open("http://%s.%s.appspot.com" % (version, get_app_id()))


class VersionedConfigs(object): 
    """Context manager (used by a 'with' statement) that replaces VERSION 
    tokens in backends.yaml and queue.yaml so that tasks generated by 
    frontends running version X will always be assigned to backends running 
    the same version X. This operation is revision control-friendly and will 
    always clean up after itself. 
    
    http://preshing.com/20110920/the-python-with-statement-by-example
    """
    
    version_token = "version"
    
    def __init__(self, version): 
        self.version = version
        self.configs = {}

    def __enter__(self): 
        """Pre-deploy: save the original contents of backends.yaml and 
        queue.yaml and then replace their version tokens with the version 
        being deployed"""
        for config in ("backends.yaml", "queue.yaml"): 
            with open(config, 'r+') as config_file: 
                self.configs[config] = config_file.read()
                config_file.seek(0)
                config_file.truncate()
                new_config = self.configs[config].replace(self.version_token, 
                    self.version)
                config_file.write(new_config) 

    def __exit__(self, type, value, traceback): 
        """Post-deploy: restore the files' original contents"""
        for config in self.configs: 
            with open(config, 'w') as config_file: 
                config_file.write(self.configs[config])
                

def deploy(version, email, password):
    print "Deploying version " + str(version)
    return 0 == popen_return_code(['appcfg.py', '-V', str(version),
                                   "-e", email, "--passin", "--backends",
                                   "update", "."],
                                  "%s\n%s\n" % (password, password))


def guess_last_prod_version():
    """Tries to guess the last version that's in production.

    This relies on JavaScript that's embedded into the top of the homepage.
    If no good guess can be found, returns None.
    """

    raw_contents = popen_results([
            "curl", "-s", "http://www.khanacademy.org"])
    ka_version_line = None
    for line in raw_contents.splitlines():
        if line.find("var KA_VERSION =") != -1:
            ka_version_line = line.strip()
            break
    if not ka_version_line:
        return None

    # Version looks like:
    # var KA_VERSION = 'MMdd-<hgversion>.<appengine_code>';
    match = re.match("var KA_VERSION = '(:?\d\d\d\d-)([^.]+)\.(.+)';",
                     ka_version_line)
    if not match or len(match.groups()) < 2:
        return None

    # match.groups can be either ("MMdd-", "hgversion", "appengineversion")
    # or just ("hgversion", "appengineversion")
    return match.groups()[-2]


def main():
    start = datetime.datetime.now()

    parser = optparse.OptionParser()

    parser.add_option('-f', '--force',
        action="store_true", dest="force",
        help="Force deploy even with local changes", default=False)

    parser.add_option('-v', '--version',
        action="store", dest="version",
        help="Override the deployed version identifier", default="")

    parser.add_option('-x', '--no-up',
        action="store_true", dest="noup",
        help="Don't hg pull/up before deploy", default="")

    parser.add_option('-t', '--no-tests',
        action="store_true", dest="notests",
        help="Don't run 'make check' before deploy", default="")

    parser.add_option('--all-tests',
        action="store_true", dest="alltests",
        help="Run 'make allcheck' before deploy, instead of 'make check'",
        default="")

    parser.add_option('-s', '--no-secrets',
        action="store_true", dest="nosecrets",
        help="Don't check for production secrets.py file before deploying",
        default="")

    parser.add_option('-d', '--dryrun',
        action="store_true", dest="dryrun",
        help="Dry run without the final deploy-to-App-Engine step",
        default=False)

    parser.add_option('-r', '--report',
        action="store_true", dest="report",
        help="Generate a report that displays minified, gzipped file size for "
             "each package element",
        default=False)

    parser.add_option('-n', '--no-npm',
        action="store_false", dest="node",
        help="Don't check for local npm modules and don't install/update them",
        default=True)

    parser.add_option('-p', '--force-priming',
        action="store_true", dest="force_priming",
        help=("Prime instances after the deploy, even if a version name is "
              "specified (by default, only daily deploys with no version "
              "names have caches primed and many instances thrown up"),
        default=False)

    options, args = parser.parse_args()

    if options.node:
        print "Checking for node and dependencies"
        if not check_deps():
            return

    if options.report:
        print "Generating file size report"
        compile_handlebar_templates()
        compress.file_size_report()
        return

    includes_local_changes = hg_st()
    if not options.force and includes_local_changes:
        print "Local changes found in this directory, canceling deploy."
        return

    version = -1
    if not options.noup:
        version = hg_pull_up()
        if version <= 0:
            print "Could not find version after 'hg pull', 'hg up', 'hg tip'."
            return

    if not options.nosecrets:
        if not check_secrets():
            print "Stopping deploy. It doesn't look like you're deploying "
            print "from a directory with the appropriate secrets.py."
            return

    # Delete obsolete .pyc files, that do not have an associated .py file.
    delete_orphan_pyc_files('.')

    if not compile_templates():
        print "Failed to compile jinja templates, bailing."
        return

    if not compile_handlebar_templates():
        print "Failed to compile handlebars templates, bailing."
        return

    if not compile_less_stylesheets():
        print "Failed to compile less stylesheets, bailing."
        return

    compress_js()
    compress_css()
    compress_exercises()

    if not options.notests:
        if not run_tests(options.alltests):
            print "Some tests failed, bailing."
            return

    if not options.dryrun:
        last_version = None
        changeset_authors = []
        if options.version:
            version = options.version
        elif options.noup:
            print 'You must supply a version when deploying with --no-up'
            return
        else:
            # Default deploy from tip of tree - find the changesets delta
            # from the last daily (most likely the last prod default)
            last_version = guess_last_prod_version()
            if last_version:
                changeset_authors = get_changeset_authors(last_version)

        print "Deploying version " + str(version)

        (email, password) = get_app_engine_credentials()
        with VersionedConfigs(version): 
            success = deploy(version, email, password)
        if success:
            send_hipchat_deploy_message(last_version, version,
                                        includes_local_changes, email,
                                        changeset_authors)
            open_browser_to_ka_version(version)

            if options.force_priming or not options.version:
                # For default/daily deploys (where no version is specified)
                # and when explicitly told to, we send a bunch of requests to
                # the new version to prime it up for real users.
                prime_cache(version)
                start_many_instances(version)
            # TODO(benkomalo): auto-tag this version? But this should
            # only happen if this version gets marked as stable. How can
            # we do this so it's semi-automatic and hard to forget, but is
            # also accurate?

    end = datetime.datetime.now()
    print "Done. Duration: %s" % (end - start)

if __name__ == "__main__":
    main()
