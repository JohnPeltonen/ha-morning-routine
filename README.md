# Morning Routine

A Home Assistant integration that runs scripts, scenes and automations around the alarm on an Android phone. For example, it can start a heater 30 minutes before the alarm goes off.

Each phone gets its own routine. A person can turn their routine on or off, skip the next alarm, and choose which clock app to follow, without building anything.

**This version is set up by an admin.** A dashboard card for adding, removing and retiming steps is coming. Until then, an admin sets the steps with a service call, described below.

## Before you install

- **Android only.** iPhones don't have the next alarm sensor this depends on.
- **Limited testing.** The rules come from one night of readings from two Samsung Galaxy S25-series phones. Other phones may behave differently. If yours does, please open an issue.

## Install

1. In HACS, add `https://github.com/JohnPeltonen/ha-morning-routine` as a custom repository of type Integration, then download Morning Routine.
2. Restart Home Assistant.
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

Anyone logged in to Home Assistant can use the switches and the clock picker. Only an admin can change the steps.

## Set the steps

A step can be a script, scene or automation.

1. Create a label named `morning routine` under Settings, Areas, labels & zones. The integration doesn't create it.
2. Apply that label to each item you want to use as a step. Items without the label don't run.
3. Call `morning_routine.set_steps` from Developer tools, Actions:

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

- `offset_minutes` is the time from the alarm, from -720 to 720. A negative number is before the alarm.
- `enabled` is optional and defaults to true.
- The call replaces all the steps of that routine. If any step is refused, nothing changes.

Each step runs once per alarm.

## How it decides

- **Home only.** A step runs only when the phone's location is exactly `home`. If the phone briefly reports `unavailable` or `unknown`, the last real location is used. A zone drawn on your property, such as a yard, counts as away and blocks steps.
- **Alarms only.** The sensor also reports things that aren't alarms. The integration follows only the chosen clock, and only entries set to a whole minute. An admin can turn off the whole-minute check under the integration's Configure button.
- **Catching up.** If a step's time passes while it is blocked, it runs as soon as the block clears, as long as the alarm is still ahead. This means **turning something on can start a step right away**. That includes the routine switch, Skip next alarm, the clock picker, coming home, or setting steps.
- **After the alarm.** There is no catching up once the alarm has gone off. A step more than 10 seconds late at that point is dropped, and so is every step of an alarm first seen after its time.
- **Restarts.** After a restart, a step runs only if it is less than 5 minutes late and the phone was home before the restart and still is. Otherwise it is dropped.

## Known limits

- **Hidden alarms.** The sensor shows only the soonest entry. An alarm cancelled while hidden behind another entry can't be detected, so its steps may still run.
- **A late start for a hidden alarm.** An alarm hidden behind another entry appears only when that entry passes, so its steps may start late.
- **Sensor outage near the alarm.** If the sensor goes `unavailable` less than 60 seconds before the alarm, the alarm is treated as having gone off, not as cancelled.
- **Shared scripts.** A script in `single` mode that is already running ignores a new start, but the step is still recorded as `started`.
- **Automation results.** An automation step reports `started` only when the automation finishes, so results can arrive late and out of order.

## Other projects

These projects came first and are worth a look:

- [Sunrise Alarm](https://github.com/rationalRobots/haos-sunrise-alarm) filters by source app and time of day, and documents the hidden-alarm problem. It requires a lamp.
- [Phone Alarm Sync](https://github.com/joshuaaaaa/HA_budik) offers a clean sensor with an offset, on/off for any entity, and stale-phone detection.

## License

MIT
