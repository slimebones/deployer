- rebuilding to Deployer

# 1.2.0, 16 April 2026

- polish execute capabilities, add -a flag
- extend sdk with missing functions, also add init_build to correctly initialize build directories
- sdk: provide project() instead of context()
- a lot of internal refactors

# 1.1.0, 15 April 2026

- dome status

# 1.0.0, 15 April 2026

- big refactors!

# 0.3.0, 17 November 2025

- support yelets imports, project functions are now available under `@import("project")`
- support yelets if, for, while
- support install, add and upload
- support yelets Path
- extended project imports with information about the build
- yelets: add `cmd` module, with functions such as `call`, with slightly changed signature that returns tuple instead of using a callback
- load `.env` on project start
- yelets: add `os` module
- adaptive search of codes.txt
- corrected all paths for yelets calls to be relative to the target project's source

# 0.2.0, 26 September 2025

- status, commit, push and update commands

# 0.1.0, 25 September 2025

- initial release, `project build` is available, basic `projectfile` is supported, `README.md` with basic design is written