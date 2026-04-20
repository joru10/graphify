SHELL := /bin/bash

.PHONY: setup setup-core setup-all run update watch launcher app

setup:
	./scripts/setup_local.sh recommended

setup-core:
	./scripts/setup_local.sh core

setup-all:
	./scripts/setup_local.sh all

run:
	./scripts/run_graphify.sh .

update:
	./scripts/run_graphify.sh . --update

watch:
	./scripts/run_graphify.sh . --watch

launcher:
	./scripts/launch_graphify_macos.sh

app:
	./scripts/create_macos_app.sh
