from time import perf_counter

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.future import select as future_select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, scoped_session
from ..utils import sqlite, config
from ..utils.sqlite import SensorData, generate_add_sensor_data_sql

# Not Async
sqlite_engine = create_engine(f"sqlite://{config.homesolar_config['SQLITE']['database']}", echo=False)
sqlite_session = scoped_session(sessionmaker(bind=sqlite_engine, expire_on_commit=False))


# Async
# sqlite_engine = create_async_engine(f"sqlite+aiosqlite://{config.homesolar_config['SQLITE']['database']}", echo=False)
# sqlite_session = scoped_session(sessionmaker(bind=sqlite_engine, expire_on_commit=False, class_=AsyncSession))


def reinitialize_tables():
    sqlite.Base.metadata.drop_all(sqlite_engine)
    sqlite.Base.metadata.create_all(sqlite_engine)


async def async_reinitialize_tables():
    async with sqlite_engine.begin() as conn:
        await conn.run_sync(sqlite.Base.metadata.drop_all)
        await conn.run_sync(sqlite.Base.metadata.create_all)


async def bulk_upsert_sensors(sensors_data):
    try:
        start_time = perf_counter()
        entries_to_update = []
        entries_to_put = []
        with sqlite_session() as session:

            # Find all customers that needs to be updated and build mappings
            for each in (
                    session.query(SensorData).filter(SensorData.name.in_(sensors_data.keys()))
            ):
                sensor = sensors_data.pop(each.name)
                entries_to_update.append({"id": each.id, "name": sensor["name"], "value": sensor["value"]})

            # Bulk mappings for everything that needs to be inserted
            for sensor in sensors_data.values():
                entries_to_put.append({"name": sensor["name"], "value": sensor["value"]})

            if entries_to_put:
                session.bulk_insert_mappings(SensorData, entries_to_put)
            if entries_to_update:
                session.bulk_update_mappings(SensorData, entries_to_update)
            session.commit()

        # if entries_to_put:
        #     write(generate_add_sensor_data_sql(entries_to_put))
        logger.debug(f"Time taken: {perf_counter() - start_time} second(s)")

    except Exception as e:
        logger.exception(f"SQLITE ERROR [{e}]]")


def write(data):
    try:
        start_time = perf_counter()
        with sqlite_session() as session:
            with session.begin():

                if type(data) is list:
                    for stmt in data:
                        session.execute(stmt)
                else:
                    session.execute(data)
            session.commit()

        logger.debug(f"Time taken: {perf_counter() - start_time} second(s)")
        logger.info("Data saved successfully!")
    except Exception as e:
        logger.exception(f"Data not saved! [{e}]")


async def query(table, filters):
    result = None
    try:
        with sqlite_session() as session:
            result = session.query(table).filter(filters)
            session.commit()
    except Exception as e:
        logger.exception(f"Failed to query data [{e}]")
    finally:
        return result


async def async_write(data):
    try:
        start_time = perf_counter()
        async with sqlite_session() as session:
            async with session.begin():

                if type(data) is list:
                    for stmt in data:
                        await session.execute(stmt)
                else:
                    await session.execute(data)
            await session.commit()
            await session.close()

        logger.debug(f"Time taken: {perf_counter() - start_time} second(s)")
        logger.info("Data saved successfully!")
    except Exception as e:
        logger.exception(f"Data not saved! [{e}]")


async def execute(statement):
    result = None
    try:
        with sqlite_session() as session:
            with session.begin():
                result = session.execute(statement)
            session.commit()
    except Exception as e:
        logger.exception(f"Something went wrong when executing an sql! [{e}]")
    finally:
        return result


async def async_execute(statement):
    result = None
    try:
        async with sqlite_session() as session:
            async with session.begin():
                result = await session.execute(statement)
            await session.commit()
            await session.close()
    except Exception as e:
        logger.exception(f"Something went wrong when executing an sql! [{e}]")
    finally:
        return result
