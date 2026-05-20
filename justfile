set shell := ["nu", "-c"]

# `just` with no args runs this (development run)
default: dev

dev:
    @ python installer/main.py version

main *args:
    @ python installer/main.py {{args}}

test:
    @ pytest tests

install:
    @ pip install -e .
