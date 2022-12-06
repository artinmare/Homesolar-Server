import json
from ..utils.mqtt import MqttTopic
from ..interfaces import database
from ..utils import datetime, data_formatter, config, bluetooth

today_production = 0
today_independence = 0


async def send_summary(mqtt_queue, update=False):
    global today_independence, today_production

    payload = {
        "solar_production": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['solar_production_measurement'],
            field=config.homesolar_config['DATA']['solar_production_field']
        ), "battery_usage": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['battery_power_measurement'],
            field=config.homesolar_config['DATA']['battery_power_field']
        ), "battery_charge": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['battery_charge_measurement'],
            field=config.homesolar_config['DATA']['battery_charge_field']
        ), "grid_usage": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['grid_power_measurement'],
            field=config.homesolar_config['DATA']['grid_power_field']
        ), "inverter_usage": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['inverter_power_measurement'],
            field=config.homesolar_config['DATA']['inverter_power_field']
        )}

    if payload["grid_usage"] is None or payload["inverter_usage"] is None:
        payload["home_usage"] = None
    else:
        payload["home_usage"] = payload["grid_usage"] + payload["inverter_usage"]

    if update:
        payload["today_production"] = \
            today_production = (await database.get_solar_production(date=datetime.get_today(), timescale="DAY"))["sum"]
        grid = (await database.get_grid_usage(date=datetime.get_today(), timescale="DAY"))["sum"]
        inverter = (await database.get_inverter_usage(date=datetime.get_today(), timescale="DAY"))["sum"]
        payload["today_independence"] = today_independence = (inverter / (grid + inverter)) * 100.0
    else:
        payload["today_production"] = today_production
        payload["today_independence"] = today_independence

    task = {
        "name": "publish",
        "topic": MqttTopic.SUMMARY,
        "payload": json.dumps(payload),
        "retain": True
    }
    mqtt_queue.put(task)


async def send_battery(mqtt_queue):
    payload = {
        "status": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['battery_status_measurement'],
            field=config.homesolar_config['DATA']['battery_status_field']
        ), "pack_voltage": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['battery_voltage_measurement'],
            field=config.homesolar_config['DATA']['battery_voltage_field']
        ), "pack_amperage": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['battery_amperage_measurement'],
            field=config.homesolar_config['DATA']['battery_amperage_field']
        ), "pack_power": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['battery_power_measurement'],
            field=config.homesolar_config['DATA']['battery_power_field']
        ), "soc": await database.get_sensor_data(
            measurement=config.homesolar_config['DATA']['battery_charge_measurement'],
            field=config.homesolar_config['DATA']['battery_charge_field']
        )}

    if payload["status"] is not None:
        payload["status"] = bluetooth.MOSFET_Discharge_St[int(payload["status"])]

    single_cell = config.homesolar_config['DATA']['battery_single_cell']
    formatted_cells = []

    cells = config.homesolar_config['DATA']['battery_cells_fields'].split()
    balances = config.homesolar_config['DATA']['battery_cells_balance_fields'].split()
    if not single_cell:
        for index, cell in enumerate(cells):
            formatted_cell = {
                "name": f"Cell {index+1}",
                "balance": await database.get_sensor_data(
                    measurement=config.homesolar_config['DATA']['battery_cells_balance_measurement'],
                    field=balances[index]
                ) == 1,
                "voltage": await database.get_sensor_data(
                    measurement=config.homesolar_config['DATA']['battery_cells_measurement'],
                    field=cells[index]
                )
            }
            formatted_cells.append(formatted_cell)

    payload["cells"] = formatted_cells

    task = {
        "name": "publish",
        "topic": MqttTopic.BATTERY,
        "payload": json.dumps(payload),
        "retain": True
    }
    mqtt_queue.put(task)

