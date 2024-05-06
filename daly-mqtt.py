import subprocess
import json
import paho.mqtt.client as mqtt
import time
import configparser
import os
import logging
from logging.handlers import RotatingFileHandler

# read conf from ini file
config = configparser.ConfigParser()
config.read('daly-mqtt-config.ini')

# store timestamp from last modified file .ini
last_modified_time = 0

mqtt_username = config['mqtt']['username']
mqtt_password = config['mqtt']['password']
broker_address = config['mqtt']['broker_address']
ttyUSB0_device = config['mqtt']['ttyUSB0_device']
sleep_time = int(config['mqtt']['sleep_time'])
autodiscovery = config.getboolean('mqtt', 'autodiscovery')
# Logs
log_rotation_size_mb = int(config['logs']['log_rotation_size_mb'])
log_rotation_count = int(config['logs']['log_rotation_count'])
enable_logs_mqtt = config.getboolean('logs', 'enable_logs_mqtt')
enable_logs_mqqt_value = config.getboolean('logs', 'enable_logs_mqtt_value')
enable_logs = config.getboolean('logs', 'enable_logs')
enable_logs_oofr_values = config.getboolean('logs', 'enable_logs_oofr_values')
enable_logs_autodiscovery = config.getboolean('logs', 'enable_logs_autodiscovery')

# Configure MQTT client
client = mqtt.Client("daly_bms")

# set the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Formatting the log
formatter = logging.Formatter('%(asctime)s - %(message)s')

# log rotation
file_handler = RotatingFileHandler('logs/daly-mqtt.log', maxBytes=log_rotation_size_mb * 1024 * 1024, backupCount=log_rotation_count)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Function on_publish
def on_publish(client, userdata, mid):
    if enable_logs_mqtt:
        logger.info(f"Message published successfully with mid={mid}")

# Customization load
customizations = {}
if 'customizations' in config:
    for key in config['customizations']:
        try:
            props = config.items('customizations', key)
            if props:  # Assicura che props non sia vuoto
                customizations[key] = {}
                for subkey, value in props:
                    prop_key = subkey.replace('-', '')
                    customizations[key][subkey] = {prop_key: value}
        except configparser.NoSectionError:
            pass

# Measurement unit map for the cells voltage
cell_voltage_unit_map = {
    "1": "V",
    "2": "V",
    "3": "V",
    "4": "V",
    "5": "V",
    "6": "V",
    "7": "V",
    "8": "V",
    "9": "V",
    "10": "V",
    "11": "V",
    "12": "V",
    "13": "V",
    "14": "V",
    "15": "V",
    "16": "V",
}

# Measurement unit map for the temperatures
temperature_unit_map = {
    "1": "°C",
    "2": "°C",
}

# Additional measurements unit map
additional_unit_map = {
    "total_voltage": "V",
    "current": "A",
    "soc_percent": "%",
    "highest_voltage": "V",
    "lowest_voltage": "V",
    "highest_temperature": "°C",
    "lowest_temperature": "°C",
    "capacity_ah": "Ah",
}
while True:
    try:

        # Check if the .ini file was modifiedè stato modificato
        current_modified_time = os.path.getmtime('daly-mqtt-config.ini')
        if current_modified_time != last_modified_time:
            # timestamp update
            last_modified_time = current_modified_time
            if enable_logs:
                logger.info(f"Last modifiedtime .ini is {last_modified_time}")
            # Read the .ini file
            config = configparser.ConfigParser()
            config.read('daly-mqtt-config.ini')
            
            # Variables update
            # mqtt
            mqtt_username = config['mqtt']['username']
            mqtt_password = config['mqtt']['password']
            broker_address = config['mqtt']['broker_address']
            ttyUSB0_device = config['mqtt']['ttyUSB0_device']
            sleep_time = int(config['mqtt']['sleep_time'])
            autodiscovery = config.getboolean('mqtt', 'autodiscovery')
            # logs
            log_rotation_size_mb = int(config['logs']['log_rotation_size_mb'])
            log_rotation_count = int(config['logs']['log_rotation_count'])
            enable_logs_mqtt = config.getboolean('logs', 'enable_logs_mqtt')
            enable_logs_mqqt_value = config.getboolean('logs', 'enable_logs_mqtt_value')
            enable_logs = config.getboolean('logs', 'enable_logs')
            enable_logs_oofr_values = config.getboolean('logs', 'enable_logs_oofr_values')
            enable_logs_autodiscovery = config.getboolean('logs', 'enable_logs_autodiscovery')

        if enable_logs:
            logger.info(f"1 -> autodiscovery is {autodiscovery}")
        # MQTT broker connection
        client.username_pw_set(mqtt_username, mqtt_password)
        client.on_publish = on_publish
        client.connect(broker_address)
    
        # Send MQTT autodiscovery only for the first time
        if autodiscovery:
            # Run daly-bms-cli to get the value in json format
            command = ["daly-bms-cli", "-d", ttyUSB0_device, "--all"]
            result = subprocess.run(command, capture_output=True, text=True)
    
            # Check empty output
            if result.stdout:
                # Analizza l'output JSON
                data = json.loads(result.stdout)
    
                # Public MQTT data
                for key, value in data.items():
                    if isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            # Convert boolean value to number
                            if isinstance(subvalue, bool):
                                subvalue = 1 if subvalue else 0
                            # Managing non text sensors
                            if not ((key == "mosfet_status" and subkey == "mode") or \
                                   (key == "status" and subkey == "states") or \
                                   (key == "balancing_status" and subkey == "error") or \
                                   key == "errors"):
                                # Send MQTT discoveri message for Home Assistant
                                config_topic = f"homeassistant/sensor/daly_bms/{key}_{subkey}/config"
                                unit_of_measurement = ""
                                if key == "cell_voltages" and subkey in cell_voltage_unit_map:
                                    unit_of_measurement = cell_voltage_unit_map[subkey]
                                elif key == "temperatures" and subkey in temperature_unit_map:
                                    unit_of_measurement = temperature_unit_map[subkey]
                                elif subkey in additional_unit_map:
                                    unit_of_measurement = additional_unit_map[subkey]
    						    
                                # add personalizations if present se presenti
                                if key in customizations and subkey in customizations[key]:
                                    customization = customizations[key][subkey]
                                    name = customization.get('name', f"daly_bms_{key}_{subkey}")
                                    icon = customization.get('icon', '')
                                else:
                                    name_key = f"{key}-{subkey}_name"  # Build name key
                                    icon_key = f"{key}-{subkey}_icon"  #  Build icon key
                                    name = config.get('customizations', name_key, fallback=f"daly_bms_{key}_{subkey}")  # Get name from .ini file
                                    icon = config.get('customizations', icon_key, fallback='')  # Get icon from .ini file
                                config_payload = {
                                    "name": name,
                                    "state_topic": f"daly_bms/{key}/{subkey}",
                                    "unit_of_measurement": unit_of_measurement,
                                    "value_template": "{{ value }}",
                                    "icon": icon
                                }
    
                                # log writer
                                if enable_logs_autodiscovery:
                                    logger.info(f"Publishing config for {config_topic} with payload {config_payload}")
                                if enable_logs_autodiscovery:
                                    logger.info(f"Blocco 1 autodiscovery")
    						    
                                client.publish(config_topic, json.dumps(config_payload))
                                # add delay
                                time.sleep(0.05)
    
                            # Managing text based sensors
                            if (key == "mosfet_status" and subkey == "mode") or \
                               (key == "status" and subkey == "states") or \
                               (key == "balancing_status" and subkey == "error"):

                                # Send MQTT discovery message for Home Assistant as text sensor
                                config_topic = f"homeassistant/sensor/daly_bms/{key}_{subkey}/config"
                                unit_of_measurement = ""
                                if key == "cell_voltages" and subkey in cell_voltage_unit_map:
                                    unit_of_measurement = cell_voltage_unit_map[subkey]
                                elif key == "temperatures" and subkey in temperature_unit_map:
                                    unit_of_measurement = temperature_unit_map[subkey]
                                elif subkey in additional_unit_map:
                                    unit_of_measurement = additional_unit_map[subkey]
    						    
                                # add personalizations if present
                                if key in customizations and subkey in customizations[key]:
                                    customization = customizations[key][subkey]
                                    name = customization.get('name', f"daly_bms_{key}_{subkey}")
                                    icon = customization.get('icon', '')
                                else:
                                    name_key = f"{key}-{subkey}_name"  # Build name key
                                    icon_key = f"{key}-{subkey}_icon"  # Build icon key
                                    name = config.get('customizations', name_key, fallback=f"daly_bms_{key}_{subkey}")  #  Get name from .ini file
                                    icon = config.get('customizations', icon_key, fallback='')  # Get icon from .ini file
                                config_payload = {
                                    "name": name,
                                    "state_topic": f"daly_bms/{key}/{subkey}",
                                    "value_template": "{{ value }}",
                                    "icon": icon
                                }
                                if enable_logs_autodiscovery:
                                    logger.info(f"Publishing config for {config_topic} with payload {config_payload}")
                                client.publish(config_topic, json.dumps(config_payload))
    
                                # Aggiungi un ritardo
                                time.sleep(0.05)
    							
                    # Managing errors sensors
                    if (key == "errors"):
                        # Managing sensor errors 1
                        # Send MQTT discovery message for Home Assistant as text sensor
                        config_topic = f"homeassistant/sensor/daly_bms/errors_1/config"
                        name_key = f"{key}-1_name"  # Build name key
                        icon_key = f"{key}-1_icon"  # Build icon key
                        name = config.get('customizations', name_key, fallback=f"daly_bms_{key}_1")  # Get name from .ini file
                        icon = config.get('customizations', icon_key, fallback='')  # Get icon from .ini file
                        config_payload = {
                            "name": name,
                            "state_topic": f"daly_bms/{key}_1",
                            "value_template": "{{ value }}",
                            "icon": icon
                        }
                        if enable_logs_autodiscovery:
                            logger.info(f"Publishing config for {config_topic} with payload {config_payload}")
                            logger.info("Blocco errors 1 autodiscovery ")
                        client.publish(config_topic, json.dumps(config_payload))
                        
                        # Aggiungi un ritardo
                        time.sleep(0.05)
                    
                        # Managing sensor  errors 2
                        #  Send MQTT discovery message for Home Assistant as text sensor
                        config_topic = f"homeassistant/sensor/daly_bms/errors_2/config"
                        name_key = f"{key}-2_name"  # Build name key
                        icon_key = f"{key}-2_icon"  # Build icon key
                        name = config.get('customizations', name_key, fallback=f"daly_bms_{key}_2")  # Get name from .ini file
                        icon = config.get('customizations', icon_key, fallback='')  # Get icon from .ini file
                        config_payload = {
                            "name": name,
                            "state_topic": f"daly_bms/{key}_2",
                            "value_template": "{{ value }}",
                            "icon": icon
                        }
                        if enable_logs_autodiscovery:
                            logger.info(f"Publishing config for {config_topic} with payload {config_payload}")
                            logger.info("Blocco errors 2 autodiscovery ")
                        client.publish(config_topic, json.dumps(config_payload))
                        
                        # Aggiungi un ritardo
                        time.sleep(0.05)

                        # Managing sensor errors 3
                        #  Send MQTT discovery message for Home Assistant as text sensor
                        config_topic = f"homeassistant/sensor/daly_bms/errors_3/config"
                        name_key = f"{key}-3_name"  # Build name key
                        icon_key = f"{key}-3_icon"  # Build icon key
                        name = config.get('customizations', name_key, fallback=f"daly_bms_{key}_3")  # Get name from .ini file
                        icon = config.get('customizations', icon_key, fallback='')  # Get icon from .ini file
                        config_payload = {
                            "name": name,
                            "state_topic": f"daly_bms/{key}_3",
                            "value_template": "{{ value }}",
                            "icon": icon
                        }
                        if enable_logs_autodiscovery:
                            logger.info(f"Publishing config for {config_topic} with payload {config_payload}")
                            logger.info("Blocco errors 3 autodiscovery ")
                        client.publish(config_topic, json.dumps(config_payload))
                        
                        # Aggiungi un ritardo
                        time.sleep(0.05)
                        
                # Managing sensor Difference
                # Send MQTT discovery message for Home Assistant
                config_topic = f"homeassistant/sensor/daly_bms/difference/config"
                name_key = f"cell_voltage-difference_name"  # Build name key
                icon_key = f"cell_voltage-difference_icon"  # Build icon key
                name = config.get('customizations', name_key, fallback=f"daly_bms_difference")  # Get name from .ini file
                icon = config.get('customizations', icon_key, fallback='')  # Get icon from .ini file
                config_payload = {
                    "name": name,
                    "state_topic": f"daly_bms/difference",
                    "value_template": "{{ value }}",
                    "unit_of_measurement": "mV",
                    "icon": icon
                }
                if enable_logs_autodiscovery:
                    logger.info(f"Publishing config for {config_topic} with payload {config_payload}")
                    logger.info("Blocco difference per autodiscovery ")
                client.publish(config_topic, json.dumps(config_payload))
                
                # add delay
                time.sleep(0.05)
                    
                                    
            else:
                if enable_logs:
                    logger.info("Output del comando vuoto. Controlla se il dispositivo /dev/ttyUSB0 è disponibile.")

        # Set autodiscovery to False after the first sent
        autodiscovery = False
        # client disconnet
        client.disconnect()

        if enable_logs:
            logger.info(f"2 -> autodiscovery is {autodiscovery}")
        


        # MQTT broker connection
        client.username_pw_set(mqtt_username, mqtt_password)
        client.on_publish = on_publish
        client.connect(broker_address)

        # Run daly-bms-cli to get the value in json format
        command = ["daly-bms-cli", "-d", ttyUSB0_device, "--all"]
        result = subprocess.run(command, capture_output=True, text=True)

        # Check empty output
        if result.stdout:
            # JSON analysis
            data = json.loads(result.stdout)

            # Pubblic MQTT data
            for key, value in data.items():
                if isinstance(value, dict):

# Start values errors checking block
                    if key == "cell_voltages":
                        # Check if at least one of the cell values ​​is outside the allowed range
                        out_of_range = any(subvalue <= 2 or subvalue > 3.7 for subvalue in value.values())
                        if out_of_range:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring cell {subkey} voltages readings as value {value} is out of range (0V - 3.7V).")
                            continue
                        # Calculating differnce beetween highest_voltage and lowest_voltage
                        highest_voltage = max(value.values())
                        lowest_voltage = min(value.values())
                        voltage_difference = int((highest_voltage - lowest_voltage) * 1000)
                        if enable_logs:
                            logger.info(f"Cell_voltage different {voltage_difference}")
                            
                        client.publish("daly_bms/difference", str(voltage_difference))
                        if enable_logs_mqqt_value:
                            logger.info(f"Public entity daly_bms/difference with value {voltage_difference}")    
                        
                    if key == "soc" and "soc_percent" in value:
                        soc_percent = value["soc_percent"]
                        if enable_logs_oofr_values:
                            logger.info(f"SOC percent reading as value {soc_percent}")
                        # Check if the value of soc_percent is outside the allowed range
                        if soc_percent < 0 or soc_percent > 100:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring SOC percent reading as value {soc_percent} is out of range (0% - 100%).")
                            continue

                    if key == "cell_voltage_range" and "highest_voltage" in value:
                        highest_voltage = value["highest_voltage"]
                        if enable_logs_oofr_values:
                            logger.info(f"highest_voltage reading as value {highest_voltage}")
                        #  Check if the highest_voltage value is outside the allowed range (2 - 3.7)
                        if highest_voltage < 2 or highest_voltage > 3.7:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring higest voltage reading as value {highest_voltage} is out of range (2 - 3.7).")
                            continue

                    if key == "cell_voltage_range" and "lowest_voltage" in value:
                        lowest_voltage = value["lowest_voltage"]
                        if enable_logs_oofr_values:
                            logger.info(f"lowest voltage reading as value {lowest_voltage}")
                        # Check if the value of lowest_voltage is outside the allowed range (2 - 3.7)
                        if lowest_voltage < 2 or lowest_voltage > 3.7:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring lowest voltage reading as value {lowest_voltage} is out of range (2 - 3.7).")
                            continue

                    if key == "soc" and "total_voltage" in value:
                        total_voltage = value["total_voltage"]
                        if enable_logs_oofr_values:
                            logger.info(f"soc total_voltage reading as value {total_voltage}")
                        # Check if the soc voltage value is outside the allowable range
                        if total_voltage < 48 or total_voltage > 60:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring total_voltage reading as value {total_voltage} is out of range.")
                            continue

                    if key == "soc" and "current" in value:
                        current = value["current"]
                        if enable_logs_oofr_values:
                            logger.info(f"soc current reading as value {current}")
                        # Check if the soc voltage value is outside the allowable range
                        if current < -180 or current > 180:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring soc current reading as value {current} is out of range.")
                            continue
                            
                     if key == "soc" and "capacity_ah" in value:
                        capacity_ah = value["capacity_ah"]
                        if enable_logs_oofr_values:
                            logger.info(f"capacity_ah reading as value {capacity_ah}")
                        # Check if the capacity_ah value is outside the allowable range
                        if capacity_ah < 0 or capacity_ah > 300:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring capacity_ah reading as value {capacity_ah} is out of range.")
                            continue

                    if key == "temperature_range" and "highest_temperature" in value:
                        highest_temperature = value["highest_temperature"]
                        if enable_logs_oofr_values:
                            logger.info(f"highest_temperature reading as value {highest_temperature}")
                        # Check if the soc voltage value is outside the allowable range
                        if highest_temperature < 0 or highest_temperature > 60:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring soc current reading as value {highest_temperature} is out of range.")
                            continue

                    if key == "temperature_range" and "lowest_temperature" in value:
                        lowest_temperature = value["lowest_temperature"]
                        if enable_logs_oofr_values:
                            logger.info(f"lowest_temperature reading as value {lowest_temperature}")
                        # Check if the soc voltage value is outside the allowable range
                        if lowest_temperature < 0 or lowest_temperature > 60:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring soc current reading as value {lowest_temperature} is out of range.")
                            continue
# End value checking errors block

                    for subkey, subvalue in value.items():
                        # Converti i valori booleani in numeri
                        if isinstance(subvalue, bool):
                            subvalue = 1 if subvalue else 0
            
                        # Pubblica il valore
                        client.publish(f"daly_bms/{key}/{subkey}", str(subvalue))
                        if enable_logs_mqqt_value:
                            logger.info(f"Public entity daly_bms/{key}/{subkey} with value {value}")
                            
                elif isinstance(value, list) and key == 'errors':
                    # Managing error field
                    if not value:  # If the error list is empty
                        if enable_logs:
                            logger.info("No errors to publish then send None to the sensors")
                        # Public "None"
                        client.publish("daly_bms/errors_1", "None")
                        client.publish("daly_bms/errors_2", "None")
                        client.publish("daly_bms/errors_3", "None")
                    else:
                        for i, errors in enumerate(value):
                            # Public the text value
                            client.publish(f"daly_bms/errors_{i+1}", errors)
                        if enable_logs_mqqt_value:
                            logger.info(f"Public entity daly_bms/{key}_{i} with value {value}")
                else:
                    # Boolean value to number
                    if isinstance(value, bool):
                        value = 1 if value else 0
            
                    # Public the value
                    client.publish(f"daly_bms/{key}", str(value))
                    if enable_logs_mqqt_value:
                        logger.info(f"Public entity daly_bms/{key}/{subkey} with value {value}")

        else:
            if enable_logs:
                logger.info("Command output empty. Check if the device /dev/ttyUSB0 if avaliable.")

    except Exception as e:
        if enable_logs:
            logger.error(f"Error during script execution: {e}")
        pass

    # Client disconnec
    client.disconnect()

    # Wait befor run again
    time.sleep(sleep_time)



