# Status

Last updated 2026-11-12.

## Where Phase 3 stands

Phase 3 lets a step change a light or a thermostat directly, with no label. The owner asked for it on 2026-11-11. It is built, reviewed and pushed. It is not on any server yet.

- All 8 tasks of the [Phase 3 plan](superpowers/plans/2026-11-11-phase-3-light-and-thermostat-steps.md) are done. One session built it, and one fresh reviewer then read the whole change on 2026-11-12.
- The integration version is 0.3.0.
- Tests: 149 rules and translation tests, 215 Home Assistant tests, and 45 card tests.
- The new form was run in a browser at 360 pixels wide against the fake server in `tests/card/demo.html`, by script. It has not been seen inside Home Assistant, and no step has changed a real light or thermostat yet.

### What Phase 3 added

- A step now has an id, an action (`run`, `turn_on`, `turn_off` or `set_temperature`) and up to four settings. An alarm records what ran by the step's id, or by its item when it has no id. Scripts, scenes and automations have no id, so files saved by version 0.2.0 behave the same.
- `devices.py`: works out what type a device is from what it reports, and which Home Assistant actions a step sends.
- `step_input.py`: checks a device step's action and settings against the device.
- The view lists every light and thermostat beside the labelled items.
- The card's form has a search box, a grouped list, and the action and settings that fit the item chosen.

### Next for Phase 3, each needing the owner's approval

1. Update the integration on the owner's server to 0.3.0 and restart.
2. Try one light step and one thermostat step with the owner watching, before relying on either.

### Decisions made while building Phase 3

Each says what was decided, why, and what it costs if wrong.

1. **A missing label is no longer shown as a problem on the card.** A routine can now be built from devices alone. The add-a-step form has a note about the label when no labelled item is offered. Cost: a household with no label gets no hint on the card's face.
2. **The picker is the browser's own list with a search box above it,** grouped into Lights, Thermostats, and Scripts, scenes and automations. Least code, and a phone shows its own picker. Cost: it may feel clumsy with hundreds of devices.
3. **A new form starts on "Choose one".** With every light listed, a stray tap on Save would otherwise add whatever came first. Cost: one more tap.
4. **A device that reports "unavailable" still counts as a step that can run.** Its step stays in place and is tried at its time. Cost: Home Assistant skips an unavailable light without an error, so the step is recorded as started when nothing happened.
5. **A light or thermostat step that is removed and added back is a new step.** If its time is still ahead of the alarm, or already due before the alarm, it runs again that morning. A script does not, because it is known by its item. The spec says a step that ran doesn't run again when removed and added back, so this is a known gap for devices. Cost: a device can be switched on twice in one morning after such an edit.
6. **A range thermostat in `auto` mode that shows one temperature gets "heat to".** The spec doesn't mention auto mode. Cost: the wrong number on a thermostat that is cooling in auto mode.
7. **Which type a thermostat is comes from the features it reports.** Thermostats that report the range feature all the time can only have temperatures set, never be turned on or off by a step. Cost: none known for those; see the Venstar item below for one that changes.
8. **Three refusal messages were reworded** to cover devices: a step that isn't written correctly, an item that can't be a step, and an item listed twice.
9. **New card text the owner has not seen:** "What to do", "Search", the hints "as it was" and "last setting", "No longer available. It was deleted.", the sentence shown when there is nothing to add, and the note about the label in the form.
10. **The card's logic was written before its tests were updated.** The reviewer checked this by changing the logic 35 ways and running the tests. No test was unable to fail. Two gaps were found and tests were added for them.

### Final review of Phase 3

One fresh reviewer read commits 1fe6991 (fix a card that could get stuck after a connection drop) to a5545ba (document light and thermostat steps and move to version 0.3.0) on 2026-11-12. It ran every test suite, wrote 12 probes, and ran the form in a browser.

**Fixed:**

- **Pressing Enter in the form's search box saved the step.** A person searching for a different item could add the one already chosen, and a step due soon runs right away. Enter in the search box now does nothing. Checked in a browser before and after. There is no automated test for it, because the form has none (see below).
- **A list sent to `set_steps` without ids could give one step another step's id.** With two steps for one light, sending them in the other order ran the first one twice and never ran the second. Each entry that is exactly an existing step now keeps that step's id, and only then do changed entries get one. Two tests failed first.
- **A range thermostat in heat or cool mode that still shows both numbers got both.** The spec says only the fitting number is sent. The mode now decides first. Two tests failed first.
- Two tests were added for the card: editing one of two steps for the same light leaves the other alone, and changing only a step's item gives it a new id.

**Checked and found fine:** all five Review Focus items in the plan, 11 hand-made requests from a non-admin account (all refused), Home Assistant's climate feature numbers, no red, no clock times, and no `innerHTML`.

**Found and not fixed.** None is filed as an issue. The owner confirms each one first.

- The form can save something different from what it shows if a device changes while the form is open. A brightness box stays visible after the light stops reporting that it dims, and the brightness is then left out. A "Turn off" step for an unavailable light shows "Turn on" if the light comes back while the form is open.
- A thermostat that reports the range feature only in some modes changes type with its mode. Home Assistant's Venstar integration does this. A "turn on" step saved in heat mode can't be edited while the thermostat is in auto mode.
- After a restart, a step for a light that has no state yet is not dropped, and it runs when the light appears, even long after its time. This only affects lights with no entry in the entity registry.
- A step for an unavailable light or one-temperature thermostat is recorded as started (decision 4 above).
- A hand-made request can give a device step any text as its id, including a script's entity id, which then blocks that script from being added. The card never sends this.
- `light.Lamp` with a capital letter is accepted from the `set_steps` action, and the card then shows it as a device that isn't in its list.
- The form (`_openForm`, `_fillFormSettings`, `_saveForm`, `_refreshForm`) has no automated test. It was checked by a scripted browser run that is not in the repo.
- `chosenItem(items, null)` and its test are left over. No form starts on its first item any more.
- A hidden light is left out of the card's list but accepted by the server if named directly.
- The view now carries every light and thermostat and is sent on every change to the routine and every entity registry change. It has not been measured on a house with hundreds of devices.

## Where Phase 2 stands

Phase 2 is the dashboard card with time steps. It is built and pushed. The owner installed it on 2026-11-11 at commit 1fe6991 (fix a card that could get stuck after a connection drop), and the card showed a routine correctly on a dashboard.

- Tasks 1 to 7 of the [Phase 2 plan](superpowers/plans/2026-11-10-phase-2-card-with-time-steps.md) are done, and Task 8 through step 4. One session built every task. One fresh reviewer then read the whole change on 2026-11-11, and its two most serious findings were fixed (see "Final review of Phase 2" below).
- Phase 2 was version 0.2.0.
- Tests: 142 rules and translation tests, 127 Home Assistant tests, and 29 card tests (23 for the logic, 6 for the element when the connection drops).
- The card was run in a browser at 360 pixels wide against a fake server (`tests/card/demo.html`). The plan's demo cases and form checks were gone through there by script, and 3 screenshots were kept, not one per case as the plan asked. The demo's fake server can't drop its connection, so a Home Assistant restart was not seen in a browser; the element tests cover it. The card has not been seen inside Home Assistant.

### What Phase 2 added

- `step_input.py`: the checks on a list of steps. A step already in a routine may stay after its item is deleted or loses the label.
- `view.py`: one bundle of facts about a routine, which the card draws.
- `websocket.py`: three commands for the card. Anyone logged in may use them.
- `card.py` and `www/morning-routine-card.js`: the card, served and loaded by the integration.

### Next for Phase 2, each needing the owner's approval

1. Update the integration on the owner's server and restart.
2. Put the card on a test dashboard and check it on a phone, as a non-admin account if one is available.

### Decisions made while building Phase 2

Each says what was decided, why, and what it costs if wrong.

1. The tests need the `home-assistant-frontend` package, pinned in `requirements_test_ha.txt`. The integration now depends on the frontend component, which can't set up in tests without it. The pin must move when the Home Assistant test version moves.
2. The card tests run with `node --test "tests/card/*.test.mjs"`. Node 24 on Windows fails when given the folder. No cost.
3. The card and its form were committed together. They are one class. Cost: a coarser history.
4. The minutes box is a text box with a number keypad, not a number box. A number box hides letters from the check, so typing "abc" could not get its sentence. Cost if wrong: one attribute.
5. After the connection to Home Assistant comes back, the card subscribes again by itself, and does not rely on the frontend library to do it. After a restart the routine may not be loaded yet, and the card's own 10-second retry covers that. The first build of this could leave the card stuck until the page was reloaded; the final review found that and it is fixed.
6. `build_view` takes a plain `ConfigEntry` type hint. Importing the integration's own alias would be a circular import. Cost: a type hint.
7. A second error text, `clock_not_offered`, sits beside the older `clock_not_found`. The older one names the clock; the card's command has only an app id to show, which means nothing to a person.

### Final review of Phase 2

One fresh reviewer read commits cd91a1e (add the Phase 2 plan) to 6d0ad91 (document the card and record Phase 2 status) on 2026-11-11. It ran every test suite and wrote its own probes.

**Fixed, each with a test that failed first:**

- **The card could get stuck after a connection drop.** A subscribe made while the connection was down, or cut off by a drop, was never answered, and the card then refused to try again. That left it blank or saying "This routine isn't available" until the page was reloaded. The card now sends nothing while the connection is down, and a new subscribe is allowed after every reconnect. Tests: `tests/card/card-element.test.mjs`.
- **An open form could switch to a different item without saying so.** If someone else used the chosen item as a step while the form was open, the picker moved to the first item left, and Save would have added that one. The picker now shows "Choose one", the form says "That choice is no longer available. Choose again.", and Save is off until something is chosen. Test: `chosenItem` in `tests/card/card-logic.test.mjs`.

**Checked and found fine:** the five Review Focus cases in the plan on the server, every change by a non-admin account, no `innerHTML` in the card, no red, no clock times, and every exact text in the plan.

**Found and not fixed.** None is filed as an issue. The owner confirms each one first.

- Each subscribe leaves one callback on the routine's config entry until the routine reloads. Memory grows slowly with every dashboard opened. (`websocket.py`)
- The server sends the same view again for every entity or label registry change anywhere in Home Assistant. Each one redraws the card, which can close an open dropdown and clear a refusal message early. (`websocket.py`)
- `test_a_second_routine_does_not_register_the_card_twice` can't fail, because Home Assistant keeps the addresses in a set. (`tests/ha/test_card.py`)
- Keyboard focus is lost after a switch or the clock picker is used, because the controls are disabled while the change is sent.
- The "alarm time has already passed" sentence and a renamed routine title appear only after some other change or reopening the page. Nothing sends a new view for them.
- The switches are 36 by 20 pixels and a step's name is one line of text, which are small targets on a phone. The form's dialog has no accessible name.
- When a routine unloads, the card's unsubscribe gets an error answer from the server. Harmless.
- A read-only account can also change a routine. The spec says anyone logged in, so this was left as it is.
- `test_subscriber_is_told_when_the_routine_unloads` checks the message only, not that the server's listeners were removed.

**Card text added during the build that the plan didn't list.** The plan says card text is the owner's call:

- "That change couldn't be saved." Shown when a change fails and the server gave no reason.
- "That choice is no longer available. Choose again." and the picker's "Choose one".
- Screen reader labels: "Routine", "Edit step: (the step's name)", "Before or after the alarm".

## Where Phase 1 stands

Phase 1 is built, passing CI, and installed on the owner's server since 2026-11-10. A test with a harmless script passed that day: the step ran 2 minutes before a test alarm.

- Tasks 1 to 8 of the [Phase 1 plan](superpowers/plans/2026-11-01-phase-1-rules-settings-first-install.md) are done, and Task 9 through step 5.
- A second look at the final-review fixes was done 2026-11-10, with no findings. It covered c23f0f7 (treat a snooze seen after the sensor moved on as the same alarm) and 125d70d (limit steps to 60 minutes after the alarm and correct the README). The snooze fix relies on the sensor moving off an alarm only after the alarm time. In 10 days of readings from two phones, the sensor moved on 0.5 to 6.3 seconds after the alarm time at every ring, and never before.

### Left from Phase 1, each needing the owner's approval

1. **Task 9, step 6: the real routine.**
2. **Close Phase 1.** File the confirmed tickets below. Delete the run's scratch folder, `.superpowers/sdd/2026-11-01-phase-1-rules-settings-first-install/`, on the computer that has it.

## Later phases

Each needs its own plan and its own go from the owner. They are listed at the end of the Phase 2 plan: motion steps, two smaller items (clock apps from the sensor's past history, and refusing scripts that need input fields), and release.

## Resuming with subagent-driven-development

The run's ledger was in `.superpowers/sdd/`, which git ignores, so it exists only on the computer that ran it. Everything it recorded that still matters is in this file.

**Do not re-run the plan.** Every task through Task 9 step 3 is done. To resume with the skill on another computer, create `.superpowers/sdd/2026-11-01-phase-1-rules-settings-first-install/progress.md` with:

```
# SDD ledger — plan: docs/superpowers/plans/2026-11-01-phase-1-rules-settings-first-install.md
Task 1: complete
Task 2: complete
Task 3: complete
Task 4: complete
Task 5: complete
Task 6: complete
Task 7: complete
Task 8: complete
Task 9: steps 1 to 3 done. CI green on 125d70d. Next: scoped re-review of 8d29858..125d70d, then step 4 with the owner's approval. Rulings 1 to 27 are in docs/status.md.
```

## Where the code differs from the plan

These rulings changed what the plan asked for. Each one is in full below.

- `set_steps` accepts offsets from -720 to 60 minutes, not -720 to 720 (ruling 26).
- An alarm first seen more than 5 seconds after its time runs no steps (ruling 8).
- At a restart, a step needs the phone to have been home before the restart and not to report somewhere else now (ruling 16).
- A step's service call never runs while the evaluation lock is held (ruling 15).
- A phone whose Next alarm sensor is off isn't offered when adding a routine. The spec was corrected to match (ruling 20).
- Diagnostics show only "home" or "not home", never a zone name (ruling 23).
- Imports are absolute everywhere (ruling 22).

## Rulings

Decisions made during the run, copied from its ledger. Each says what was decided, why, and what it costs if wrong. "The owner" is the repo owner.

1. `loaded` fixture is added to tests/ha/conftest.py in Task 7; Task 6's options test uses it and first passes after Task 7. The fixture needs `__init__.py`, and Task 5 tests Routine directly with MockConfigEntry. Costs one CI failure on Task 6's options test until Task 7 if wrong order.
2. At restart, an overdue disabled step is dropped like any blocked step. The plan's decision says blocked ones are included and a toggle is a block. If wrong, a step toggled on after a restart waits for the next alarm.
3. GitHub Actions is the test runner for tests/ha. Tasks 5, 6, 7 push and read CI results, so those tests really run per task rather than all at Task 9. The owner authorized pushing. Costs failing runs visible on a public repo.
4. `test_non_admin_can_use_the_switches` uses a user created with `GROUP_ID_USER`, not `hass_read_only_user`. The requirement is a normal non-admin account. No cost if wrong beyond a test rewrite. `test_set_steps_refused_for_non_admin` also uses `GROUP_ID_USER`.
5. The controller runs Task 8's household-name search itself, so the names never enter a brief. No cost.
6. Task 9 Step 2 is done by the controller pushing. The owner authorized it on 2026-11-01. No cost.
7. Reviews and re-reviews use Opus and implementers use Sonnet. The owner's plan-sizing rule keeps reviews on the higher tier. If Fable is more capable, reviews were one tier lower than the rule asks.
8. An alarm first seen, or returning, more than `CLOCK_SKEW` after its time gets `went_off=True` and a new field `seen_late=True`, without touching `skip_next`. `steps_to_run` never runs a `seen_late` alarm (spec: if the alarm has passed, the step is dropped). Only `steps_after_restart` may, and `skip_next` blocks it there. This reverses the plan's step 4 `settle` call for that case. The spec says a skip turned on after an alarm applies to the next alarm, and using it up on a stale value would let the next real alarm start a step. If wrong, a stale value leaves the switch on until the next real alarm, which is the safe direction.
9. `steps_to_run` records a step in `alarm.dropped` once it can no longer run. A restart must not start a step already lost while running (spec anti-goal). A step lost this way stays dropped if retimed after the alarm passed, which can only cost a step. Task 5 must call `steps_after_restart` before `steps_to_run` at startup, and pass `dt_util.utcnow()` rather than the timer's argument.
10. A phone connection drop over 60 seconds that returns the same alarm still ahead runs overdue steps right away. Pinned with a test. The spec's "seen late" rule allows it, the alarm is real, and a glitch must not cost the morning; the anti-goal aims at starts with no real alarm behind them. If wrong, a reconnect can start a step late, only while its alarm is still ahead.
11. An alarm first seen within 5 seconds after its time is not `seen_late`, so its at-alarm step runs. That's the clock skew rule, and the window is 5 seconds. If wrong, one on-time step runs up to 5 seconds after a late first sighting.
12. `steps_to_run` drops every step of a `seen_late` alarm at once, whatever its time. Spec: if the alarm has passed, the step is dropped. If wrong, an alarm first seen at startup loses its future after-alarm steps, which can only cost a step.
13. Task 5 order. Every change: settle and ask `steps_to_run`, then save, then run (each run saves `ran` before the service call). Startup: load the store, observe the sensor, run `steps_after_restart` using the stored location and routine state, save, and only then read the tracker's current state, then evaluate normally. Otherwise `steps_to_run`'s drops are lost across a restart, or a phone that came home during downtime starts a step. No cost; it's the order the rules need.
14. A saved file that fails to load is logged and treated as no saved file. Otherwise the routine silently never starts and the household can't fix it. A fresh state has no stored location, so a restart starts nothing. If wrong, a step could repeat once for an alarm still ahead after a damaged file.
15. A step's service call never runs under the evaluation lock. Each run adds to `ran`, awaits the save, then starts the call as a tracked task that handles its own result. A long automation, or a script already running, otherwise stalls the home check, loses later steps or deadlocks a switch. If wrong, the event and `last_result` arrive slightly later than the start. This replaces the brief's plain blocking call under the lock.
16. At restart a step needs the stored location to be home AND the tracker's current real state, if it has one, to be home. `unavailable` or `unknown` is ignored as before. Spec anti-goal: never run when the phone is away, and the home check applies at that moment. This narrows ruling 13, which only stopped the came-home-during-downtime case. If wrong, a step is lost at a restart, which is the safe direction.
17. Settings changed before startup finishes are applied and saved, with no evaluation until startup has run. Otherwise they bypass the restart rule. If wrong, a change during boot takes effect a few seconds later.
18. Ruling 14 covers Store read failures as well as parse failures. A broad except around the load, logged with the traceback. The point is that the routine still starts. No cost.
19. The reviewer's "owner must rule" on the restart home check is settled by the spec's anti-goal, and pushing is authorized by the owner for this phase. Neither stops the run.
20. A phone with the sensor turned off is not listed, and the instructions are in the step description or the `no_phones` abort. Spec line 279 is corrected to match. The brief's exact text says "If a phone isn't listed", and picking a phone whose sensor is off would produce a routine that does nothing. If wrong, someone has to turn the sensor on first, which they must do anyway.
21. Turning the seconds check back on cancels the current alarm if its time equals the entry now rejected, through a new `rules.recheck_current`. Spec: an entry that isn't an alarm must not start anything. A cancelled record keeps `ran`, so turning the check off again doesn't repeat a step. If wrong, an alarm with non-zero seconds that someone really wants needs the check off, which is the setting's purpose. (Narrowed later: it cancels only when the entry fails the seconds check, not when another app has an entry at the same time.)
22. Imports become absolute across the integration. The plan's Global Constraints and the owner's global rule require them. The controller wrongly told implementers to use relative ones in Tasks 4 to 7, carrying over an exception that applies only to the Franklin-Home-Assistant repo. Cost: one mechanical commit.
23. Diagnostics report home or not home, not the zone name. These files go on public bug reports. No cost to debugging.
24. Task 8 has no separate review; the final whole-branch review reads the README against the code. One doc, and the budget was close. If wrong, a wrong README line is found later.
25. A rung alarm claims an entry up to 20 minutes after its latest time even when it isn't current. Spec: a snooze following a ring is the same alarm, and a step must not run twice. If wrong, a separate real alarm within 20 minutes after a rung one runs no pre-alarm steps, which the spec's 7:00 and 7:10 example already accepts.
26. `set_steps` limits offsets to -720 to 60, not 720. The record lasts 90 minutes, and a step past that was accepted and silently never ran. The plan's 720 can't be honoured without keeping records longer. If wrong, someone wanting a later step waits for a later phase.
27. `_schedule` gets the evaluation's `now`, not a fresh one, so a step due during the saves gets a timer. A past time fires at once, then re-evaluates with a fresh `now`.

## Samsung Clock and the whole-minute check

Found 2026-11-10 in 10 days of readings from one Samsung phone. It is not in the reviewed commits.

- On about half the mornings, Samsung Clock replaced the alarm with the same alarm 2 seconds later, some minutes before it rang.
- With the whole-minute check on, that entry is rejected and the alarm is treated as cancelled. Steps already run are not affected. Steps due after that point don't run, Skip next alarm is not used up, and a snooze that follows could run earlier steps again.
- With the check off, a replay of a real morning ran every step once and used up the skip.
- On that phone every entry came from Samsung Clock, so the check filtered nothing else.
- The owner's decision: turn the whole-minute check off for a routine that follows Samsung Clock. No code change for now. A possible later change is to stop treating a rejected entry within a few seconds of the current alarm as a cancel.

## Possible GitHub issues

Found by reviews and not fixed. None is filed. The owner confirms each one before it becomes an issue.

- Renaming the phone's location entity can leave the routine's stored location stuck on "home".
- A disabled location entity gives a routine that never runs and shows no error. `find_tracker` ignores disabled entities.
- Nothing is logged when a step runs, is blocked, or is dropped.
- Moving an alarm earlier counts as a new alarm, so a step that already ran can run again. Needs the owner's ruling on what should happen.
- If `_async_begin` fails before `_started` is set, the routine stays idle until it is reloaded. The only cause found is an `OSError` from `os.makedirs`.

## Deferred minor findings

Smaller review findings, kept for later phases. File and line numbers are as of the commit where they were found.

- Task 1: CI failed until `tests/ha` and `config_flow.py` existed (expected, now resolved). `pytest` is unpinned, copied from another of the owner's integration repos.
- Task 2: an unreachable `IN_THE_PAST` guard, and `test_stale_entry_doesnt_cancel_current` uses `WRONG_APP` (rules.py:98, test_alarms.py:252).
- Task 2: two records can share one alarm time when an earlier alarm's `latest` moves onto it (rules.py:109); lookup finds the older record first.
- Task 2: the connection-drop test cancels through a later entry, not `observe_no_alarm` (test_alarms.py:184). Task 5 tests `observe_no_alarm` end to end.
- Task 2: an entry between `time` and `latest` after a snooze becomes a new alarm (rules.py:109).
- Task 2: `unavailable` starting under 60 seconds before the alarm is recorded as a ring, not a cancel (rules.py:128). In the README's known limits.
- Task 2: a snooze chain past 90 minutes loses its record (rules.py:72).
- Task 3: `next_wakeup` includes steps in `ran` or `dropped`, which causes one harmless extra wakeup. The `seen_late` exclusion in `next_wakeup` has no test (rules.py:219-225).
- Task 3: a step dropped at restart stays dropped after the alarm moves (rules.py:202). Starts nothing.
- Task 3: the phone replay tests leave out a few logged entries (test_phone_replays.py).
- Task 3: two tests run the clock backwards (test_steps.py around line 264, test_phone_replays.py).
- Task 3: removal at the exact instant (rules.py:82, :220). Handled by Task 5 passing `utcnow`.
- Task 3: a lost step can't be retimed later for the same alarm, because `dropped` is matched by item. Starts nothing, lasts one morning. Accepted in ruling 9.
- Task 3: no test that a disabled step is dropped at once on a `seen_late` alarm (rules.py:175-177).
- Task 4: a chosen clock on the never-offered list stays offered, with no test (clocks.py:21-22). A weak name assertion (test_clocks.py:41-42). No round-trip test outside UTC; a one-off script showed it correct (test_storage.py:16).
- Task 5: a stale save after a stop during the startup run (routine.py:219).
- Task 5: no test that a listener hears a step result. Applied-and-saved during startup has no assertion. The started-path test would pass if begin never ran. No named-zone test at restart.
- Task 5: the no-alarm task doesn't re-check the sensor (routine.py:289 at c2a188d, connect the rules to Home Assistant), which now needs a lock hold during a save.
- Task 5: `ran` belongs to one alarm record. Clock A to B to A with a moved alarm can repeat a pre-alarm step (rules.py:146).
- Task 5: a time without a time zone in a hand-edited file raises on every evaluation.
- Task 6: turning the seconds check off doesn't pick up an alarm already on the sensor until it next changes or a restart. (Task 7 added an update listener that re-reads the sensor.)
- Task 7: a leftover Store file if an entry is deleted during a save (`routine_store` in routine.py). A step dropped by the restart rule stays dropped if retimed (rules.py:173). No entity-level test of state updating when startup finishes; no reload-then-options test; no test of a stop during the evaluation save.
- Task 7: the seconds check turned on while the sensor is `unavailable`, or shows a different time, leaves a rejected entry current (routine.py:343-350, rules.py:154).
- Task 7: `last_result` holds free text from a failed step's error, and diagnostics include it (routine.py:275).

## Not yet seen on a real phone

These come from reading source code or from one night of readings. Task 9 steps 5 and 6 are the first chance to see them.

- What the sensor shows when someone taps Snooze on a Samsung Clock alarm.
- What the sensor shows when no alarm is set. The spec's finding 8 says `unavailable` for 60 seconds or longer; that was read from source only.
- Whether Samsung writes non-alarm entries on :00 seconds.
- Whether the location tracker says "away" overnight while the phone charges with Wi-Fi off.
- How late an alarm rings after its time, and how far the phone's clock differs from the server's.
- Whether the `Package` attribute survives a Home Assistant restart.
- The manufacturer string used to offer Samsung Clock in the clock list.
- A real labelled script starting.
- Whether HACS will download from the default branch when the repo has no release.

## Cost

The plan's budget line was 1 session and about 500k tokens. By per-agent figures, not counting the controller, the first stretch used about 740k (Tasks 1 to 3). After that budget stop, the owner said to keep building with a second line of about 1.5M, and the second stretch used about 1.56M (Tasks 4 to 9 step 3).
