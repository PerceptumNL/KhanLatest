import re
from setuptools import setup, find_packages

def extract_version():
    """
    Find the version without importing the package. Via zooko:
    http://stackoverflow.com/questions/458550/standard-way-to-embed-version-into-python-package/7071358#7071358
    """
    version_str_line = open("agar/_version.py", "rt").read()
    VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
    mo = re.search(VSRE, version_str_line, re.M)
    if mo:
        version = mo.group(1)
    else:
        raise RuntimeError("Unable to find version string in agar/_version.py.")

    return version

setup(
    name='agar',
    version=extract_version(),
    description='A collection of libraries for making Google App Engine development easier.',
    long_description=open("README.rst").read(),
    license="MIT",
    author='Thomas Bombach, Jr.',
    author_email='thomas@gumption.com',
    url='http://bitbucket.org/gumptioncom/agar',
    zip_safe=False,
    packages=find_packages(exclude=['tests', 'tests.*', 'lib']),
    classifiers=[
      "Development Status :: 3 - Alpha",
      "Environment :: Web Environment",
      "Intended Audience :: Developers",
      "Topic :: Internet :: WWW/HTTP",
      "Topic :: Utilities",
      "License :: OSI Approved :: MIT License"
    ]
)
