"""Which Android apps can be picked as the alarm clock. Must never import homeassistant."""

GOOGLE_CLOCK = "com.google.android.deskclock"
SAMSUNG_CLOCK = "com.sec.android.app.clockpackage"
NOT_CLOCKS = {"com.samsung.android.app.routines"}

CLOCK_NAMES = {
    GOOGLE_CLOCK: "Google Clock",
    SAMSUNG_CLOCK: "Samsung Clock",
}


def clock_options(
    manufacturer: str | None, reported: set[str], chosen: str | None
) -> dict[str, str]:
    """Package to plain name, for the clock picker."""
    packages = {GOOGLE_CLOCK}
    if (manufacturer or "").lower() == "samsung":
        packages.add(SAMSUNG_CLOCK)
    packages |= reported - NOT_CLOCKS
    if chosen is not None:
        packages.add(chosen)
    return {package: CLOCK_NAMES.get(package, package) for package in sorted(packages)}
