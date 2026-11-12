DOMAIN = "morning_routine"

CONF_ALARM_SENSOR = "alarm_sensor"
CONF_TRACKER = "tracker"
CONF_DEVICE_ID = "device_id"
CONF_REQUIRE_ZERO_SECONDS = "require_zero_seconds"

LABEL_NAME = "morning routine"
EVENT_STEP_RAN = "morning_routine_step_ran"
SERVICE_SET_STEPS = "set_steps"

ALLOWED_DOMAINS = ("script", "scene", "automation")
# Devices a step can change directly. These need no label.
DEVICE_DOMAINS = ("light", "climate")
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_STEPS = "steps"
MIN_OFFSET_MINUTES = -720
# An alarm's record is kept for 90 minutes after it, and a later step would never run.
MAX_OFFSET_MINUTES = 60
