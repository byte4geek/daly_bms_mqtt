# Daly BMS mqtt vs Home Assistant v0.2
Send Daly BMS data via MQTT with autodiscovery for Home Assistant.

This script simply uses the [python-daly-bms](https://github.com/dreadnought/python-daly-bms) library which must be installed and running to take data from the Daly BMS and send it via MQTT.

The script focuses on making it easy to set up entities on Home Assistant using MQTT Discovery.

In the .ini file you can configure all the parameters required by the script:
- The device RS485 (ex. /dev/ttyUSB0);
- The mqtt broker ip;
- The mqtt broker user and password;
- set the capacity of your battery;
- set the maximum charge and discharge current (e.g. 100 / -100);
- set the max difference in milliVolt (this is to avoid value out of range;
- and soo on.

## Requirements:
```
Python 3.11.2
pip3 install paho-mqtt==1.5.1
```
## Installation and configuration:
```
git clone https://github.com/byte4geek/daly_bms_mqtt.git
```
`cd mqtt-daly-bms`
edit the file `daly-mqtt-config.ini` with your parameters.

## Executing the script:
```
python3 daly-mqtt.py
```

## AutoRun at boot:
if you have the script under /root insert in crontab:
```
@reboot sleep 10 && cd /root/mqtt-daly-bms/ && nohup python3 daly-mqtt.py &

```
## NOTE:
Once the script is started it will send the mqtt discovery messages and home assistant will configure all the entities based on the names and icons present in the .ini file.

Note that when you make a change to the .ini file the script already running will send the updates to home assistant like the name or icon of the entity, or you can open or close the various sections of the logs:

- enable_logs_mqtt: messages from the mqtt client
- enable_logs_mqtt_value = record the payload to the log
- enable_logs = generic logs
- enable_logs_oofr_values = out of range values messages
- enable_logs_autodiscovery: Messages about mqtt autodiscovery.



## DISCLAIMER:
This software is provided as is, no support is guaranteed, any problems or failures caused by its use are at your own risk.



# Donation
Buy me a coffee.

[![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=VK4CSX9NVQAZU)

