set shell := ["nu", "-c"]

# `just` with no args runs this (development run)
default: dev

dev:
    @ python deployer/main.py version

main *args:
    @ python deployer/main.py {{args}}

test:
    @ pytest tests

install:
    @ pip install -e .
