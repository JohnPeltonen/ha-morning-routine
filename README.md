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

## Choose which scripts a step may run

Lights and thermostats can be steps with no setup. Scripts, scenes and automations can be steps only when an admin offers them:

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
- **+ Add a step** opens a form built from Home Assistant's own controls. Choose what should happen from the list, which has a search box. Then choose how many minutes before or after the alarm. A step can be up to 720 minutes before the alarm and up to 60 minutes after it.
  - A light or a thermostat that can be turned on and off shows **Turn on** and **Turn off** buttons.
  - A setting that can be left out, such as a light's brightness, has a checkbox. Tick it to get a slider. Leave it unticked and the setting is left as it was.
  - Each slider runs between the device's own lowest and highest setting. The box beside it takes a typed number.
- **Tap a step's name** to change its time, change what it does, or remove it.
- **The switch beside a step** turns that one step off without removing it.
- **Skip next alarm** and **Clock to watch** work the same as the entities above.

Each step runs once per alarm.

After an update, a browser that was already open can still hold the old card. The card then shows "Morning Routine was updated. Reload this page to finish the update." Reload the page. Home Assistant keeps a saved copy of each page, so it can take two reloads.

### What a step can be

- **A light.** Turn it on or off. Turning on can set a brightness from 1 to 100 percent if the light dims. Leave Brightness unticked and the light comes on as it was last.
- **A thermostat with one temperature,** such as a heater. Turn it on or off. Turning on can set a temperature. Leave Temperature unticked and it starts at its last setting.
- **A thermostat with a "heat to" and a "cool to" temperature.** The step sets both. It doesn't turn the thermostat on or off. In heat mode only "heat to" is used, and in cool mode only "cool to". If the thermostat is off, the step fails and changes nothing.
- **A script, scene or automation** that has the "morning routine" label. Each can be a step once per routine.

Lights and thermostats need no label, and any logged-in account can add them. A light or thermostat can be a step more than once, for example on before the alarm and off after it.

A step never puts a setting back. A temperature or a light stays as the step left it until something else changes it.

Other device types, such as switches, locks and garage doors, can't be steps. Put those in a script and give the script the label.

If something needs attention, the card says so in a sentence. For example, it says when no clock is chosen, or when a step's script or device was deleted.

If the card doesn't appear in the card list after an update, refresh the browser, or close and reopen the Home Assistant app.

The card's switches and its form use controls that are part of Home Assistant. If a later Home Assistant release moves them, the card still shows the routine and its switches still work, drawn in the card's own style. The form then says "This form couldn't load Home Assistant's controls." Please open an issue if you see that.

## For admins and scripts

The action `morning_routine.set_steps` replaces all the steps of one routine. Only an admin can call it. The card doesn't need it.

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
    - item: light.bedside_lamp
      offset_minutes: -10
      action: turn_on
      brightness: 30
    - item: climate.hallway
      offset_minutes: -5
      action: set_temperature
      heat_to: 68
      cool_to: 74
```

- `offset_minutes` is the time from the alarm, from -720 to 60. A negative number is before the alarm.
- `enabled` is optional and defaults to true.
- A light or thermostat step needs an `action`: `turn_on`, `turn_off` or `set_temperature`. `turn_on` may have `brightness` for a light or `temperature` for a thermostat. `set_temperature` needs `heat_to` and `cool_to`.
- A light or thermostat step gets an `id` the first time it is saved. A list sent without ids keeps them, matched by item and action.
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
- **A thermostat step that half works.** Turning a thermostat on and setting its temperature are two actions. If the second fails, the thermostat is on at its old temperature and the step is recorded as `failed`.
- **Shared scripts.** A script in `single` mode that is already running ignores a new start, but the step is still recorded as `started`.
- **Automation results.** An automation step reports `started` only when the automation finishes, so results can arrive late and out of order.

## Other projects

These projects came first and are worth a look:

- [Sunrise Alarm](https://github.com/rationalRobots/haos-sunrise-alarm) filters by source app and time of day, and documents the hidden-alarm problem. It requires a lamp.
- [Phone Alarm Sync](https://github.com/joshuaaaaa/HA_budik) offers a clean sensor with an offset, on/off for any entity, and stale-phone detection.

## License

MIT
