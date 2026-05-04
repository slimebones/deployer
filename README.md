# Dome

Collection of utilities for project technical management. Should contain all the features we need to deploy reliable projects with focus on simplicity.

This software manages projects, which are directories with a file named `project.py` defined. These files contain Python Programming Language code aimed on providing customizable project development services, such as building, code generation, dependency management.

While every project could be an application, library, module, Dome does not distinguish their types. It's all *software*. And if it's a software, and we have `project.py` defined, then Dome can control it.

Projects can be nested. This pattern is recognizable by Dome, and in fact, it's a core part of how crucial commands works, for example, see [execute -a](#execute).


## Console Commands

Every console call to Dome is written according to this pattern:
```
dome {...dome_args} {module} {...module_args}
```

Below we will discuss available Dome arguments, and then, shortly, available modules.

### Dome Arguments

#### `-d`

Enables Debug mode. This is a special simple state to choose a specific behaviour. In combination with mode selection `-m`, this allows to support wide variety of strategies. Disabled by default.

#### `-m {mode}`

Specifies a mode for the call. Modes allow to choose a specific behaviour. Default: `default`.


#### `-v`

Specifies a version for the call. The version can be used in sequences like releasing. If is not provided, the following command might pop up a prompt to enter the version.


#### `-cwd`

Alters current working directory. Default: current working directory, where the command were executed.

### Modules
#### init

```
dome init {project_id} {template = null}
```

Creates a new project using template.

#### execute

```
dome execute {function_name} {...args}
```

Executes a function, defined in `project.py`.

If you provide flag `-a`, this command will execute a function for this, and all nestead projects. The same arguments are passed for each function.

Target function should be a defined in `project.py` object, following signature `Callable`, accepting one of the following:
- zero arguments
- `args` list of strings
- `kwargs` dict, keys are strings, values are strings
- both `args` and `kwargs`

Example:
```python
# project.py

def deploy(args: list[str], kwargs: dict[str, str]):
    # implementation...
    pass
```

See [SDK](#sdk) for the information of how to use powers of Dome in the custom functions.

#### package

```
dome package {subcommand}
```

Manages Packages - bundled projects.

The subcommands are listed below.

##### install

```
dome package install
```

Installs/Refreshes all project-specified dependencies.

##### upload

```
dome package upload {directory}
```

Uploads a package to a server, specified in project's `user.cfg` configuration.

##### add

```
dome package add {package_id} {version = "latest"} {output_directory = *original package id*}
```

Adds a package to package list of the current project and does call [install](#install) afterwards.

#### status

```
dome status
```

Displays information about the current project.


#### vc

```
dome vc {subcommand}
```

Utilities for Version Control System.

The subcommands are listed below.

##### commit

```
dome vc commit
```

Commits changes to version control. The commit message is generated automatically, see [why we use automatic git commit messages](https://ryzhovalex.com/post/why-we-use-automatic-git-commit-messages).

##### push

```
dome vc push
```

Pushes changes to version control.

##### update

```
dome vc update
```

Updates changes from version control. Works like a `git pull` if applicable to Git.

## Structure of `project.py`

File `project.py` is a normal python script, which can define various objects, as well as import stuff. The minimal `project.py` looks just like this:
```python
project_id = "my_project"
```

Yes, the `id` is the bare-minimum for starting a project. Everything beyond that is custom-space: everything that is needed for the project technical management.

Any defined here object without leading underscore will be available for the external commands. Everything prefixed with a `project_` is **reserved**.

### SDK

Every Dome installation comes with SDK, available as `import dome.sdk`. It is a collection of utilities for powerful collaboration with the Dome, mainly from `project.py` custom functions.

Work Under Progress: SDK's interface and documentation is currently under an active development. Consider reading Python's built-in `help()` on `dome.sdk` module.
