
# Values from the API come back as enums, and we don't want to say that the printer's
# current status is PAUSED_FILAMENT_RUNOUT -- we'd rather say "Paused - Filament runout".
# This maps those enum values to display strings.
#
# The enum values were taken directly from the API's github source, and the display strings
# were customized for this project.  (https://github.com/BambuTools/bambulabs_api)
PRINTER_STATUS_MAP = {
    "PRINTING": "Printing",
    "AUTO_BED_LEVELING": "Leveling bed",
    "HEATBED_PREHEATING": "Preheating bed",
    "SWEEPING_XY_MECH_MODE": "Sweeping XY mechanical mode",
    "CHANGING_FILAMENT": "Changing filament",
    "M400_PAUSE": "Paused",
    "PAUSED_FILAMENT_RUNOUT": "Paused - filament runout",
    "HEATING_HOTEND": "Heating hotend",
    "CALIBRATING_EXTRUSION": "Calibrating extrusion",
    "SCANNING_BED_SURFACE": "Scanning bed surface",
    "INSPECTING_FIRST_LAYER": "Inspecting first layer",
    "IDENTIFYING_BUILD_PLATE_TYPE": "Identifying bed plate",
    "CALIBRATING_MICRO_LIDAR": "Calibrating micro-LiDAR",
    "HOMING_TOOLHEAD": "Homing toolhead",
    "CLEANING_NOZZLE_TIP": "Cleaning nozzle tip",
    "CHECKING_EXTRUDER_TEMPERATURE": "Checking extruder temperature",
    "PAUSED_USER": "Paused - user paused",
    "PAUSED_FRONT_COVER_FALLING": "Paused - front cover fell off",
    "CALIBRATING_LIDAR": "Calibrating LiDAR",
    "CALIBRATING_EXTRUSION_FLOW": "Calibrating extrusion flow",
    "PAUSED_NOZZLE_TEMPERATURE_MALFUNCTION": "Paused - nozzle temperature malfunction",
    "PAUSED_HEAT_BED_TEMPERATURE_MALFUNCTION": "Paused - heat bed temperature malfunction",
    "FILAMENT_UNLOADING": "Unloading filament",
    "PAUSED_SKIPPED_STEP": "Paused - skipped step",
    "FILAMENT_LOADING": "Loading filament",
    "CALIBRATING_MOTOR_NOISE": "Calibrating motor noise",
    "PAUSED_AMS_LOST": "Paused - lost AMS",
    "PAUSED_LOW_FAN_SPEED_HEAT_BREAK": "Paused - low fan speed heat break",
    "PAUSED_CHAMBER_TEMPERATURE_CONTROL_ERROR": "Paused - chamber temperature control error",
    "COOLING_CHAMBER": "Cooling chamber",
    "PAUSED_USER_GCODE": "Paused - user gcode pause",
    "MOTOR_NOISE_SHOWOFF": "Showing off motor noise",
    "PAUSED_NOZZLE_FILAMENT_COVERED_DETECTED": "Paused - nozzle filament cover detected",
    "PAUSED_CUTTER_ERROR": "Paused - cutter error",
    "PAUSED_FIRST_LAYER_ERROR": "Paused - first layer error",
    "PAUSED_NOZZLE_CLOG": "Paused - nozzle clogged",
    "UNKNOWN": "Unknown",
    "IDLE": "Idle",
}