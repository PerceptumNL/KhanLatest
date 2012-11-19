import zipfile
import sys
import StringIO
import urllib2

response = urllib2.urlopen('http://googleappengine.googlecode.com/files/google_appengine_1.7.3.zip')
html = response.read()

data = StringIO.StringIO(html)
z = zipfile.ZipFile(data)
dest = sys.argv[1] if len(sys.argv) == 2 else '.'
z.extractall(dest)
