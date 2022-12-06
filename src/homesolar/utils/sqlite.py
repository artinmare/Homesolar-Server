from loguru import logger
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import declarative_base

# Models for each tables
Base = declarative_base()


class SensorData(Base):
    __tablename__ = "sensor_data"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True)
    value = Column(String)


def mapped_for_upsert(data):
    measurement = data["measurement"]
    fields = data["fields"]
    sensor_datas = {}
    for field, value in fields.items():
        sensor_data = {
            "name": f"{measurement}#{field}",
            "value": value
        }
        sensor_datas[f"{measurement}#{field}"] = sensor_data

    return sensor_datas

def generate_add_sensor_data_sql(data):
    sensor_datas = []
    for sensor in data:
        stmt = insert(SensorData).values(
            name=sensor["name"],
            value=sensor["value"]
        )
        do_update_stmt = stmt.on_conflict_do_update(
            index_elements=['name'],
            set_=dict(value=stmt.excluded.value)
        )
        sensor_datas.append(do_update_stmt)

    return sensor_datas


def generate_get_sensor_data_sql(measurement, field):
    stmt = select(SensorData).where(SensorData.name == f'{measurement}#{field}')

    return stmt
