#!/bin/bash

set -e

echo "#########################################"
echo "Starting ${GITHUB_WORKFLOW}:${GITHUB_ACTION}"
echo "Args: $*"
echo "Working directory: "
pwd
ls -la 
echo "Env: "
set

pip3.7 install -r requirements.txt
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
py.test -p no:cacheprovider -W ignore::DeprecationWarning --tb=long tests
