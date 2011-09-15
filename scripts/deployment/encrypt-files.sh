#! /bin/bash

input=$2
set -e

function error() {
  local PARENT_LINENO="$1"
  local MESSAGE="$2"
  local CODE="${3:-1}"
  if [[ -n "$MESSAGE" ]] ; then
    echo "Error at line ${PARENT_LINENO}: ${MESSAGE}; exiting with status ${CODE}"
  else
    echo "Error at line ${PARENT_LINENO}; exiting with status ${CODE}"
  fi
  exit "${CODE}"
}
trap 'error ${LINENO}' ERR

case "$1" in
  encrypt)
    if [ -d $input ]; then
      echo "Encrypting configuration files..."
      tar -cjO $2 | gpg -ca --force-mdc > $input.tbz.asc
    fi
    ;;

  decrypt)
    if [ -f $input ]; then
      echo "Decrypting configuration files..."
      gpg -d $input | tar -xj
    fi
    ;;

  *)
    echo "Usage: encrypt-files.sh {encrypt|decrypt} <encrypted_file|folder_name>"
esac

