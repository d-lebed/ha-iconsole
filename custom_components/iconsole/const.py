"""Constants for the iConsole+ (ChangYow) integration."""

from typing import Final

DOMAIN: Final = "iconsole"

CONF_DEVICE_INFO: Final = "device_info"

# GATT Service and Characteristic UUIDs
DIS_SERVICE_UUID: Final = "0000180a-0000-1000-8000-00805f9b34fb"
DIS_MANUFACTURER_UUID: Final = "00002a29-0000-1000-8000-00805f9b34fb"
DIS_MODEL_UUID: Final = "00002a24-0000-1000-8000-00805f9b34fb"
DIS_SERIAL_UUID: Final = "00002a25-0000-1000-8000-00805f9b34fb"
DIS_HW_REV_UUID: Final = "00002a27-0000-1000-8000-00805f9b34fb"
DIS_SW_REV_UUID: Final = "00002a26-0000-1000-8000-00805f9b34fb"

FFF0_SERVICE_UUID: Final = "0000fff0-0000-1000-8000-00805f9b34fb"
FFF1_NOTIFY_UUID: Final = "0000fff1-0000-1000-8000-00805f9b34fb"
FFF2_WRITE_UUID: Final = "0000fff2-0000-1000-8000-00805f9b34fb"

ISSC_SERVICE_UUID: Final = "49535343-fe7d-4ae5-8fa9-9fafd205e455"
ISSC_NOTIFY_UUID: Final = "49535343-1e4d-4bd9-ba61-23c647249616"
ISSC_WRITE_UUID: Final = "49535343-8841-43f4-a8d4-ecbe34729bb3"

# ChangYow packet command & response codes
STARTER: Final = 0xF0

CMD_ACK: Final = 0xA0
RESP_ACK: Final = 0xB0

CMD_GET_MAX_LEVEL: Final = 0xA1
RESP_GET_MAX_LEVEL: Final = 0xB1

CMD_GET_STATUS: Final = 0xA2
RESP_GET_STATUS: Final = 0xB2

CMD_SET_MODE: Final = 0xA3
RESP_SET_MODE: Final = 0xB3

CMD_SET_PARAM: Final = 0xA4
RESP_SET_PARAM: Final = 0xB4

CMD_SET_CONTROL_STATE: Final = 0xA5
RESP_SET_CONTROL_STATE: Final = 0xB5

CMD_D5_SET_SPEED: Final = 0xA6
RESP_D5_SET_SPEED: Final = 0xB6

CMD_MACHINE_CHECK: Final = 0xAB
RESP_MACHINE_CHECK: Final = 0xBB

CMD_SET_INCLINE: Final = 0xAC
RESP_SET_INCLINE: Final = 0xBC

CMD_SET_KEY_LOCK: Final = 0xAF
RESP_SET_KEY_LOCK: Final = 0xBF

# Telemetry keys
KEY_SPEED: Final = "speed_instant"
KEY_DISTANCE: Final = "distance_total"
KEY_CALORIES: Final = "energy_total"
KEY_HEART_RATE: Final = "heart_rate"
KEY_INCLINE: Final = "inclination"
KEY_TIME_ELAPSED: Final = "time_elapsed"
KEY_TRAINING_STATUS: Final = "training_status"
KEY_CONNECTION_STATUS: Final = "connection_status"
KEY_TARGET_INCLINE: Final = "target_inclination"
KEY_TARGET_SPEED: Final = "target_speed"

# Training statuses
STATUS_IDLE: Final = "idle"
STATUS_RUNNING: Final = "running"
STATUS_PAUSED: Final = "paused"
STATUS_STOPPED: Final = "stopped"

TRAINING_STATUS_OPTIONS: Final = [
    STATUS_IDLE,
    STATUS_RUNNING,
    STATUS_PAUSED,
    STATUS_STOPPED,
]

# Connection statuses
CONN_DISCONNECTED: Final = "disconnected"
CONN_CONNECTING: Final = "connecting"
CONN_SLEEPING: Final = "sleeping"
CONN_CONNECTED: Final = "connected"
CONN_AUTONOMOUS_RUNNING: Final = "autonomous_running"

CONNECTION_STATUS_OPTIONS: Final = [
    CONN_DISCONNECTED,
    CONN_CONNECTING,
    CONN_SLEEPING,
    CONN_CONNECTED,
    CONN_AUTONOMOUS_RUNNING,
]
