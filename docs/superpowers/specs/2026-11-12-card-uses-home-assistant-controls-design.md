# The card uses Home Assistant's own controls: design

Date: 2026-11-12. Status: draft. A fresh reviewer read it as a builder on 2026-11-12, and its questions are settled below except one. Waiting for the owner to answer "Open question for the owner" and then approve this document. Nothing is built.

"Owner" is the person this integration was built for. The main design is [2026-11-01-morning-routine-integration-design.md](2026-11-01-morning-routine-integration-design.md). This document changes only how the card looks and where the card's form gets its settings from. Anything marked "Builder's call" is a decision the owner hasn't specifically reviewed.

## Why

The add-a-step form works, but it doesn't look like Home Assistant. Brightness and temperatures are typed into plain text boxes. The item picker is the browser's own list with a search box above it. The owner wants the   form, and the card around it, to look and feel like the rest of Home Assistant.

The owner's priority, in order:

1. Make it look like Home Assistant.
2. Later, make new device types easy to add. That isn't part of this work, but the way this is built should help it.

Today, each device type is described in five places: the saved step, the server's checks, the view sent to the card, the card's logic, and the form. Every check on a setting is written twice, once in the card and once on the server.

## What the owner decided

On 2026-11-12, from mockups:

- **The form uses Home Assistant's standard controls** (option A of the mockups): its entity picker, its toggle buttons, its checkbox and its slider. These come from Home Assistant's "selectors". A selector is Home Assistant's standard description of one setting, such as "a number from 1 to 100, shown as a slider, in percent". Its settings screens, blueprints and card editors all use them.
- **Not the device controls** (option B): the round thermostat dial and the big brightness bar from a light's pop-up. The owner liked how they look but chose A because of the catch: those controls are internal parts of Home Assistant, not offered to custom cards. Any release can change them without notice.
- **A thermostat that takes a range gets two sliders,** one for "heat to" and one for "cool to". Not one slider with two handles. Both sliders fill from the left. Home Assistant's standard number control has no setting to fill from the right.
- **Each slider's limits and step size come from the device itself.** The owner especially wanted this.
- **The server describes each item's settings in Home Assistant's selector format, and the card draws them** (approach 2 below).
- **The owner accepted these proposals:**
  - The picker drops the "Lights / Thermostats / Scripts" headings. Each item shows its icon and room instead, the way the picker does everywhere in Home Assistant.
  - If Home Assistant's controls fail to load, the form shows a short sentence. Today's form is not kept as a backup.
  - The card itself matches Home Assistant too: its switches and its clock dropdown. The owner didn't choose explicitly; this was proposed and not objected to.

## Goals

- The add-a-step form is built from Home Assistant's standard controls, as sketched below.
- The card's switches and clock dropdown are Home Assistant's own.
- The server is the one place that knows what a light or thermostat step can do. It sends the card a description of each item's actions and settings. The card draws whatever it is sent, without knowing what a light or thermostat is.
- One description on the server feeds both the form and the server's checks, so the two can't disagree.

## Non-goals

- New device types. Switches, fans and the rest come later, as their own phase.
- Changing what a step can do. Lights and thermostats keep exactly the actions and settings they have in version 0.3.0.
- Changing how steps are saved. The saved file, `set_steps`, and the step fields sent back by the card stay as they are.
- The timeline. Home Assistant has nothing like it, so it stays the card's own.
- Home Assistant's device controls (the round dial, the big brightness bar).
- Home Assistant's action editor from its script screens. It shows every option a light has, such as transition, flash, color and effect, which is too much for someone who isn't comfortable with technology. It would also bypass the limits on what a step can do.

## Anti-goals

These would make this a failure even if everything else worked.

- **The routine switch must always work.** If a phone is lost while its owner is away, the person at home must be able to turn that routine off from the card. Even if Home Assistant's switch doesn't load, the card's switches must still work. The form is allowed to fail to load. The card's face is not.
- **The form must never save something different from what it shows.** If a new view arrives while the form is open, Save either sends what is on screen or says what changed. It never sends a setting the form isn't showing. The Phase 3 review found two ways the current form does this (see `docs/status.md`).
- Everything in the main design's anti-goals still holds, including no red and no clock times.

## Constraints

- **Home Assistant doesn't promise its controls to custom cards.** It loads selectors, the entity picker and its other controls only when one of its own screens needs them. The card has to get them loaded first. One known way is to call `window.loadCardHelpers()`, create one of Home Assistant's own cards, and ask it for its editor, which loads the controls that editor uses. The builder confirms what works on the oldest version this integration supports.
- **The oldest supported version is Home Assistant 2026.10.0** (`hacs.json`), with frontend 20260930. The selectors named here were read from the frontend's current `dev` branch on 2026-11-12. The builder confirms each one exists and behaves the same way in the 2026.10 frontend:
  - `entity` with `include_entities` draws `ha-entity-picker`.
  - `button_toggle` draws `ha-button-toggle-group`.
  - `number` with `mode: slider` and both `min` and `max` set draws `ha-slider` with a number box beside it.
  - `select` with `mode: dropdown` draws `ha-select`.
- **The card stays one plain JavaScript file with no build step.** Home Assistant's controls are ordinary page elements. The card creates them, sets their properties, and listens for their `value-changed` event. No library is needed.
- **The card's existing rules stay in force.** It builds its page with its `h()` helper and never with `innerHTML`. Card text is plain words.
- **Home Assistant's controls exist only inside Home Assistant.** The stand-in page `tests/card/demo.html` can't show them. The new form has to be checked in a real Home Assistant.
- **The repo is public.** Test data and screenshots use made-up names.

## Approaches

### How it looks

The owner saw three options side by side: today's form, A (Home Assistant's standard controls) and B (its device controls). The owner chose A. B was set aside because its controls aren't offered to custom cards and can change in any release. Copying B's controls into the card was also considered. Home Assistant's frontend is under the Apache 2.0 license, so that's allowed with the notice kept. But the controls are written in TypeScript with the Lit library, so they'd need rewriting or a build step, and the card would then maintain them.

For a thermostat that takes a range, the owner chose two sliders over one slider with two handles. The two-handle slider isn't part of the standard number control. The card would have to use Home Assistant's slider directly, and that had not been confirmed to work.

### How it's built

1. **The card turns what the server already sends into Home Assistant's controls.** This is the smallest change. The card keeps its knowledge of lights and thermostats and its own copies of the checks. A new device type later still needs changes in both the card and the server.
2. **The server describes each item's settings in Home Assistant's selector format, and the card draws them.** This is more work now: the card's form logic is rewritten, and the server gains the descriptions. Afterwards the card knows nothing about device types, its copies of the checks go away, and a new device type is mostly server work. **The owner chose this.** The form is being rewritten either way, and doing 1 now and 2 later would rewrite it twice.
3. **Save each step as a Home Assistant action and use the action editor.** Ruled out, for the reasons under Non-goals.

## The design

### The form

```
+--------------------------------------+
| X  Add a step                        |
|                                      |
|  [bulb] Bedroom lamp              v  |   Home Assistant's entity picker
|         Bedroom                      |
|                                      |
|  [ v Turn on ]  [ Turn off ]         |   toggle buttons, only when the
|                                      |   item has more than one action
|  [x] Brightness                      |   checkbox for an optional setting
|  ----------o-------------  [ 40 % ]  |   slider with its number box
|                                      |
|  When                                |
|  [ Minutes  30 ]  [ before the alarm v ]
|                                      |
|                    Cancel   (Save)   |
+--------------------------------------+
```

The approved mockups are in `.superpowers/brainstorm/` on the computer where this was written. That folder is git-ignored. The sketch above is the reference.

- **The picker** is Home Assistant's entity picker. It offers only what the server lists for this routine: lights, thermostats, and labelled scripts, scenes and automations. A script, scene or automation already used by another step is left out, as today. A new step starts with nothing chosen, and Save stays off until something is.
- **What to do:** toggle buttons, one per action the item has, such as "Turn on" and "Turn off". An item with one action shows no buttons. That covers a script, scene or automation (it runs) and a thermostat that takes a range (it sets temperatures).
- **Settings:** one control for each setting of the chosen action, drawn from the server's description.
  - An **optional setting** (brightness, or a one-temperature thermostat's temperature) has a checkbox. Unchecked means the setting is left out: the light comes on as it was, or the thermostat starts at its last setting. Checked shows the slider.
  - A **required setting** ("heat to" and "cool to") always shows its slider.
  - Home Assistant's form control (`ha-form`) has no checkbox for an optional setting, so the card adds Home Assistant's checkbox itself.
- **Limits and step size** come from the device. Brightness is 1 to 100 percent in steps of 1. A thermostat's sliders run from its own lowest to its own highest setting. The step size is the device's `target_temp_step` if it reports one. Otherwise it's 0.5 in Celsius and 1 in Fahrenheit. Builder: check that this matches Home Assistant's own thermostat card.
- **When** is unchanged in what it does: a minutes box and a "before the alarm" / "after the alarm" choice, drawn with Home Assistant's controls. The card's existing minutes check stays.
- **Save and Cancel:** Save is a filled button and Cancel a plain one, as in Home Assistant's dialogs. "Remove step" stays when editing.
- **A step whose item is gone** can still be retimed or removed. What it does can't be changed, and its name is shown as it is today.
- **A step that the item's current description can't show** is treated the same way: its time can change and it can be removed. What it does is shown as its detail line, with a short note, not as controls. This covers three cases: an action the item no longer offers (for example, a thermostat that changes type with its mode), a setting it no longer offers (a light that stopped reporting that it dims), and a saved value outside the device's current limits. Builder's call. The note's wording is new card text for the owner.
- **A saved value between a slider's steps,** such as 68.3 on a thermostat whose step is 1, is kept. The form holds the saved value until the person moves that slider, so opening and saving a step never rounds it.

### The card's face

- The routine switch, the skip switch and each step's switch become Home Assistant's switch (`ha-switch`). They still move only when the server's next view says so, as today.
- The clock dropdown becomes Home Assistant's dropdown.
- If Home Assistant's switch hasn't loaded, the card draws its own switch, so the card is never without a working switch (see Anti-goals).
- The timeline, the step names and the "+ Add a step" button stay as they are.
- Each step's detail line ("Turn on at 40%", "Heat to 68°F, cool to 74°F") comes from the server, so the card doesn't need to know device types to write it. The words are the same as today.

### What the server sends

`devices.py` stays the one place that knows what each device type can do. For each item, it produces the actions and, for each action, its settings in selector format. The view's `items` carry this. The checks in `step_input.py` read the same description, so the form and the checks can't disagree.

An item in the view, for a light that dims:

```json
{
  "item": "light.test_lamp",
  "name": "Test lamp",
  "actions": [
    {
      "action": "turn_on",
      "name": "Turn on",
      "settings": [
        {
          "key": "brightness",
          "name": "Brightness",
          "optional": true,
          "start": 100,
          "selector": {"number": {"min": 1, "max": 100, "step": 1, "mode": "slider", "unit_of_measurement": "%"}}
        }
      ]
    },
    {"action": "turn_off", "name": "Turn off", "settings": []}
  ]
}
```

A thermostat that takes a range has one action, `set_temperature`, named "Set temperatures", with two required settings, `heat_to` and `cool_to`. A script, scene or automation has one action, `run`, with no settings.

- **`key`** is the field name the card sends back in `set_steps`: `brightness`, `temperature`, `heat_to` or `cool_to`, as today.
- **`name`** is the words shown on the button or beside the control. The server sends all of the form's device words, so the card holds none of them.
- **`start`** is where a slider begins on a new step, or when its checkbox is first ticked. Builder's call: the device's current setting where it reports one. Otherwise, brightness starts at 100 and a one-temperature thermostat at the middle of its range. For a thermostat that takes a range, "heat to" starts one third of the way up the range and "cool to" two thirds, so a new step can be saved without moving either. When editing, the slider starts at the step's saved value.
- The view isn't sent again when a device's state changes, only when the routine or the registries change. So start values and limits can be slightly out of date while the card is open. That's accepted.
- **Each step in the view gains `detail`,** its detail line in words.
- Builder's call: the exact field names, and whether the view keeps sending `type` and the old per-item flags (`brightness`, `temperature`, `min_temp`, `max_temp`) once the card no longer reads them.

### What the card sends back

Unchanged. `set_steps` takes the same list of steps, with `id`, `item`, `offset_minutes`, `enabled`, `action` and any settings as top-level fields. Steps saved by versions 0.2.0 and 0.3.0 load and behave as before.

### Checks

- Every check stays on the server, as today. No check is added or removed.
- The sliders keep each value within the device's limits, so the card no longer checks brightness or temperatures itself.
- **Step size is only for the slider.** The server doesn't refuse a value between steps, as in 0.3.0. A number typed into the box beside a slider can fall between steps, and it's accepted.
- When the server refuses a change, such as "heat to" at or above "cool to", the form shows the server's sentence, as it already does for other refusals.

### When Home Assistant's controls don't load

The card starts loading Home Assistant's controls when it first appears. If they haven't loaded when the form opens, the form waits briefly, then shows one sentence instead of its controls. The owner approves the wording. A proposal: "This form couldn't load Home Assistant's controls. Reload the page to try again." Builder's call on how long it waits.

### Text the owner hasn't seen

The builder lists every new or changed piece of card text in `docs/status.md` for the owner, as in earlier phases. Known now: the sentence above, and "Turn on" and "Turn off" as button labels rather than dropdown choices.

## Testing and checking

- **Server tests:** the description for each device type, including limits, step size, start values and detail text. Tests also check that the description and the checks agree: every setting the description offers, at its limits, passes the checks. A setting it doesn't offer, or a value outside its limits, is refused. Step size isn't checked (see Checks).
- **Card tests (Node):** the card's logic that turns a description into the form's state and the form's state into a step to send. The element tests stand in for Home Assistant's controls with small fake elements. The form gets automated tests. Today it has none, which was a Phase 3 review finding.
- **A real Home Assistant, before anything else is built:** first prove that the card can load Home Assistant's controls on version 2026.10, for an admin and for a non-admin account. This is the riskiest assumption. Home Assistant's `demo` integration provides made-up lights and thermostats to try the form with. The owner's server is only used with the owner's go, following the rules in the owner's private repo.
- **If that first test fails:** if one selector is missing or behaves differently in 2026.10, the builder uses the nearest standard control and records it. For example, a `select` in list mode can replace the toggle buttons. Builder's call. If the controls can't be loaded at all, or they load for an admin but not for a non-admin account, the build stops and the builder reports to the owner. Raising the oldest supported version needs the owner's go.
- **Before release:** the whole form is checked in that real Home Assistant at 360 pixels wide, in light and dark themes, and as a non-admin account.

## Documents to update

- The main design's section "The card" gets one line pointing to this document.
- README: "Use the card" describes the new form.
- `docs/status.md`: where this work stands, decisions made while building, and new card text.

## Left to the builder

- File layout and function names.
- Whether the form uses `ha-form` for its settings or one `ha-selector` per setting.
- Whether the dialog is Home Assistant's own dialog element or the card's `<dialog>` styled to match.
- How the card loads Home Assistant's controls, within the constraints above.
- How long the form waits before saying the controls didn't load.
- How the form shows a change from a new view while it's open, within the anti-goal.
- The version number. 0.4.0 is the obvious one.

## Open question for the owner

**Where is the new card tried in a real Home Assistant, and where do the Home Assistant tests run?**

The laptop this was written on doesn't have WSL. On 2026-11-12 the owner said the desktop does, and that work will continue there.

1. **A computer with WSL** (the desktop, or WSL installed on the laptop). A throwaway Home Assistant 2026.10 with the `demo` integration runs there, and `pytest tests/ha` runs there too. Nothing is pushed until the end, and only with the owner's go. Claude's pick: it's the only option that tests the oldest supported version, and it never touches the house server.
2. **A test dashboard on the owner's server.** No setup, but every visit needs the owner's go under the private repo's rules. It only proves the version the server runs, not 2026.10. Without WSL the Home Assistant tests run in GitHub Actions, so the build would push to `main` after each task, as in Phase 3. Failing runs would show on the public repo.

## Builder check, 2026-11-12

A fresh reviewer read this document as the builder and asked four questions. How each was settled:

1. **What if the first test on 2026.10 fails?** Settled as Claude's call, now under "Testing and checking". Swap in the nearest standard control for one missing selector. Stop and report if the controls can't load at all, or don't load for a non-admin account. Raising the oldest supported version needs the owner's go.
2. **A saved step that the item's current description can't show.** Settled as Claude's call, now under "The form". It's treated like a step whose item is gone. A saved value between slider steps is kept unless the person moves that slider.
3. **Should the server refuse values between slider steps?** Already answered by the non-goals: no. Now said plainly under "Checks".
4. **Pushing during the build, or tests in WSL?** This is the open question above.

The reviewer also caught that starting both range-thermostat sliders at the middle would make "heat to" equal "cool to", which the server refuses. Start values are now one third and two thirds of the way up the range.

## Calls Claude made, for the owner to check while reading

The owner approved the look, the two sliders, approach 2 and the proposals listed under "What the owner decided". These were filled in by Claude:

- The second anti-goal: the form never saves something different from what it shows. It comes from two Phase 3 review findings, and the rewrite must not carry them forward.
- The routine switch must always work, even if Home Assistant's switch doesn't load. The card falls back to its own switch.
- The server sends every word the form shows for a device (action names, setting names, detail lines), so the card holds none of them.
- Start values for each slider (under "What the server sends").
- A step the item can no longer show: time and remove only, with a note.
- Step size guides the slider only. No new check.
- If the first test fails: swap one control, or stop and report. No version change without the owner.
- The card stays one plain JavaScript file with no build step.
- The dialog, and whether to use `ha-form` or separate selectors, are left to the builder.
