# Morning Routine integration: design

Date: 2026-11-01. Status: approved by the owner with the changes recorded here. Nothing is built.

"Owner" is the person this was built for. "User" is anyone in a household who has a routine, including someone who is not comfortable with technology. Anything marked "Builder's call" is a decision the owner hasn't specifically reviewed.

## Why this exists

The owner wants things in the house to happen around each person's phone alarm, without anyone keeping a second schedule. Change the alarm on the phone, and the routine follows.

The owner's own examples:

- Start the steam shower 30 minutes before the alarm.
- Play the radio softly in the kitchen the next time there's motion there.
- Later, turn the kitchen lights on dim.

Home Assistant's Android app already reports each phone's next alarm, but the sensor can't be used directly. On Samsung phones it also reports entries that aren't alarms, and it can hide a real alarm behind them. See "What the phones actually do".

Other people have built parts of this, but nothing found combines all of it. See "Prior art".

**Success:** a household member who will never build an automation can turn their routine on and off, choose the clock to watch, and add, remove or retime steps from their dashboard. The routine runs for real alarms and stays quiet for everything else.

## Goals

- A public Home Assistant custom integration, installable as a custom repository in HACS.
- One routine per phone. Each has an on/off switch, a clock to watch, and a list of steps.
- A step pairs something to run with a time to run it.
- A dashboard card that non-admin users can use to change all of this. The layout is in "The card".
- Filtering that handles the phone behavior recorded in this document.

## Non-goals

- iPhones. They don't have the next-alarm sensor. The README says so.
- Knowing what a step does. The integration knows nothing about showers, radios or lights. Steam-specific behavior, such as restarting a run that's already going, belongs in the owner's script.
- Building or editing scripts from the card. The owner builds them once in Home Assistant.
- Reading, setting, snoozing or dismissing alarms on the phone. The sensor is read-only.
- Working out who walked into a room. See "Motion steps".
- Showing clock times in the card. See "The card".

## Anti-goals

These would make it a failure even if everything else worked.

- **A routine must never run when its phone is away.** The check is built in. There is no setting anywhere to turn it off, and no way to bypass it. The owner doesn't want it turned off by accident. The risk is a heater starting while nobody is home.
- **A brief glitch must not cost someone their morning.** The rule in "The home check" exists for this.
- **A restart, reload or reconnect must not start anything by itself.**
- **A step must not run twice for one alarm.**
- **A non-admin user must not be able to reach every script in the house.** Only items with the label can be chosen. See "What a step can run".
- **No red or alarm-style coloring in the card.** A skipped step or a phone that's away is information, not a warning.

## Constraints

- Home Assistant 2026.10.0 or newer, and Python 3.14. Forms use `probatio`, not `voluptuous`.
- Android companion app, with the next-alarm sensor turned on. It's off by default.
- Follow the layout and tooling of the owner's `ha-amerec-steam` repo: `hacs.json`, `pyproject.toml`, `requirements_test.txt`, `requirements_test_ha.txt`, and GitHub Actions for hassfest and tests. Pin `pytest-homeassistant-custom-component` to the version for 2026.10.0, which is 0.13.371.
- The owner develops on native Windows, where Home Assistant doesn't run. Keep the alarm rules in a module with no `homeassistant` imports, so their tests run locally. Everything else is tested in GitHub Actions.
- Public repo: no household names, addresses, entity IDs from the owner's house, or real phone identifiers in code, docs or test data. Test data uses made-up values.
- Code style: snake_case, absolute imports, `logger = logging.getLogger(__name__)` with %-style formatting, `T | None`, minimal docstrings. Use `type`, never `kind`, for a category field.
- Plain language in the card and README, written for someone reading cold.

## What the phones actually do

This is the evidence behind the rules. It comes from one night of Home Assistant history, 2026-10-31 to 2026-11-01, from two Samsung Galaxy S25-series phones. The README must say the evidence is this small, and that other phones may behave differently.

**The sensor.** `sensor.<phone>_next_alarm` is a timestamp. It has a `Package` attribute naming the app, and a `Local Time` attribute. Android gives the app only the single soonest entry.

**Entries seen on the first phone**, which uses Sleep mode and Samsung Routines:

| Entry time | Package | What it was |
|---|---|---|
| 22:30:03 | `com.sec.android.app.clockpackage` | Not an alarm |
| 22:30:08 | `com.samsung.android.app.routines` | Not an alarm |
| 22:39:00 | `com.google.android.deskclock` | Real test alarm |
| 00:41:50 | `com.samsung.android.app.routines` | Not an alarm |
| 07:00:03 | `com.sec.android.app.clockpackage` | Not an alarm |
| 07:30:00 | `com.samsung.android.app.routines` | Not an alarm |
| 07:30:05 | `com.samsung.android.app.routines` | Not an alarm |
| 09:00:00 | `com.google.android.deskclock` | Real alarm |
| 21:00:00 | `com.samsung.android.app.routines` | Not an alarm |

**Entries seen on the second phone**, which uses Samsung Clock for its alarms:

| Entry time | Package | What it was |
|---|---|---|
| 06:42:00 | `com.sec.android.app.clockpackage` | Real alarm, later moved |
| 09:03:00 | `com.sec.android.app.clockpackage` | Real alarm |
| 09:08:00 | `com.sec.android.app.clockpackage` | Shown for 11 seconds after 09:03. Probably a snooze; not yet confirmed |

**What follows from this:**

1. **Neither check is enough alone.** Filtering by app misses the Samsung Clock entries that aren't alarms. Requiring :00 seconds misses the Routines entries at 07:30:00 and 21:00:00. Together, they accept every real alarm above and reject every entry that isn't one.
2. **The phone's own Allow list doesn't help.** It hides updates but doesn't reveal the alarm behind them. The sensor then holds its old value, and in testing a 22:39 alarm stayed on the sensor until the Allow list was removed at 23:28. Filtering must happen in the integration, with the Allow list off.
3. **A real alarm can be hidden.** The 09:00 alarm only appeared at 07:30:05, when the entry in front of it passed. An alarm that appears late can leave less notice than a step wants.
4. **Updates are fast.** Each new entry arrived within about a second of the previous one passing.
5. **Daylight saving is handled by the sensor.** The state is in UTC and stayed correct across the clock change that night.
6. **Short `unavailable` blips happen.** The tracker went `unavailable` 8 times, for 14 to 34 milliseconds, and `person` entities showed `unknown` for the same moments. Several sensors on the phone dropped together, so these look like the phone's connection to Home Assistant reloading, not a loss of location. Some lined up with a sensor being turned on, and two aren't explained. In the 10 days before that night there were none.
7. **Values repeat.** The same alarm is re-reported after a Home Assistant restart.
8. **"No alarm" looks like a blip.** This comes from reading source code, not from that night, because both phones always had an entry. With no alarm set, the Android app's `NextAlarmManager.kt` sends the state `unavailable`, with an empty `Package` and `Time in Milliseconds` of 0. Home Assistant's `mobile_app` entity then marks the sensor unavailable, and an unavailable entity's extra attributes are dropped. So the only way to tell "no alarm" from a blip is how long it lasts. Confirm this on a real phone with no entries during the live test.

## How it works

### Which entries count

An entry counts as a real alarm only if all of these are true:

- Its `Package` matches the clock chosen for this routine.
- Its time is on :00 seconds. This check is on by default. An admin can turn it off per routine in an advanced setting.
- It's a real timestamp, not `unavailable` or `unknown`.

Every other entry is ignored, and the most recent one is recorded with the reason. See "Diagnostics".

### Knowing what happened to an alarm

The sensor changes as soon as an alarm rings, so the integration has to keep its own record of the current alarm. Steps after the alarm depend on this.

Because Android only reports the soonest entry, a new sensor value says something about the alarm being tracked. Builder's calls, all of them:

| New sensor value | What it means | What happens |
|---|---|---|
| Same time as the current alarm | A repeat | Nothing |
| Counts, and is up to 20 minutes after the current alarm | Same alarm: a snooze or a small edit | Keep the record of what ran. Don't run anything again |
| Counts, and is earlier than the current alarm or more than 20 minutes after it | A different alarm | That alarm becomes current, and its steps are scheduled |
| Doesn't count, and is earlier than the current alarm | The current alarm may just be hidden | Keep the current alarm |
| Doesn't count and is later, before the alarm time | The alarm was cancelled | Drop steps that haven't run. Steps that ran aren't undone |
| `unavailable` for 60 seconds or longer, before the alarm time | The phone has no alarm set | Same as cancelled |
| `unavailable` for less than 60 seconds, or `unknown` | Nothing is known | Ignore it and keep the current alarm |
| Any other change at or after the alarm time | The alarm rang | Keep going with the remaining steps and any open motion window |

**How these rules fit together:**

- **First match wins, from the top of the table.** A snooze that follows a ring is the same alarm, not a new one.
- **The phone's clock may differ slightly from Home Assistant's.** A change within 5 seconds before the alarm time counts as the alarm ringing.
- **The 60 seconds is a margin over what was measured.** The longest blip recorded was 34 milliseconds.
- **The record of what ran is kept until the alarm's motion window would have closed.** If an alarm is cancelled and the same time comes back, as after a connection drop longer than 60 seconds, it's the same alarm and nothing runs twice.
- **A new alarm doesn't cancel an old one's remaining steps.** If an alarm's after-alarm steps or motion window are still open when the next alarm becomes current, both carry on.

**The cost of the hidden-alarm rule:** an alarm cancelled while it's hidden can't be detected, so its steps may still run.

A 20-minute gap means a 7:00 with a 7:30 backup runs two routines, and a 7:00 with a 7:10 backup runs one. The owner hasn't said how often this comes up.

### Time steps

A time step runs at the alarm time plus an offset. Negative is before the alarm and positive is after it.

- **Seen late.** If the alarm appears after the step's time has passed and the alarm is still ahead, the step runs right away. This handles hidden alarms. If the alarm has already passed, the step is dropped.
- **Blocked, then cleared.** If a step's time passes while something is blocking it, it runs as soon as the block clears, as long as the alarm is still ahead. The owner chose this over waiting for the next alarm. With a 7:00 alarm and a 6:30 step, any of these at 6:45 runs the step right away:
  - The routine is turned on, a clock is chosen, or Skip next alarm is turned off.
  - The step's toggle is turned on.
  - The step is added, or retimed to a time that has already passed.
  - The phone comes home.

  Limits on this rule:
  - Once the alarm has passed, the step is dropped.
  - A step that already ran for this alarm doesn't run again, even if it's retimed, or removed and added back. A step is matched by the item it runs. Builder's call.
  - The home check still applies at that moment.
  - Only a real change clears a block. A restart, reload or reconnect doesn't. Builder's call. To tell a real arrival from a restart, the last real location is saved with `Store`.
- **Missed because Home Assistant was down.** If the step's time passed during downtime, it runs if it's less than 5 minutes late and is dropped otherwise. Builder's call. An alarm first seen during startup follows this rule, not the "seen late" rule, so that a restart can't start things.
- **Times aren't fixed in advance.** If an edit moves the alarm, steps that haven't run move with it.

### Motion steps

A motion step runs on the next motion from a sensor the user picks, within a window.

- **The window opens** at an offset the user chooses before the alarm. If the alarm is at 9:30 and the offset is 60 minutes, motion at 8:50 starts the step and motion at 3am doesn't.
- **The window closes** 90 minutes after the alarm. The owner chose this.
- **A sensor already on when the window opens** counts as motion. Builder's call.
- **If the phone is away when motion happens,** the step doesn't run, and the window stays open in case the person comes home.
- **If a step is blocked when its window opens** by anything else, such as its toggle being off, it starts watching for motion once the block clears, as long as the window is still open.

**Known limit, accepted by the owner:** motion can't tell who walked in. If someone else walks through the kitchen during the window while the alarm's owner is asleep, the step runs anyway. The offset is how a user controls this for now.

A later version might also require the phone to show its owner is up, such as being unplugged or having the screen on. The evidence so far is one morning. Don't build this now.

Any `binary_sensor` with a device class of `motion`, `occupancy` or `presence` can be picked. Some sensors only report in certain states. Blink cameras, for example, fired only while armed during 11 days of the owner's history. The README should warn about this.

### The home check

Each step checks for itself, at the moment it would run. If the person leaves after the first step, later steps don't run. If they come back while the alarm is still ahead, those steps catch up. See "Blocked, then cleared" under "Time steps".

- The check uses that phone's own `device_tracker`. Another person being home doesn't count.
- The location used is **the last real one**. `unavailable` and `unknown` are ignored, however long they last.
- **Only `home` allows a step to run.** A tracker inside another named zone reports that zone's name, not `not_home`, so `not_home` and any named zone both block a step. There's no list of extra allowed zones, because nothing may bypass this check. A zone drawn on the property, such as a yard, would therefore block steps, and the README should say so.
- If there has never been a real location, the step doesn't run.

**The cost:** a phone that dies at home and is then carried out still counts as home. The owner's data shows updates at least about every 30 minutes while home, and 19 departures in 11 days, none before 7:03am.

### Skip next alarm

A switch per routine, on the owner's approved card layout. It's tied to an alarm, not to a day or a clock time. The first two rules are the owner's decision. The rest are builder's calls.

- **Turned on before the alarm goes off:** every step that hasn't run for that alarm is cancelled, including steps after the alarm and motion steps.
- **Turned on after the alarm has gone off:** that alarm's remaining steps carry on, and the skip applies to the next alarm.
- **After the skipped alarm goes off,** the switch turns itself off. The cancelled steps stay cancelled, and a snooze doesn't bring them back.
- **Turned off by a person before the alarm goes off:** the steps come back, and any that are overdue run right away. See "Blocked, then cleared" under "Time steps".
- **If no alarm is known when it's turned on,** such as when the real alarm is hidden, it applies to the next alarm that counts.
- **If the alarm is cancelled or replaced,** the switch stays on and applies to whichever alarm goes off next.

### What a step can run

- Scripts, scenes and automations that have a Home Assistant label named "morning routine". The owner chose this. Otherwise, "Everything Off" would be one tap away in a morning routine.
- Scripts are started without waiting for them to finish. Automations are triggered, and scenes are turned on. Builder's call.
- A script that needs input fields isn't supported.
- **The check runs on the server,** not just in the card. A request naming an item without the label is refused.
- If an item is later deleted or loses its label, the step stays on the list, doesn't run, and the card says so in plain words. Builder's call.
- If a step fails, log it, record it in diagnostics, and carry on with the other steps.
- If the label doesn't exist yet, the card explains that an admin needs to create it. The integration doesn't create it. The owner confirmed this.

### Each step runs once per alarm

This was the owner's decision. What ran is saved to disk with Home Assistant's `Store`, along with the current alarm, so that a restart can't repeat a step.

### Two phones

Routines run independently. Two routines can run the same script on one morning, and that script has to cope with it.

## The card

The owner chose this layout from mockups. **Everything is relative to the alarm.** No clock times appear anywhere, because the integration can't always know when the alarm is: a real alarm can be hidden, as described above. Don't add a "next alarm" line.

```
+--------------------------------------------+
| <Person>'s morning routine           [on]  |
| Runs around each alarm from the clock      |
| below, only when <Person>'s phone is home  |
+--------------------------------------------+
|  30 min before  o Start the steam     [on] |
|                 |                          |
|  From 30 min    o Play the radio      [on] |
|  before         | On the next kitchen      |
|                 | motion                   |
|                 |                          |
|                 O Alarm                    |
|                 |                          |
|  At alarm       o Kitchen lights dim  [off]|
|                                            |
|            + Add a step                    |
+--------------------------------------------+
| Skip next alarm                      [off] |
| Clock to watch                             |
| [ Samsung Clock                        v ] |
+--------------------------------------------+
```

- A timeline with the alarm as the fixed point. Steps are sorted by when they run.
- **Every step has its own toggle.** A step that's off stays in place, greyed out.
- Tapping a step's name opens the same form as "Add a step", with a way to remove it.
- Designed for a phone first, at about 360 pixels wide.

**The add-a-step form:**

- What should happen: a dropdown of items with the label.
- When: "At a time around the alarm" or "The next motion".
- For a time: minutes before or after the alarm.
- For motion: which sensor, and how long before the alarm to start watching.

**The clock dropdown:**

- It shows plain names, such as "Samsung Clock" and "Google Clock".
- Google Clock is offered on every phone. Samsung Clock is offered only on a Samsung phone, or on a phone that has reported it. The owner chose this for Samsung Clock.
- It adds any other app that phone has reported, read from the sensor's history, showing the package name if there's no known plain name.
- Known non-clock apps, such as Samsung Routines, aren't offered. Builder's call.
- A routine has one clock. It stays off until a clock is chosen. Builder's call.

**Problems shown in plain words,** with no red: the phone's next-alarm sensor is off or missing, a step's item is no longer available, or the sensor has shown a time well in the past, which usually means the phone's Allow list is on. Builder's call on the wording and on how long "well in the past" is.

## Who can change what

The owner's server has a non-admin user account, so this is a real requirement.

| Change | Who | Where |
|---|---|---|
| Add a phone, remove a routine, the :00 advanced setting | Admin | Integration settings |
| On/off, clock, skip, steps | Anyone logged in | The card |

Integration settings screens are expected to be admin-only, so the card uses the integration's own WebSocket commands, without the admin requirement. Builder: confirm this in Home Assistant's source. Anyone logged in can edit any routine, with no per-person lock. The owner chose this. If a phone is lost while its owner is travelling, the person at home must still be able to shut that routine off.

## Setup

- Config flow: one config entry per phone. It lists phones with a next-alarm sensor from the `mobile_app` integration. A phone with the sensor turned off is listed with instructions for turning it on, and for making sure the Allow list is off.
- The routine's name comes from the `person` linked to that phone's tracker, or the phone's name if there isn't one. Builder's call.
- The integration registers the card itself, so nobody has to add a dashboard resource by hand. Builder: confirm the current way to do this for version 2026.10.

## Entities and events

One device per routine. Builder's call on the exact names.

- Switch: routine on/off.
- Switch: skip next alarm.
- Select: clock to watch.
- Sensor, diagnostic: last ignored entry, with its time, package and reason as attributes.
- Sensor, diagnostic: current alarm, a timestamp. It can be wrong while an alarm is hidden, so the card doesn't use it.
- Event: `morning_routine_step_ran`, with the routine, step, item and result. Anything fancier than a step can trigger from this.

Steps aren't entities. They're stored with `Store` and changed through the WebSocket commands.

## Testing

- **The alarm rules** have no `homeassistant` imports and run locally. Tests replay the sequences in "What the phones actually do" as fixtures and check what would run, including the hidden alarm, the probable snooze and the blips. Fixtures use made-up phone names.
- **Integration tests** run in GitHub Actions: setup, entities, the WebSocket commands including refusal of unlabeled items, the home check, and restart behavior.
- **The card:** builder's call on how to test it, and it should be checked on a real phone before release.
- **A live test on the owner's server** comes last, with a harmless script before any real one.

## Prior art

Both of these are MIT licensed. Ideas and code can be reused with credit.

- [Sunrise Alarm](https://github.com/rationalRobots/haos-sunrise-alarm) filters by source app and time of day, starts late when an alarm appears late, and documents the hidden-alarm problem. It requires a lamp, and it doesn't handle non-alarm entries from Samsung Clock.
- [Phone Alarm Sync](https://github.com/joshuaaaaa/HA_budik) offers a clean sensor with an offset, on/off for any entity, and stale-phone detection. It doesn't filter by source app, and its README is in Czech.

## Delivery

Each phase gets its own plan and approval.

The owner wants one routine running at home while the owner is away for a few days, and intends to adjust it through use. So the first phase ends with a real install, before the card exists.

1. **Rules, settings and first install:** the repo tooling, the alarm rules with their tests, setup, entities, and running time steps with the home check. Steps are set by an admin through a temporary service until the card exists. The routine switch and the skip switch are ordinary entities, so a non-admin user can use them from a dashboard. Install on the owner's server and test with a harmless script before any real one. Installing needs a restart, so ask the owner first, take a backup, and coordinate with any other Claude session working on that server.
2. **The card and motion steps:** the WebSocket commands, the card and its registration, and motion steps. The owner's house has no motion sensor that works while people are home, so motion steps wait until now.
3. **Release:** check the card on a real phone, update the README and publish. The owner does all pushing.

**Not part of this repo:** the owner's scripts, the label on them, placing the card on the owner's dashboard, and a kitchen motion sensor that works while people are home. The owner's Blink cameras don't do this. Motion steps can't work in the owner's kitchen until there is one.

## Left to the builder

File layout, class names, entity names, translation text, offset ranges and increments, the card's framework and exact styling within the layout above, and how the WebSocket commands are shaped.
