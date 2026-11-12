# Morning Routine

A Home Assistant integration that runs scripts, scenes and automations around the alarm on an Android phone. For example, it can start a heater 30 minutes before the alarm goes off.

Each phone gets its own routine. A person can turn their routine on or off, skip the next alarm, and choose which clock app to follow, without building anything.

Steps are added, retimed, turned off and removed from a dashboard card. Anyone logged in to Home Assistant can use it. An admin does the one-time setup below.

## Before you install

- **Android only.** iPhones don't have the next alarm sensor this depends on.
- **Limited testing.** The rules come from one night of readings from two Samsung Galaxy S25-series phones. Other phones may behave differently. If yours does, please open an issue.

## Install

1. On Home Assistant 2026.11 or newer, go to Settings, Marketplace, choose Add from link, and enter `https://github.com/JohnPeltonen/ha-morning-routine`. Then download Morning Routine. On older versions, add the same address in HACS as a custom repository of type Integration.
2. Restart Home Assistant. Every update of this integration also needs a restart.
3. In the Home Assistant Android app, go to Settings, Companion app, Manage sensors. Turn on **Next alarm**, and leave that sensor's **Allow list** off.
4. In Home Assistant, go to Settings, Devices & services, Add integration, and choose Morning Routine. Pick the phone.

Each routine has these entities:

| Entity | What it does |
|---|---|
| Routine | Turns the routine on or off. It starts off. |
| Skip next alarm | Cancels the steps for the next alarm, then turns itself off when that alarm goes off. |
| Clock to watch | The clock app to follow. Nothing runs until one is chosen. |
| Current alarm | The alarm being followed (diagnostic). |
| Last ignored entry | The last sensor value that was ignored, and why (diagnostic). |

Anyone logged in to Home Assistant can use the switches and the clock picker, and can change the steps from the card.

## Choose what a step may run

A step can be a script, scene or automation. An admin decides which ones are offered:

1. Create a label named `morning routine` under Settings, Areas, labels & zones. The integration doesn't create it.
2. Add that label to each script, scene or automation that may be used as a step. Items without the label aren't offered and don't run.

## Add the card to a dashboard

The integration loads the card by itself. There is no dashboard resource to add.

1. Edit a dashboard, choose Add card, and pick **Morning Routine**.
2. Choose the routine in the card's settings.

In YAML, the card is:

```yaml
type: custom:morning-routine-card
routine: 0123456789abcdef0123456789abcdef
```

`routine` is the routine's config entry id. The card's settings form fills it in for you.

## Use the card

The card shows the routine as a timeline. Steps before the alarm are above the word Alarm, and steps at or after it are below.

- **The switch at the top** turns the whole routine on or off.
- **+ Add a step** opens a form. Choose what should happen, and how many minutes before or after the alarm. A step can be up to 720 minutes before the alarm and up to 60 minutes after it.
- **Tap a step's name** to change its time, change what it runs, or remove it.
- **The switch beside a step** turns that one step off without removing it.
- **Skip next alarm** and **Clock to watch** work the same as the entities above.

Each step runs once per alarm. Each script, scene or automation can be a step once per routine.

If something needs attention, the card says so in a sentence. For example, it says when no clock is chosen, or when a step's script was deleted or lost the label.

If the card doesn't appear in the card list after an update, refresh the browser, or close and reopen the Home Assistant app.

## For admins and scripts

The action `morning_routine.set_steps` replaces all the steps of one routine. Only an admin can call it. The card doesn't need it, and it may be removed in a later version.

```yaml
action: morning_routine.set_steps
data:
  config_entry_id: 0123456789abcdef0123456789abcdef
  steps:
    - item: script.start_the_heater
      offset_minutes: -30
    - item: scene.kitchen_lights_dim
      offset_minutes: 0
      enabled: false
```

- `offset_minutes` is the time from the alarm, from -720 to 60. A negative number is before the alarm.
- `enabled` is optional and defaults to true.
- If any step is refused, nothing changes.

## How it decides

- **Home only.** A step runs only when the phone's location is exactly `home`. If the phone briefly reports `unavailable` or `unknown`, the last real location is used. A zone drawn on your property, such as a yard, counts as away and blocks steps.
- **Alarms only.** The sensor also reports things that aren't alarms. The integration follows only the chosen clock, and only entries set to a whole minute. An admin can turn off the whole-minute check under the integration's Configure button.
- **Catching up.** If a step's time passes while it is blocked, it runs as soon as the block clears, as long as the alarm is still ahead. This means **a change can start a step right away**: turning the routine on, turning Skip next alarm off, choosing a clock, coming home, or adding or retiming a step.
- **After the alarm.** There is no catching up once the alarm has gone off. A step more than 10 seconds late at that point is dropped. An alarm first seen more than 5 seconds after its time runs no steps.
- **Snoozes.** An entry up to 20 minutes after an alarm counts as the same alarm, so nothing runs again. A 7:00 with a 7:10 backup runs one routine, and a 7:00 with a 7:30 backup runs two.
- **Restarts.** A step that came due while Home Assistant was restarting runs only if it is less than 5 minutes late, the phone was home before the restart, and the phone doesn't now report somewhere else. Otherwise it is dropped.
- **Turning it off.** Turning the routine off stops steps that haven't started. It doesn't undo one that has.

## Known limits

- **Hidden alarms.** The sensor shows only the soonest entry. An alarm cancelled while hidden behind another entry can't be detected, so its steps may still run.
- **A late start for a hidden alarm.** An alarm hidden behind another entry appears only when that entry passes, so its steps may start late.
- **Sensor outage near the alarm.** If the sensor goes `unavailable` less than 60 seconds before the alarm, the alarm is treated as having gone off, not as cancelled.
- **A phone that dies at home.** It still counts as home, because its last real location was home.
- **Scripts with input fields.** These aren't supported as steps, because a step passes no values.
- **Moving an alarm earlier.** That counts as a different alarm, so a step that already ran can run again.
- **Renaming entities.** Renaming the phone's next alarm sensor or location entity breaks the routine. Remove the routine and add it again.
- **Shared scripts.** A script in `single` mode that is already running ignores a new start, but the step is still recorded as `started`.
- **Automation results.** An automation step reports `started` only when the automation finishes, so results can arrive late and out of order.

## Other projects

These projects came first and are worth a look:

- [Sunrise Alarm](https://github.com/rationalRobots/haos-sunrise-alarm) filters by source app and time of day, and documents the hidden-alarm problem. It requires a lamp.
- [Phone Alarm Sync](https://github.com/joshuaaaaa/HA_budik) offers a clean sensor with an offset, on/off for any entity, and stale-phone detection.

## License

MIT
