set shell := ["nu", "-c"]

main *args:
    @ python dome/main.py {{args}}

test:
    @ pytest tests

install:
    @ pip install -e .