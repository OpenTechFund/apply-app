# Developer tips

## Git configuration and commands

To avoid spurious merge commits use a rebase workflow when appropriate.

Set this to always use rebase when pulling in updates in a branch.

```shell
git config --global branch.autosetuprebase always
```

When updating a feature branch with new commits from the main branch use `rebase` and not `merge`

```shell
git switch feature-branch-name
git fetch origin
git rebase origin/main
```

To update the feature branch on GitHub you then need to do a forced push. Instead of `--force` use `--force-with-lease`. If someone have made changes to the branch that you do not have locally you get a warning. It is a good habit to always use `--force-with-lease`. One day it will save you from a bad mistake.

```shell
git push --force-with-lease
```

## Coding style and linting in pre-commit hook

Hypha's coding style is enforced by ruff, stylelint and biome.

Install pre-commit to auto-format the code before each commit:

```shell
pre-commit install
```

If you want to check all files without committing you can run:

```shell
pre-commit run --all-files
```

The pre-commit hook also updates the requirements files for you, see next section about uv.


## Make best use of uv

For development [uv](https://docs.astral.sh/uv/) is a Hypha requirement. It is fast and easy to use.

uv is used to:

* Setup the virtual environment
* Install python dependencies.
* Add and remove python packages.
* Update python packages.
* Generate the requirements files.

See also [Stand alone development setup](../../setup/deployment/development/stand-alone.md)

### Add and remove packages with uv

All python requirements are listed in `pyproject.toml`.

To add a package:

```shell
uv add django-htmx
```

To remove a package:

```shell
uv remove django-select2
```

After adding or removing a packages run this to update `uv.lock`.

```shell
uv sync
```

When you attempt to commit the pre-commit hook will update the requirements files for you.

The requirements files exist so you do not need uv for deployment.


## Postgres snapshots/restore

Hypha dev requirements contain the [dslr](https://github.com/mixxorz/DSLR) tool. Use this for fast snapshots and restores of the postgres database.

Perfect when testing migrations and other times when you need to reset the database or switch between databases.

Take a snapshot, you can have as many as you like.

```shell
dslr snapshot name-of-the-snapshot
```

Restore the snapshot.

```shell
dslr restore name-of-the-snapshot
```

Delete a snapshot you no longer need.

```shell
dslr delete name-of-the-snapshot
```

List all your snapshots:

```shell
dslr list
```

## Commands in Makefile

This is the one stop place to find commands for running test, build resources and docs, linting and code style checks/fixes.

The one command you will be running the most is:

```shell
make serve
```

This command runs `npm watch` to keep the front end updates and runs development servers for both Hypha app and the Hypha docs.

## Editor extensions

If you editor does not have a Language Server Protocol (LSP) preinstalled make sure to add the plugin for it. Then add "LSP-ruff" for a fast Python linter and code transformation tool.

Your editor most likely have plugins for the other languages Hypha uses as well, css/scss, yaml and html. We recommend to install them as well.

## Shell configuration

In the shell you can press the up arrow to see earlier (history) commands. It is possible to bind this to history search.

You can then e.g. write `git` and then press the upp arrow and see the commands from your history that start with `git`. So useful and intuitive that it should be the default.

For zsh:

```shell
# Settings for history function
HISTFILE=$ZDOTDIR/.zsh_history
HISTSIZE=75000
SAVEHIST=70000
setopt append_history
setopt extended_history
setopt hist_expire_dups_first
setopt hist_ignore_dups
setopt hist_ignore_space
setopt hist_reduce_blanks
setopt hist_verify
setopt inc_append_history
setopt share_history
autoload -Uz up-line-or-beginning-search
autoload -Uz down-line-or-beginning-search
zle -N up-line-or-beginning-search
zle -N down-line-or-beginning-search

# Bind up/down arrows to history search.
if [[ $OSTYPE == darwin* ]]; then
  bindkey '\e[A' up-line-or-beginning-search
  bindkey '\e[B' down-line-or-beginning-search
else
  bindkey "${terminfo[kcuu1]}" up-line-or-beginning-search
  bindkey "${terminfo[kcud1]}" down-line-or-beginning-search
fi
```

For bash:

```shell
# Settings for history function
export HISTFILESIZE=50000
export HISTSIZE=50000
export HISTCONTROL=ignoreboth:erasedups
export HISTIGNORE='\&:e:c:l:ca:cd:cd -'

# Make history work well with multiple shells
# append to the history file, don't overwrite it
shopt -s histappend

# Bind up/down arrow to history search
bind '"\e[A":history-search-backward'
bind '"\e[B":history-search-forward'
```

