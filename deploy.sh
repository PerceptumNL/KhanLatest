#!/bin/bash
export COLOR_NC='\e[0m' # No Color
export COLOR_WHITE='\e[1;37m'
export COLOR_BLACK='\e[0;30m'
export COLOR_BLUE='\e[0;34m'
export COLOR_LIGHT_BLUE='\e[1;34m'
export COLOR_GREEN='\e[0;32m'
export COLOR_LIGHT_GREEN='\e[1;32m'
export COLOR_CYAN='\e[0;36m'
export COLOR_LIGHT_CYAN='\e[1;36m'
export COLOR_RED='\e[0;31m'
export COLOR_LIGHT_RED='\e[1;31m'
export COLOR_PURPLE='\e[0;35m'
export COLOR_LIGHT_PURPLE='\e[1;35m'
export COLOR_BROWN='\e[0;33m'
export COLOR_YELLOW='\e[1;33m'
export COLOR_GRAY='\e[0;30m'
export COLOR_LIGHT_GRAY='\e[0;37m'

export COLMSG=$COLOR_LIGHT_BLUE
export COLNC=$COLOR_NC
alias echo="echo -e"

PASS=
EMAIL=
APPCFG=

. deploy_settings.sh &> /dev/null

DEPLOY=deploy
REQUIREMENTS=$DEPLOY/requirements.txt
VE=$DEPLOY/env

command_exists() {
  CMD=$1
  if [ -z "$1" ];then
    return 0
  fi
  if command -v $CMD &>/dev/null;then
    return 1
  else
    return 0
  fi
}

install_easyinstall() {
  sudo port install easy_install
  echo "Installing easy_install Mac port ..."
}

install_pip() {
  echo "You need to install pip."
}

install_virtualenv() {
  command_exists easy_install
  if [ $? -eq 1 ];then
    echo "Installing virtualenv ..."
    sudo easy_install virtualenv
  else
    install_easyinstall
    exit 1
  fi
}

create_virtualenv() {
  command_exists virtualenv
  if [ $? -eq 0 ];then
    install_virtualenv
  fi
  echo "${COLMSG}Creating virtual environment $VE ... $COLNC"
  virtualenv $VE
}

load_env() {
  echo "${COLMSG}Loading virtual environment $VE... $COLNC"
  CURR=`pwd`
  cd $VE &>/dev/null
  source bin/activate
  cd $CURR &>/dev/null
}


init_submodules() {
  echo "${COLMSG}Initializing submodules ... $COLNC"
  git submodule init
  git submodule update
#  cd third_party/appengine-search-src/search/
#  rm -rf pyporter2
#  ln  -s ../../../search/pyporter2
#  cd -
}

install_deps() {
  pip install ez_setup
  pip install -r $REQUIREMENTS
}

create_deploy() {
  echo "${COLMSG}Creating a deployment version ... $COLNC"
  python deploy/deploy.py
}

upload_deploy() {
  command_exists $APPCFG
  if [ $? -eq 0 ];then
    echo "${COLMSG}OK, now you need to upload the version with the AppEngine${COLNC}"
  else
    echo "${COLMSG}Uploading version ... $COLNC"
    echo $PASS | $APPCFG --passin -e $EMAIL update .
  fi

  command_exists notify-send
  if [ $? -eq 0 ];then
    notify-send "Depoyment complete!"
  fi
}

start_deploy() {
  if [ -d $VE ];then
    load_env
    create_deploy
    upload_deploy
  else
    init_submodules
    create_virtualenv
    load_env
    install_deps
    create_deploy
    upload_deploy
  fi
}

clean() {
    rm -rf $VE
}

start_deploy
