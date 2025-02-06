#!/bin/bash

# Read the JSON file and set environment variables in GHA
while read -r line; do
    echo "$line" >> $GITHUB_ENV
done < <(jq -r '.[] | .Key + "=" + .Value' .stack-outputs.json)