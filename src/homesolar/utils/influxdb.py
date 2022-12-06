import re

from loguru import logger

from ..utils import config


def generate_combined_tables_flux(measurements, fields, start_time, end_time, timescale,
                                  combined_measurement="combined_measurement", combined_field="combined_field",
                                  operator="+", bucket=None):
    if bucket is None:
        bucket = config.homesolar_config['INFLUXDB']['default_bucket']

    additional_query = ""
    yield_str = ""
    aggregate_str = '''
    |> aggregateWindow (every:1m, fn: mean, createEmpty: false)
    |> toFloat()
    |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
    |> map(fn: (r) => ({r with _value: r._value/60.0}))
    '''

    raw_data_query = f'''
    import "timezone"
    option location = timezone.location(name: "{config.homesolar_config['INFLUXDB']['timezone']}")
    '''
    data_query = ""
    tables = "{"
    values = "{r with _value:"
    regex_filter = re.compile(r'[^a-zA-Z]+')
    add_measurement_field = "{" + f'r with _measurement: "{combined_measurement}", _field:"{combined_field}"' + "}"

    if timescale == "DAY":
        yield_str = '|> yield(name: "formatted_data")'
        aggregate_str = '''
        |> aggregateWindow (every:10s, fn: mean, createEmpty: false)
        |> toFloat()
        |> aggregateWindow(every: 5m, fn: sum, createEmpty: true)
        |> map(fn: (r) => ({r with _value: r._value/30.0}))
        '''
        data_query = '''
        |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
        |> map(fn: (r) => ({r with _value: r._value/12.0}))
        '''
    elif timescale == "MONTH":
        additional_query = f'''
            formatted_data = data
            |> aggregateWindow(every: 1d, fn: sum, createEmpty: true)
            |> map(fn: (r) => ({add_measurement_field}))
            |> yield(name: "formatted_data")
        '''
    elif timescale == "YEAR":
        additional_query = f'''
            formatted_data = data
            |> aggregateWindow(every: 1mo, fn: sum, createEmpty: true)
            |> map(fn: (r) => ({add_measurement_field}))
            |> yield(name: "formatted_data")
        '''

    for measurement, field in zip(measurements, fields):
        name = re.sub(regex_filter, "", f'{measurement}_{field}')
        raw_data_query += f'''
        {name} = from(bucket: "{bucket}")
        |> range(start: {start_time}, stop: {end_time})
        |> filter(fn: (r) => r["_measurement"] == "{measurement}")
        |> filter(fn: (r) => r["_field"] == "{field}")
        {aggregate_str}
        '''

        tables += f"{name}:{name},"
        values += f"r._value_{name}{operator}"

    tables = tables[:-1] + "}"
    values = values[:-1]

    result = f'''
    {raw_data_query}

    combined_value = join(tables: {tables}, on:["_time"])
    |> map(fn:(r) => ({values},_measurement:"{combined_measurement}",_field:"{combined_field}"{'}'}))
    {yield_str}

    data = combined_value
    {data_query}

    {additional_query}

    sum = data
    |> sum()
    |> yield(name: "sum")
    '''

    logger.debug(result)
    return result


def generate_flux(measurement, field, start_time, end_time, timescale, bucket=None):
    if bucket is None:
        bucket = config.homesolar_config['INFLUXDB']['default_bucket']

    data_query = ""
    additional_query = ""
    yield_str = '''
    |> aggregateWindow (every:1m, fn: mean, createEmpty: false)
    |> toFloat()
    |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
    |> map(fn: (r) => ({r with _value: r._value/60.0}))
    '''

    if timescale == "DAY":
        yield_str = '''
        |> aggregateWindow (every:10s, fn: mean, createEmpty: false)
        |> toFloat()
        |> aggregateWindow(every: 5m, fn: sum, createEmpty: true)
        |> map(fn: (r) => ({r with _value: r._value/30.0}))
        |> yield(name: "formatted_data")
        '''
        data_query = '''
        |> aggregateWindow(every: 1h, fn: sum, createEmpty: false)
        |> map(fn: (r) => ({r with _value: r._value/12.0}))
        '''
    elif timescale == "MONTH":
        additional_query = f'''
        formatted_data = data
        |> aggregateWindow(every: 1d, fn: sum, createEmpty: true)
        |> yield(name: "formatted_data")
        '''
    elif timescale == "YEAR":
        additional_query = f'''
        formatted_data = data
        |> aggregateWindow(every: 1mo, fn: sum, createEmpty: true)
        |> yield(name: "formatted_data")
        '''

    result = f'''
    import "timezone"
    option location = timezone.location(name: "{config.homesolar_config['INFLUXDB']['timezone']}")
        
    raw_data = from(bucket: "{bucket}")
    |> range(start: {start_time}, stop: {end_time})
    |> filter(fn: (r) => r["_measurement"] == "{measurement}")
    |> filter(fn: (r) => r["_field"] == "{field}")
    {yield_str}

    data = raw_data
    {data_query}

    {additional_query}

    sum = data
    |> sum()
    |> yield(name: "sum")
    '''
    logger.debug(result)
    return result


def generate_measurements_flux(bucket=None):
    if bucket is None:
        bucket = config.homesolar_config['INFLUXDB']['default_bucket']

    query = f'''
    import "influxdata/influxdb/schema"
    schema.measurements(bucket: "{bucket}")
    '''

    return query


def generate_fields_flux(measurement, bucket=None):
    if bucket is None:
        bucket = config.homesolar_config['INFLUXDB']['default_bucket']

    query = f'''
        import "influxdata/influxdb/schema"
        schema.measurementFieldKeys(bucket: "{bucket}", measurement: "{measurement}")
        '''

    return query


def serialize(tables, timescale="DAY"):
    data = []
    try:
        for idx, table in enumerate(tables):
            field = {"table": idx}
            values = []
            for row in table:
                value = {}
                try:
                    field["measurement"] = row.values["_measurement"]
                    field["field"] = row.values["_field"]
                    value["time"] = row.values["_time"]
                except Exception as e:
                    logger.warning(f"Something went wrong when serializing data, skipping... [{e}]")

                value["value"] = row.values["_value"]
                values.append(value)

            # Check length of values saved
            field["name"] = check_table_name(len(values))
            field["values"] = values

            data.append(field)
    except Exception as e:
        logger.error(e)
    finally:
        return data


def check_table_name(length: int):
    if length == 1:
        return "sum"

    return "data"
