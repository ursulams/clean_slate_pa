#! /usr/bin/env bash

# Install dependencies
uv sync

# Mark the workspace folder as safe
git config --global --add safe.directory ${WORKSPACE}

# Install pre-commit hooks
uv tool run pre-commit install --install-hooks
