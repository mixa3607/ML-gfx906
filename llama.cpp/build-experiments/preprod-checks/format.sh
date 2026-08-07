#!/bin/bash

cat cols.yaml | yq -o=csv
yq -p=json -o=csv '(load("cols.yaml")) as $c | [ $c[] as $k | (select($k == "devices") | .devices | split("/") | length) // .[$k] ]' $1
