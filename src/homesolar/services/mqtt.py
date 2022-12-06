# Third party imports
import datetime
import json
import threading

from loguru import logger
from paho.mqtt import client as paho_mqtt

# Project imports
from ..utils.mqtt import MqttTopic


# This thread is responsible for any task that needed to be executed on mqtt process
# mainly for publish message task and several other task for internal commands.
# The reason it has to be on a different thread is to make sure that whatever task that is processed
# would not hog the MQTT client ability to received message from the broker
# and skipping any information that might be important
def mqtt_task_loop(run, queue, client: paho_mqtt.Client):
    try:
        while True:
            # Waiting for task to do
            logger.debug("Waiting for task!")
            task = queue.get()
            logger.debug(f"Task received [{task}]")

            # If stop is issued, shutting down the thread
            if task == "STOP":
                logger.info("Stop is issued, shutting down the thread")
                break

            try:
                if task["name"] == "publish":
                    client.publish(task["topic"], task["payload"])
                else:
                    logger.warning(f"Unknown task is issued, discarding... [{task}]")
            except Exception as e:
                logger.warning(f"Invalid task is issued, discarding... [{e}]")

    except Exception as e:
        logger.exception(f"Unexpected error occurred, shutting down thread [{e}]")
    finally:
        run.append("STOP")
        return


# Start the MQTT Service, designed to only work properly on an entirely different process
# Any other implementation and usage of the service is not recommended, only do so if you understand what you're doing
def start_service(mqtt_queue, main_queue, config):
    # Initialize the client and thread
    run = []
    client = paho_mqtt.Client()
    mqtt_task_thread = threading.Thread(target=mqtt_task_loop, args=[run, mqtt_queue, client])

    try:
        host = config['MQTT']['host']
        port = config['MQTT']['port']
        username = config['MQTT']['username']
        password = config['MQTT']['password']
        keepalive = config['MQTT']['keepalive']
        reconnect = config['MQTT']['reconnect_delay']

        client.reconnect_delay_set(max_delay=reconnect)
        client.on_message = decorated_on_message(mqtt_queue, main_queue)
        client.on_connect = on_connect
        client.username_pw_set(username, password)
        client.connect(host, port, keepalive)

        # Start the task thread
        mqtt_task_thread.start()
        logger.info("Publish thread started")

        # Start MQTT main loop
        client.loop_forever()

    except Exception as e:
        logger.exception(f"Something unexpected happened when running MQTT Service, shutting down... [{e}]")
    finally:
        client.disconnect()
        mqtt_queue.put("STOP")
        mqtt_task_thread.join()
        main_queue.put("STOP")


def decorated_on_message(mqtt_queue, main_queue):
    def on_message(client: paho_mqtt.Client, userdata, msg):
        # Handles messages on Sensors Topic
        if MqttTopic.SENSORS[:-2] in str(msg.topic):
            sensor_name = str(msg.topic).replace(MqttTopic.SENSORS[:-2] + "/", "").rstrip('/')
            data = {
                "name": sensor_name,
                "payload": msg.payload,
                "time": datetime.datetime.now().timestamp()
            }

            logger.debug(f"Incoming Sensor Data [{sensor_name}]")
            main_queue.put({"name": "write_sensor_data", "data": data})

        # Handles messages on Client Topic
        elif MqttTopic.CLIENT[:-2] in str(msg.topic):
            client_id = str(msg.topic).split("/")[-2]
            logger.debug(f"Client [{client_id}] request incoming {msg.payload}")

            # Handles Client status update
            if "status" in str(msg.topic):
                logger.debug("Client update request received")
                status = str(msg.payload, 'utf-8')
                try:
                    if status == "Connected":
                        task = {
                            "name": "add_client",
                            "client_id": client_id
                        }
                    else:
                        task = {
                            "name": "remove_client",
                            "client_id": client_id
                        }
                    main_queue.put(task)

                except Exception as e:
                    logger.warning(f"Something went wrong when updating client's status {e}")

            # Handles client request
            elif "request" in str(msg.topic):
                logger.debug("Client request received")
                try:
                    json_data = json.loads(msg.payload)
                    request_type = json_data["request_type"]
                    task = {
                        "name": request_type,
                        "request_id": json_data["request_id"],
                        "client_id": client_id
                    }

                    if request_type == "chart_data":
                        task["date"] = json_data["date"]
                        task["timescale"] = json_data["timescale"]
                        main_queue.put(task)
                    else:
                        logger.warning(f"Unknown request is issued, discarding... [{request_type}]")

                except Exception as e:
                    logger.warning(f"Invalid request, rejected [{e}]")
            else:
                logger.warning(f"Unknown request received, discarding... [{msg.topic}:{msg.payload}]")

    return on_message


def on_connect(client: paho_mqtt.Client, userdata, flags, reconnect):
    try:
        client.subscribe(MqttTopic.SENSORS)
        client.subscribe(MqttTopic.REQUEST)
        client.subscribe(MqttTopic.CLIENT)
        message = "Client reconnected successfully" if reconnect else "Client connected successfully"
        logger.info(message)
    except Exception as e:
        logger.exception(f"Something went wrong while trying to subscribes {e}")
