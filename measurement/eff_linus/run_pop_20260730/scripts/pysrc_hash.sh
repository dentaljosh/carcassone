#!/usr/bin/env bash
# path-relative content hash of a staged pysrc tree
root="$1"
cd "$root" && find . -type f -name '*.py' | sort | xargs sha256sum | sha256sum
