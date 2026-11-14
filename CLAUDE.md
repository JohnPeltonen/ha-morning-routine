# ha-morning-routine

A public, MIT-licensed Home Assistant custom integration, domain `morning_routine`. It runs scripts, scenes and automations around the alarm on an Android phone.

Read these first:
- [docs/status.md](docs/status.md): where the work stands and what's next. Start here.
- [docs/superpowers/specs/2026-11-01-morning-routine-integration-design.md](docs/superpowers/specs/2026-11-01-morning-routine-integration-design.md): the design.
- [docs/superpowers/plans/2026-11-01-phase-1-rules-settings-first-install.md](docs/superpowers/plans/2026-11-01-phase-1-rules-settings-first-install.md): the Phase 1 plan.

## This repo is public

Never put any of these in code, docs, tests, test data or commit messages:
- household names or addresses
- entity IDs from the owner's house, or real phone identifiers
- household habits: when people leave, when the owner is away, real alarm times, how the owner's cameras behave, the owner's script names

The owner's GitHub name in URLs, the LICENSE and codeowners is fine. Public Android package names, such as `com.sec.android.app.clockpackage`, are fine. Test data uses made-up values, such as `sensor.test_phone_next_alarm`.

House details for this work, and the steps that change the owner's Home Assistant server, are in the owner's private repo `JohnPeltonen/home-assistant`, in `morning_routine/status.md`. That repo's `CLAUDE.md` has the rules for touching the server.

Project memory goes in [docs/status.md](docs/status.md). `.claude/docs/memory/` is git-ignored in this repo, so notes there never leave the computer they were written on.

## Commands

First time on a computer (Windows, Python 3.14):

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements_test.txt
```

Rules and translation tests, from the repo root. `tests/ha` is skipped, because Home Assistant can't be installed on native Windows:

```bash
.venv/Scripts/python.exe -m pytest -v
```

Home Assistant tests run in GitHub Actions on every push (`.github/workflows/tests.yaml`, plus `hassfest.yaml`). Read the results with:

```bash
gh run list --repo JohnPeltonen/ha-morning-routine --limit 5
gh run view <id> --log-failed
```

On Linux or WSL with Python 3.14, `pip install -r requirements_test_ha.txt` then `pytest tests/ha -v` runs them the way CI does. On the owner's desktop, WSL Ubuntu has that environment at `/root/mr/.venv`, and the tests run straight from the Windows folder:

```bash
wsl -d Ubuntu -- bash -c 'cd /mnt/d/code/ha-morning-routine && /root/mr/.venv/bin/python -m pytest tests/ha -q -p no:cacheprovider'
```

Card tests, with Node 24:

```bash
node --test "tests/card/*.test.mjs"
```

A throwaway Home Assistant for trying the card in a browser. It is the oldest supported version, uses made-up devices from the `demo` integration, and listens on `http://localhost:8123`. Its settings folder is `/root/mr-try` in WSL, outside the repo:

```bash
wsl -d Ubuntu -- bash /mnt/d/code/ha-morning-routine/tests/try/start.sh
# The first time only, once it has started:
wsl -d Ubuntu -- bash -c 'cd /mnt/d/code/ha-morning-routine && /root/mr/.venv/bin/python tests/try/set_up.py'
```

Then open `http://localhost:8123/try-card`. The accounts are `tester` (admin) and `member` (not an admin), and the password is in `tests/try/set_up.py`. Restart it after changing any Python file. To start over, stop it and delete `/root/mr-try`.

## Conventions

- Absolute imports everywhere, including between the integration's own modules: `from custom_components.morning_routine.const import DOMAIN`. The Franklin-Home-Assistant repo allows relative imports inside its integration. This repo does not.
- `rules.py` never imports `homeassistant`. All alarm decisions live there and are tested locally.
- Forms and service schemas use `probatio`, not `voluptuous`.
- snake_case, PascalCase classes, UPPER_CASE constants, `logger = logging.getLogger(__name__)` with %-style formatting, `T | None`, minimal docstrings.
- `strings.json` and `translations/en.json` must hold the same text. `tests/test_translations.py` compares them.

## Git

- Commit straight to `main` with explicit paths: `git commit <paths> -F -`. A new file needs `git add -- <path>` first.
- On 2026-11-01 the owner authorized pushing this repo for the rest of Phase 1. For later phases, ask before pushing.
- No force pushes, amends or `reset --hard` without asking.
