#!/usr/bin/env bash

function git_get_origin {
  if [ "$1" != "" ]; then pushd "$1" > /dev/null; fi
  git config --get remote.origin.url
  if [ "$1" != "" ]; then popd > /dev/null; fi
}

function git_get_current_tag {
  if [ "$1" != "" ]; then pushd "$1" > /dev/null; fi
  git tag --points-at HEAD --sort=-creatordate | sed -n '1{s|+||g;p;}'
  if [ "$1" != "" ]; then popd > /dev/null; fi
}

function git_get_current_sha {
  if [ "$1" != "" ]; then pushd "$1" > /dev/null; fi
  git rev-parse --short HEAD
  if [ "$1" != "" ]; then popd > /dev/null; fi
}

function git_get_current_ref {
  local REF
  : "${REF:="$(git_get_current_tag "$1")"}"
  : "${REF:="$(git_get_current_sha "$1")"}"
  echo "$REF"
}
