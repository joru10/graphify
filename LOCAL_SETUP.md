# Graphify Local Setup (macOS)

## 1) One-time install in this repo

```bash
cd /Users/joru2/Applications/Graphify
./scripts/setup_local.sh recommended
```

Profiles:
- `core`: lightest install
- `recommended`: good default for architecture/DD workflows
- `all`: includes heavy extras (video transcription etc.)

## 2) Run Graphify

```bash
./scripts/run_graphify.sh .
./scripts/run_graphify.sh . --update
./scripts/run_graphify.sh . --watch
```

Or use `make` shortcuts:

```bash
make setup
make run
make update
make watch
```

## 3) Create a clickable Mac launcher app

```bash
make app
```

This creates:
- `/Users/joru2/Applications/Graphify/macos/Graphify Launcher.app`

Double-click it to:
- choose target folder
- choose mode (full/update/watch)
- pass optional extra args
- run in Terminal automatically

## 4) Push to your GitHub fork

```bash
cd /Users/joru2/Applications/Graphify
git remote -v
# if needed, point origin to your repo:
# git remote set-url origin https://github.com/<your-user>/graphify.git

git add scripts Makefile LOCAL_SETUP.md
# include macos app wrapper source changes only (not required to track generated .app)
git commit -m "Add local setup scripts and macOS launcher workflow"
git push origin v4
```

If you prefer a clean branch:

```bash
git checkout -b chore/local-launcher-setup
git push -u origin chore/local-launcher-setup
```

## 5) Optional: expose generated graph quickly

After a run, open:
- `graphify-out/graph.html`
- `graphify-out/GRAPH_REPORT.md`
- `graphify-out/graph.json`
