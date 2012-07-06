# npm.py - an interface to our increasing love of node
import os
import sys
import commands

MODULE_PATH = os.path.join(os.getcwd(), "tools", "node_modules")


def popen_results(args):
    return commands.getoutput(' '.join(args))


def installed():
    """docstring for npm_installed"""
    return popen_results(["command", "-v", "npm"]).strip()


def local_modules_setup():
    """see if npm install has been called before"""
    return os.path.exists(MODULE_PATH)


def package_installed(package, local_only=False):
    """checks to see if the module is installed and returns a path to it"""
    local_package_path = os.path.join(MODULE_PATH, ".bin", package)

    sys_install = popen_results(["command", "-v", package]).strip()
    local_install = os.path.exists(os.path.join(MODULE_PATH, ".bin", package))

    if local_only:
        return local_package_path if local_install else False
    else:
        return local_package_path if local_install else sys_install


def call(cmd):
    """docstring for install_deps"""
    cd = os.getcwd()
    os.chdir(os.path.join(cd, "tools"))
    npm_results = popen_results(["npm", cmd])
    os.chdir(cd)
    return npm_results


def colorize(string, color, bold=False, highlight=False):
    colors = {
        'gray': 30,
        'red': 31,
        'green': 32,
        'yellow': 33,
        'blue': 34,
        'magenta': 35,
        'cyan': 36,
        'white': 37,
        'crimson': 38
    }

    if not color in colors or not sys.stdout.isatty():
        return string
    else:
        color = str(colors[color] + 10) if highlight else str(colors[color])
        colorcode = [color] if not bold else [color, '1']
        return '\x1b[%sm%s\x1b[0m' % (';'.join(colorcode), string)


def check_dependencies():
    if not installed():
        print colorize("-- DANGA-ZONE!", 'red')
        print "npm isn't installed, try \n"
        print "  curl http://npmjs.org/install.sh | sh"
        print "\nor follow the instructions here:"
        print "  http://npmjs.org/"
        return False

    if local_modules_setup():
        print (colorize("==> A-OK!", 'green') +
               " npm is updating local module dependencies")
        npm_results = call("update")

    else:
        print colorize("==> Danga-Zone!", 'red') + ' (well not really)'
        print "    Installing node dependencies locally via package.json"
        print '  - this should only happen once, all files are in ' \
            + colorize('tools/node_modules', 'yellow') + '\n'
        npm_results = call("install")

    print npm_results
    return True
