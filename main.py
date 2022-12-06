import asyncio
import datetime
import json
import multiprocessing as mp
import sys
import threading
from time import sleep, perf_counter

from loguru import logger

from homesolar.utils import config
from homesolar.utils.datetime import DateTimeEncoder

config_string = {
    "LOGGER": {
        "log_location": "logs/"
    },
    "CLIENT": {
        "response_time": 5,
        "update_time": 5 * 60
    },
    "MQTT": {
        "host": "homesolar.wilamare.com",
        "port": 1883,
        "username": "homesolar",
        "password": "homesolar123",
        "keepalive": 60,
        "reconnect_delay": 120,
    },
    "INFLUXDB": {
        "host": "http://localhost",
        "port": 8086,
        "token": "g0f6rFPPiAPqxPyuCmbR57WFCoeIV0-RlexjybpipavSP-vWGS7ZeSsXm_jXx8ppX-34xyyJa2sh-6MQoko_hg==",
        "org": "wilamare",
        "default_bucket": "homesolar",
        "read_timeout": 30_000,
        "timezone": "Asia/Makassar"
    },
    "SQLITE": {
        "database": "/homesolar.db"
    },
    "BLUETOOTH": {
        "port": "/dev/rfcomm0",
        "request_code": "DBDB00000000"
    },
    "DATA": {
        "battery_single_cell": False,
        "battery_cells_measurement": "Antw33-BMS",
        "battery_cells_fields": "Cell1 Cell2 Cell3 Cell4 Cell5 Cell6 Cell7 Cell8 Cell9 Cell10 Cell11 Cell12 Cell13",
        "battery_cells_balance_measurement": "Antw33-BMS",
        "battery_cells_balance_fields": "Bal1 Bal2 Bal3 Bal4 Bal5 Bal6 Bal7 Bal8 Bal9 Bal10 Bal11 Bal12 Bal13",
        "battery_status_measurement": "Antw33-BMS",
        "battery_status_field": "DischargeStatus",
        "battery_voltage_measurement": "Antw33-BMS",
        "battery_voltage_field": "Voltage",
        "battery_amperage_measurement": "Antw33-BMS",
        "battery_amperage_field": "Current",
        "battery_power_measurement": "Antw33-BMS",
        "battery_power_field": "Power",
        "battery_charge_measurement": "Antw33-BMS",
        "battery_charge_field": "SoC",
        "solar_production_measurement": "tasmota_solar/SENSOR",
        "solar_production_field": "ENERGY_Power",
        "grid_power_measurement": "tasmota_grid/SENSOR",
        "grid_power_field": "ENERGY_Power",
        "inverter_power_measurement": "tasmota_inverter/SENSOR",
        "inverter_power_field": "ENERGY_Power",
    }
}
config.load_config(config_string)
logger.info("Configuration loaded")

from homesolar.services import mqtt, bluetooth, relayer
from homesolar.services.sqlite import reinitialize_tables
from homesolar.interfaces import database
from homesolar.interfaces import mqtt as mqtt_interface


def dummy_bluetooth(main_task_queue):
    payload = {'Voltage': 48.6, 'Current': 5.9, 'Power': 286.0, 'Capacity': 200.0, 'ChargeStatus': 1.0,
               'DischargeStatus': 1.0, 'BalanceStatus': 0.0, 'BalanceCells': 0.0, 'Bal0': 0, 'Bal1': 0,
               'Bal2': 0, 'Bal3': 0, 'Bal4': 0, 'Bal5': 0, 'Bal6': 0, 'Bal7': 0, 'Bal8': 0, 'Bal9': 0,
               'Bal10': 0, 'Bal11': 0, 'Bal12': 0, 'Bal13': 0, 'Bal14': 0, 'Bal15': 0, 'Bal16': 0, 'Bal17': 0,
               'Bal18': 0, 'Bal19': 0, 'Bal20': 0, 'Bal21': 0, 'Bal22': 0, 'Bal23': 0, 'Temp1': 35.0,
               'Temp2': 34.0, 'Temp3': 34.0, 'Temp4': 33.0, 'Temp5': 38.0, 'Temp6': 32.0, 'MinCell': 8.0,
               'MaxCell': 4.0, 'MinVolt': 3.694, 'MaxVolt': 3.786, 'AvgVolt': 3.733, 'SoC': 34.58870168483647,
               'Cell1': 3.718, 'Cell2': 3.735, 'Cell3': 3.709, 'Cell4': 3.786, 'Cell5': 3.733, 'Cell6': 3.696,
               'Cell7': 3.738, 'Cell8': 3.694, 'Cell9': 3.71, 'Cell10': 3.734, 'Cell11': 3.758, 'Cell12': 3.75,
               'Cell13': 3.772, 'Cell14': 0.0, 'Cell15': 0.0, 'Cell16': 0.0, 'Cell17': 0.0, 'Cell18': 0.0,
               'Cell19': 0.0, 'Cell20': 0.0, 'Cell21': 0.0, 'Cell22': 0.0, 'Cell23': 0.0, 'Cell24': 0.0}
    data = {'name': 'Antw33-BMS',
            'payload': json.dumps(payload),
            'time': datetime.datetime.now().timestamp()
            }
    while True:
        try:
            sleep(5)
            logger.debug(f"Incoming Sensor Data [{data['name']}]")
            task = {
                "name": "write_sensor_data",
                "data": data
            }
            main_task_queue.put(task)
        except:
            break

    return


def main():
    try:
        # Multiprocessing Variables, used for sending data from and to another process or thread
        processes = []
        manager = mp.Manager()
        main_task_queue = manager.Queue()
        mqtt_service_queue = manager.Queue()

        try:
            # Starting the MQTT Service
            mqtt_service = mp.Process(target=mqtt.start_service,
                                      args=(mqtt_service_queue, main_task_queue, config_string), daemon=True)
            processes.append(mqtt_service)
            mqtt_service.start()
            logger.info("MQTT Service started")

            mqtt_task = {
                "name": "publish",
                "topic": "test",
                "payload": "Test"
            }
            mqtt_service_queue.put(mqtt_task)

            # if debug:
            #     # Relayer is a dummy services that relays sensor data from actual broker to development branch
            #     # useful for developing using real-life sensor data without altering the live version
            #     relayer_thread = mp.Process(target=relayer.initialize,
            #                                 args=(mqtt_service_queue, "192.168.1.22", 1883, "relayer", "relayer"),
            #                                 daemon=True)
            #     relayer_thread.start()
            #     logger.info("Relayer started")
            #
            #     # Reset Sqlite Database
            #     reinitialize_tables()
            #
            #     # Testing Bluetooth but with static data
            #     bluetooth_thread = mp.Process(target=dummy_bluetooth, args=(main_task_queue,), daemon=True)
            #     bluetooth_thread.start()
            #     logger.info("Bluetooth service started")
            # else:
            #     # Real Bluetooth services
            #     bluetooth_thread = mp.Process(target=bluetooth.initialize, args=(main_task_queue,), daemon=True)
            #     bluetooth_thread.start()
            #     logger.info("Bluetooth service started")
            #
            # # Start the main process loop
            # main_periodical_thread = threading.Thread(target=main_periodical_loop, args=[mqtt_service_queue],
            #                                           daemon=True)
            # main_periodical_thread.start()
            # logger.info("Main loop started")
            #
            # asyncio.run(send_configurations(mqtt_service_queue))
            # asyncio.run(main_task_loop(main_task_queue, mqtt_service_queue))

        except KeyboardInterrupt:
            logger.error \
                ("User interrupt")
            logger.warning("Shutting down services, manual restart needed...")
            mqtt_service_queue.put("STOP")
            main_task_queue.put("STOP")

            # Terminating running processes
            for process in processes:
                process.kill()

            exit()

        except Exception as e:
            mqtt_service_queue.put("STOP")
            main_task_queue.put("STOP")

            # Terminating running processes
            for process in processes:
                process.kill()

            global retry_count
            logger.exception(f"Something went wrong when starting the app: {e}")

            if retry_count >= 5:
                logger.error("App still failed after 5 times, exiting...")
                logger.warning("Please check if the server is configured correctly then restart the server")
                logger.warning("You can visit github.com/artinmare/homesolar for examples on how to setup the server")
                exit()

            try:
                logger.warning("Restarting the app, please CTRL+C to stopped the process!")
                sleep(5)
            except Exception as e:
                logger.info(f"App is closing... [{e}]")
                exit()

            retry_count += 1
            main()
        finally:
            for process in processes:
                process.join()
    except:
        logger.warning("Shutting down the app")
        exit()


# Send configurations to the broker
async def send_configurations(mqtt_task_queue):
    configs = await database.get_configurations()
    mqtt_task = {
        "name": "publish",
        "topic": mqtt.MqttTopic.CONFIGURATION,
        "payload": json.dumps(configs)
    }
    mqtt_task_queue.put(mqtt_task)


# Main task loop is used for sending task to different process
async def main_task_loop(main_task_queue, mqtt_task_queue):
    global connected_clients
    try:
        is_interrupt = False
        while True:
            try:
                logger.debug("Waiting for task!")
                task = main_task_queue.get()
                logger.debug(f"Task received [{task}]")
                logger.debug(f"Task remaining [{main_task_queue.qsize()}]")
                if task == "STOP":
                    break

                try:
                    if task["name"] == "write_sensor_data":
                        await asyncio.gather(database.write_sensor_to_sqlite(task["data"]),
                                             database.write_sensor_to_influxdb(task["data"]))
                    elif task["name"] == "add_client":
                        connected_clients.append(task["client_id"])
                    elif task["name"] == "remove_client":
                        connected_clients.remove(task["client_id"])
                    elif task["name"] == "chart_data":
                        chart_data = await database.get_chart_data(task["date"], task["timescale"])
                        chart_data["request_id"] = task["request_id"]
                        mqtt_task = {
                            "name": "publish",
                            "topic": mqtt.MqttTopic.CLIENT[:-1] + f"{task['client_id']}/response",
                            "payload": json.dumps(chart_data, cls=DateTimeEncoder)
                        }
                        mqtt_task_queue.put(mqtt_task)
                    # elif task["name"] == "send_periodical_data":
                    #
                    else:
                        logger.warning(f"Unknown task is issued, discarding... [{task}]")

                except Exception as e:
                    logger.warning(f"Invalid task is issued, discarding... [{e}]")

            except KeyboardInterrupt:
                is_interrupt = True
                break
            except Exception as e:
                logger.exception(
                    f"Something unexpected happened when running Main Task Loop, shutting down the server [{e}]")
                break
        if is_interrupt:
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        logger.error(f"User interrupt")
    except Exception as e:
        logger.exception(f"Something went wrong running the main task loop [{e}]")
        raise Exception("Unexpected Error on Main Task Loop")


# Main periodical loop is a loop thread for sending periodical data to the android clients if any is connected
# the reason it's running on it own thread is for cleaner code purposes, since main_task_loop is event-based loop
# and main_periodical_loop is time-based loop
def main_periodical_loop(mqtt_task_queue, request_queue=None):
    global connected_clients
    elapsed = 0
    update_time = 0

    async def send_periodic_data(is_update):
        await asyncio.gather(mqtt_interface.send_summary(mqtt_task_queue, is_update),
                             mqtt_interface.send_battery(mqtt_task_queue))

    while True:
        try:
            if connected_clients and perf_counter() - elapsed >= config.homesolar_config["CLIENT"]["response_time"]:
                if perf_counter() - update_time >= config.homesolar_config["CLIENT"]["update_time"]:
                    update = True
                    update_time = perf_counter()
                else:
                    update = False
                elapsed = perf_counter()
                asyncio.run(send_periodic_data(update))

        except:
            break


def running_random_test():
    for i in range(100):
        start_time = perf_counter()
        print(datetime.datetime.now().timestamp())
        print(f"{perf_counter() - start_time} sec(s)")


if __name__ == '__main__':
    debug = True
    retry_count = 0
    connected_clients = []
    if not debug:
        # Set Logger Level
        logger.remove()
        logger.add(sys.stderr, level="INFO")
    logger.add(config.homesolar_config["LOGGER"]["log_location"] + "file_{time}.log", rotation="100 MB",
               retention="7 days")

    logger.info("Starting the App...")
    main()
    # running_random_test()
