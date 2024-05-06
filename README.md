# daly_bms_mqtt
Send Daly BMS data via MQTT with autodiscovery for Home Assistant.

This script simply uses the [python-daly-bms](https://github.com/dreadnought/python-daly-bms) library which must be installed and running to take data from the Daly BMS and send it via MQTT.

The script focuses on making it easy to set up entities on Home Assistant using MQTT Discovery.

In the .ini file you can configure all the parameters required by the script:
The device RS485 (ex. /dev/ttyUSB0)
The mqtt broker ip;
The mqtt broker user and password;
and soo on.

To execute the script use:
python3 daly-mqtt.py

Once the script is started it will send the mqtt discovery messages and home assistant will configure all the entities based on the names and icons present in the .ini file

Note that when you make a change to the .ini file the script already running will send the updates to home assistant like the name or icon of the entity, or you can open or close the various sections of the logs:

enable_logs_mqtt: messaggi dal client mqtt

enable_logs_mqtt_value = invio dei payload al log

enable_logs = logs generici

enable_logs_oofr_values = messaggi di out of range values

enable_logs_autodiscovery: Log riguardanti i messaggi di mqtt autodiscovery.
