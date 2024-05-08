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

# Battery values
battery_capacity = int(config['battery_conf']['battery_capacity'])
max_charging_amp = int(config['battery_conf']['max_charging_amp'])
max_dicharging_amp = int(config['battery_conf']['max_dicharging_amp'])
max_difference = int(config['battery_conf']['max_difference'])

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

last_valid_cell_voltages = None
last_valid_soc_percent = None

while True:
    try:
        logger.info("")
        logger.info("********** Starting ************")
        logger.info("")
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
            
            # Battery values
            battery_capacity = int(config['battery_conf']['battery_capacity'])
            max_charging_amp = int(config['battery_conf']['max_charging_amp'])
            max_dicharging_amp = int(config['battery_conf']['max_dicharging_amp'])
            max_difference = int(config['battery_conf']['max_difference'])
            
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
                                    logger.info(f"Step 1 autodiscovery")
    						    
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
                        
                        # Managing sensor error 0
                        #  Send MQTT discovery message for Home Assistant as text sensor
                        config_topic = f"homeassistant/sensor/daly_bms/errors_0/config"
                        name_key = f"{key}-0_name"  # Build name key
                        icon_key = f"{key}-0_icon"  # Build icon key
                        name = config.get('customizations', name_key, fallback=f"daly_bms_{key}_0")  # Get name from .ini file
                        icon = config.get('customizations', icon_key, fallback='')  # Get icon from .ini file
                        config_payload = {
                            "name": name,
                            "state_topic": f"daly_bms/{key}_0",
                            "value_template": "{{ value }}",
                            "icon": icon
                        }
                        if enable_logs_autodiscovery:
                            logger.info(f"Publishing config for {config_topic} with payload {config_payload}")
                            logger.info("Step error 0 autodiscovery ")
                        client.publish(config_topic, json.dumps(config_payload))
                        
                        # Aggiungi un ritardo
                        time.sleep(0.05)
                        
                        # Managing sensor error 1
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
                            logger.info("Step error 1 autodiscovery ")
                        client.publish(config_topic, json.dumps(config_payload))
                        
                        # Aggiungi un ritardo
                        time.sleep(0.05)
                    
                        # Managing sensor  error 2
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
                            logger.info("Step error 2 autodiscovery ")
                        client.publish(config_topic, json.dumps(config_payload))
                        
                        # Aggiungi un ritardo
                        time.sleep(0.05)

                        # Managing sensor error 3
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
                            logger.info("Step error 3 autodiscovery ")
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
                    logger.info("Step difference per autodiscovery ")
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
                        # Check if at least one of the cell values is outside the allowed range
                        out_of_range = any(subvalue <= 2 or subvalue > 3.7 for subvalue in value.values())
                        if out_of_range:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring cell {subkey} voltages readings as value {value} is out of range (0V - 3.7V).")
                            continue
                        
                        if last_valid_cell_voltages is not None:
                            # Check if new values exceed ±10 from last valid values
                            if enable_logs:
                                logger.info(f"Last valid cell voltages    {last_valid_cell_voltages}")
                                logger.info(f"Current valid cell voltages {value}")
                                logger.info("Calculating cells exceed range")
                            exceed_range = any(abs(subvalue - last_valid_cell_voltages[subkey]) > 0.03 for subkey, subvalue in value.items())
                            if exceed_range:
                                if enable_logs_oofr_values:
                                    logger.info(f"Ignoring cell {subkey} voltages readings as value {subvalue} exceed ±30% with exceed range from last valid values {last_valid_cell_voltages}.")
                                continue
                            if enable_logs:
                                logger.info("No cells exceed range present")
                        # Update last valid cell voltages
                        last_valid_cell_voltages = {subkey: subvalue for subkey, subvalue in value.items()}

                    # Check highest_voltage and lowest_voltage range + calcultanig difference
                    if (key == "cell_voltage_range" and "highest_voltage") and (key == "cell_voltage_range" and "lowest_voltage") in value:
                        highest_voltage = value["highest_voltage"]
                        lowest_voltage = value["lowest_voltage"]
                        if enable_logs:
                            logger.info(f"highest_voltage reading as value:     {highest_voltage}")
                            logger.info(f"lowest voltage reading as value:      {lowest_voltage}")
                        #  Check if the highest_voltage value is outside the allowed range (2 - 3.7)
                        if highest_voltage < 2 or highest_voltage > 3.7:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring higest voltage reading as value {highest_voltage} is out of range (2 - 3.7).")
                            continue
                        if lowest_voltage < 2 or lowest_voltage > 3.7:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring lowest voltage reading as value {lowest_voltage} is out of range (2 - 3.7).")
                            continue
                        # Calculating differnce beetween highest_voltage and lowest_voltage
                        logger.info(f"Hv: {highest_voltage} Lv: {lowest_voltage}")
                        voltage_difference = int((highest_voltage - lowest_voltage) * 1000)
                        if enable_logs:
                            logger.info(f"Cell_voltage difference:              {voltage_difference}")
                            logger.info(f"Max voltage difference is:            {max_difference}")
                        if voltage_difference < 0 or voltage_difference > max_difference:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring voltage_difference readings as values {voltage_difference} is out of range (0 - {max_difference}.")
                            continue
                        # Publish voltage difference
                        client.publish("daly_bms/difference", str(voltage_difference))
                        if enable_logs_mqqt_value:
                            logger.info(f"Publishing entity daly_bms/difference with value {voltage_difference}")
#                        # Update last valid voltage difference
#                        last_valid_voltage_difference = voltage_difference
#                        if last_valid_voltage_difference == 0:
#                            last_valid_voltage_difference = None

                    if (key == "soc" and "soc_percent") and (key == "soc" and "total_voltage") and (key == "soc" and "current") in value:
                        soc_percent = value["soc_percent"]
                        total_voltage = value["total_voltage"]
                        current = value["current"]
                        if enable_logs:
                            logger.info(f"SOC percent reading as value:         {soc_percent}")
                            logger.info(f"SOC total_voltage reading as value:   {total_voltage}")
                            logger.info(f"SOC current reading as value:         {current}")
                            logger.info(f"Max charging current is:              {max_charging_amp}")
                            logger.info(f"Max discharging current is:           {max_dicharging_amp}")
                        # Check if the value of soc_percent is outside the allowed range
                        if soc_percent < 1 or soc_percent > 100:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring SOC percent reading as value {soc_percent} is out of range (0% - 100%).")
                            continue
                        if last_valid_soc_percent is not None:
                            soc_range_threshold = last_valid_soc_percent * 0.1
                            if enable_logs:
                                logger.info(f"soc_percent range threshold:          {soc_range_threshold}")
                            if soc_percent > last_valid_soc_percent + soc_range_threshold or soc_percent < last_valid_soc_percent - soc_range_threshold:
                                if enable_logs_oofr_values:
                                    logger.info(f"Ignoring soc percent readings as value {soc_percent} exceeds ±10% range from last valid value {last_valid_soc_percent}.")
                                continue
                        last_valid_soc_percent = soc_percent
                            
                        # Check if the soc voltage value is outside the allowable range
                        if total_voltage < 48 or total_voltage > 60:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring total_voltage reading as value {total_voltage} is out of range.")
                            continue
                        # Check if the current value is outside the allowable range
                        if current < max_dicharging_amp or current > max_charging_amp:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring soc current reading as value {current} is out of range.")
                            continue
                            
                    if key == "mosfet_status" and "capacity_ah" in value:
                        capacity_ah = value["capacity_ah"]
                        if enable_logs:
                            logger.info(f"capacity_ah reading as value:         {capacity_ah}")
                            logger.info(f"Battery capacity setting is:          {battery_capacity}")
                        # Check if the capacity_ah value is outside the allowable range
                        if capacity_ah < 0 or capacity_ah > battery_capacity:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring capacity_ah reading as value {capacity_ah} is out of range.")
                            continue

                    if (key == "temperature_range" and "highest_temperature") and (key == "temperature_range" and "lowest_temperature") in value:
                        highest_temperature = value["highest_temperature"]
                        lowest_temperature = value["lowest_temperature"]
                        if enable_logs:
                            logger.info(f"highest_temperature reading as value: {highest_temperature}")
                            logger.info(f"lowest_temperature reading as value:  {lowest_temperature}")
                        # Check if the soc voltage value is outside the allowable range
                        if highest_temperature < 0 or highest_temperature > 60:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring highest_temperature reading as value {highest_temperature} is out of range.")
                            continue
                        # Check if the soc voltage value is outside the allowable range
                        if lowest_temperature < 0 or lowest_temperature > 60:
                            if enable_logs_oofr_values:
                                logger.info(f"Ignoring lowest_temperature reading as value {lowest_temperature} is out of range.")
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
                        client.publish("daly_bms/errors_0", "None")
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
