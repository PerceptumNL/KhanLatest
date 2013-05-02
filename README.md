**Installation**

Download git from:

http://git-scm.com/download/

So far, to install the english version, retrieve the repository from:

  $ git clone https://github.com/PerceptumNL/KhanLatest
  
Make sure //git// and //nodejs// are installed in your system.

Also, virtualenv needs to be installed. Use the following command:

  $ sudo easy_install virtualenv

Then, is needed to download some dependencies, (it is done automatically):

  KhanLatest$ source activate 
  
  KhanLatest$ kenv firstrun

Finally, set your user name and password for deployment:

  KhanLatest$ kenv setuser

**Always**

//kenv// needs to be loaded. Inside the KhanLatest/ path, run:

  KhanLatest$ source activate 

To see the available command, type:

  KhanLatest$ kenv

**Local testing**

  KhanLatest$ kenv runlocal

Then go to the url http://localhost:8080/

**Deploy**

First, check the current default version at http://appengine.google.com
Then, run:

  KhanLatest$ kenv deploy

After preparing to upload, it will ask for the version name.

**Local Khan Exercises Testing**

Inside ‘KhanLatest/khan-exercises/’ path run:

  KhanLatest/khan-exercises$ python -m SimpleHTTPServer

Then go to the url http://localhost:8000/exercises/
