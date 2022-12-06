import asyncio
from loguru import logger

from ..interfaces import database
from ..interfaces import mqtt
from ..services import mqtt as mqtt_services

POISON_PILL = "STOP"
homesolar_database_queue = None
homesolar_task_queue = None


def load_queue(queue1, queue2):
    global homesolar_database_queue, homesolar_task_queue
    homesolar_database_queue = queue1
    homesolar_task_queue = queue2


# def process_task(queue):
#     try:
#         while True:
#             new_data = queue.get()
#
#             if new_data == POISON_PILL:
#                 break
#
#             asyncio.run(database.write_sensor_data(new_data))
#     except:
#         pass
#     finally:
#         return


def process_task(queue):
    try:
        while True:
            logger.debug("Waiting for task")
            task = queue.get()

            logger.debug(f"Task received [{task}]")

            if task == POISON_PILL:
                break

            try:
                if task["name"] == "write_sensor_data":
                    asyncio.run(database.write_sensor_data(task["data"]))
                elif task["name"] == "send_summary":
                    mqtt.send_summary(mqtt_services.mqtt_client, task["update"])
                elif task["name"] == "send_battery":
                    mqtt.send_battery(mqtt_services.mqtt_client)
                elif task["name"] == "chart_data":
                    database.get_chart_data(task["date"], task["timescale"])
                elif task["name"] == "update_config":
                    pass
                else:
                    logger.warning(f"Invalid task, discarding.. [{task}]")
            except Exception as e:
                logger.exception(f"Something went wrong when trying to do a task [{e}]")
    except:
        pass
    finally:
        return
