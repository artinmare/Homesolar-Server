import asyncio
import json
from time import perf_counter

from loguru import logger

# project's imports
from ..services import influxdb, sqlite
from ..utils import datetime, config, data_formatter
from ..utils import influxdb as influx_utils
from ..utils import sqlite as sqlite_utils
from ..utils.sqlite import SensorData


# Used on All database
async def write_sensor_data(data):
    start_time = perf_counter()
    sensor_data = data_formatter.format_sensor_data(data)
    await influxdb.write(sensor_data)
    logger.debug("is it waiting ?")
    mapped_data = sqlite_utils.mapped_for_upsert(sensor_data)
    await sqlite.bulk_upsert_sensors(mapped_data)
    logger.debug(json.dumps(sensor_data))
    logger.debug(f"Time taken for entire sensor_data_write: {perf_counter() - start_time} second(s)")


async def write_sensor_to_influxdb(data):
    await influxdb.write(data_formatter.format_sensor_data(data))


async def write_sensor_to_sqlite(data):
    await sqlite.bulk_upsert_sensors(sqlite_utils.mapped_for_upsert(data_formatter.format_sensor_data(data)))


# Used only on InfluxDB
async def get_battery_charge(date):
    flux = influx_utils.generate_flux(
        config.homesolar_config['DATA']['battery_charge_measurement'],
        config.homesolar_config['DATA']['battery_charge_field'],
        datetime.stringify_timestamp(date),
        datetime.get_next_day(date), "DAY"
    )
    result = await influxdb.query(flux)
    logger.debug(result)
    return data_formatter.simplify_serialized_data(influx_utils.serialize(result, "DAY"))


async def get_battery_usage(date, timescale):
    start_time, stop_time = datetime.get_date_pair(date, timescale)
    flux = influx_utils.generate_flux(
        config.homesolar_config['DATA']['battery_power_measurement'],
        config.homesolar_config['DATA']['battery_power_field'],
        start_time,
        stop_time,
        timescale
    )
    result = await influxdb.query(flux)
    logger.debug(result)
    return data_formatter.simplify_serialized_data(influx_utils.serialize(result, timescale))


async def get_solar_production(date, timescale):
    start_time, stop_time = datetime.get_date_pair(date, timescale)
    flux = influx_utils.generate_flux(
        config.homesolar_config['DATA']['solar_production_measurement'],
        config.homesolar_config['DATA']['solar_production_field'],
        start_time,
        stop_time,
        timescale
    )
    result = await influxdb.query(flux)
    logger.debug(result)
    return data_formatter.simplify_serialized_data(influx_utils.serialize(result, timescale))


async def get_grid_usage(date, timescale):
    start_time, stop_time = datetime.get_date_pair(date, timescale)
    flux = influx_utils.generate_flux(
        config.homesolar_config['DATA']['grid_power_measurement'],
        config.homesolar_config['DATA']['grid_power_field'],
        start_time,
        stop_time,
        timescale
    )
    result = await influxdb.query(flux)
    logger.debug(result)
    return data_formatter.simplify_serialized_data(influx_utils.serialize(result, timescale))


async def get_inverter_usage(date, timescale):
    start_time, stop_time = datetime.get_date_pair(date, timescale)
    flux = influx_utils.generate_flux(
        config.homesolar_config['DATA']['inverter_power_measurement'],
        config.homesolar_config['DATA']['inverter_power_field'],
        start_time,
        stop_time,
        timescale
    )
    result = await influxdb.query(flux)
    logger.debug(result)
    return data_formatter.simplify_serialized_data(influx_utils.serialize(result, timescale))


async def get_home_usage(date, timescale):
    start_time, stop_time = datetime.get_date_pair(date, timescale)
    flux = influx_utils.generate_combined_tables_flux(
        [config.homesolar_config['DATA']['grid_power_measurement'],
         config.homesolar_config['DATA']['inverter_power_measurement']],
        [config.homesolar_config['DATA']['grid_power_field'],
         config.homesolar_config['DATA']['inverter_power_field']],
        start_time,
        stop_time,
        timescale
    )
    logger.debug(flux)
    result = await influxdb.query(flux)
    return data_formatter.simplify_serialized_data(influx_utils.serialize(result, timescale))


async def get_chart_data(date, timescale):
    solar_production = await get_solar_production(date, timescale)
    battery_usage = await get_battery_usage(date, timescale)
    grid_usage = await get_grid_usage(date, timescale)
    inverter_usage = await get_inverter_usage(date, timescale)
    home_usage = await get_home_usage(date, timescale)

    if timescale == "DAY":
        battery_charge = await get_battery_charge(date)
    else:
        battery_charge = None

    data = {
        "solar_production": solar_production,
        "battery_usage": battery_usage,
        "grid_usage": grid_usage,
        "inverter_usage": inverter_usage,
        "home_usage": home_usage,
        "battery_charge": battery_charge
    }
    return data


async def get_measurements(bucket=None):
    flux = influx_utils.generate_measurements_flux(bucket)
    tables = await influxdb.query(flux)
    measurements = [row.values["_value"] for table in tables for row in table]

    logger.debug(f"Measurements: {measurements}")
    return measurements


async def get_fields(measurement, bucket=None):
    flux = influx_utils.generate_fields_flux(measurement, bucket)
    tables = await influxdb.query(flux)
    fields = [row.values["_value"] for table in tables for row in table]

    logger.debug(f"Fields: {fields}")
    return fields

async def get_configurations():
    configurations = []
    measurements = await get_measurements()
    logger.debug(measurements)
    for measurement in measurements:

        fields = await get_fields(measurement)
        configuration = {"measurement": measurement, "fields": fields}
        configurations.append(configuration)

    return configurations

# Used only on Sqlite
async def get_sensor_data(measurement, field):
    sensor_data = await sqlite.query(SensorData, SensorData.name.in_([f"{measurement}#{field}"]))
    if sensor_data is None:
        logger.warning("No sensor data with specified name found")
        return None
    else:
        for sensor in sensor_data:
            return data_formatter.parse_to_float_if_possible(sensor.value)
