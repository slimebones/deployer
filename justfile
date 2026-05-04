set shell := ["nu", "-c"]

main *args:
    @ python deployer/main.py {{args}}

test:
    @ pytest tests

install:
    @ pip install -e .