import asyncio
import datetime
import json
import math
import time
from binascii import unhexlify

import serial
from loguru import logger

from ..interfaces import database
from ..utils import config, bluetooth, multiprocessing


class Parameter:
    def __init__(self, data, field, start_byte, stop_byte, byte_order='big', signed=False, precision=1.0):
        self.field = field
        self.start_byte = start_byte
        self.stop_byte = stop_byte
        self.byte_order = byte_order
        self.signed = signed
        self.precision = precision
        self.data = data[start_byte: stop_byte]
        self.value = int.from_bytes(data[self.start_byte: self.stop_byte], byteorder=self.byte_order,
                                    signed=self.signed) * self.precision
        if self.precision < 1:
            self.value = round(self.value, math.ceil(math.log(1 / self.precision, 10)))

    def get_bits(self, index=None):
        string_bytes = self.data
        bytes_list = []
        for i in range(len(string_bytes)):
            bytes_list.append(string_bytes[i:i + 1])

        bits = []
        for byte in bytes_list:
            for i in range(8):
                bits.append((ord(byte) >> i) & 1)
        return bits


def initialize(main_task_queue):
    try:
        ser = serial.Serial(
            port=config.homesolar_config['BLUETOOTH']['port'],
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS)

        try:
            ser.open()
            time.sleep(1)
        except Exception as e:
            ser.close()
            ser.open()
            logger.warning(f"Something went wrong when trying to open Bluetooth as a Serial Connection [{e}]")

        first_boot = True
        while True:
            try:
                ser.write(unhexlify(config.homesolar_config['BLUETOOTH']['request_code']))
                if first_boot:
                    time.sleep(1)
                    first_boot = False
                antw33 = ser.read(140)

                params = [Parameter(antw33, "Voltage", 4, 6, 'big', True, 0.1),
                          Parameter(antw33, "Current", 70, 74, 'big', True, 0.1),
                          Parameter(antw33, "Power", 111, 115, 'big', True),
                          Parameter(antw33, "Capacity", 75, 79, 'big', False, 0.000001),
                          Parameter(antw33, "ChargeStatus", 103, 104), Parameter(antw33, "DischargeStatus", 104, 105),
                          Parameter(antw33, "BalanceStatus", 105, 106), Parameter(antw33, "BalanceCells", 133, 136),
                          Parameter(antw33, "Temp1", 91, 93), Parameter(antw33, "Temp2", 93, 95),
                          Parameter(antw33, "Temp3", 95, 97), Parameter(antw33, "Temp4", 97, 99),
                          Parameter(antw33, "Temp5", 99, 101), Parameter(antw33, "Temp6", 101, 103),
                          Parameter(antw33, "MinCell", 118, 119), Parameter(antw33, "MaxCell", 115, 116),
                          Parameter(antw33, "MinVolt", 119, 121, 'big', False, 0.001),
                          Parameter(antw33, "MaxVolt", 116, 118, 'big', False, 0.001),
                          Parameter(antw33, "AvgVolt", 121, 123, precision=0.001),
                          Parameter(antw33, "Cell1", 6, 8, 'big', False, 0.001),
                          Parameter(antw33, "Cell2", 8, 10, 'big', False, 0.001),
                          Parameter(antw33, "Cell3", 10, 12, 'big', False, 0.001),
                          Parameter(antw33, "Cell4", 12, 14, 'big', False, 0.001),
                          Parameter(antw33, "Cell5", 14, 16, 'big', False, 0.001),
                          Parameter(antw33, "Cell6", 16, 18, 'big', False, 0.001),
                          Parameter(antw33, "Cell7", 18, 20, 'big', False, 0.001),
                          Parameter(antw33, "Cell8", 20, 22, 'big', False, 0.001),
                          Parameter(antw33, "Cell9", 22, 24, 'big', False, 0.001),
                          Parameter(antw33, "Cell10", 24, 26, 'big', False, 0.001),
                          Parameter(antw33, "Cell11", 26, 28, 'big', False, 0.001),
                          Parameter(antw33, "Cell12", 28, 30, 'big', False, 0.001),
                          Parameter(antw33, "Cell13", 30, 32, 'big', False, 0.001),
                          Parameter(antw33, "Cell14", 32, 34, 'big', False, 0.001),
                          Parameter(antw33, "Cell15", 34, 36, 'big', False, 0.001),
                          Parameter(antw33, "Cell16", 36, 38, 'big', False, 0.001),
                          Parameter(antw33, "Cell17", 38, 40, 'big', False, 0.001),
                          Parameter(antw33, "Cell18", 40, 42, 'big', False, 0.001),
                          Parameter(antw33, "Cell19", 42, 44, 'big', False, 0.001),
                          Parameter(antw33, "Cell20", 44, 46, 'big', False, 0.001),
                          Parameter(antw33, "Cell21", 46, 48, 'big', False, 0.001),
                          Parameter(antw33, "Cell22", 48, 50, 'big', False, 0.001),
                          Parameter(antw33, "Cell23", 50, 52, 'big', False, 0.001),
                          Parameter(antw33, "Cell24", 52, 54, 'big', False, 0.001)]

                voltage = 0
                fields = {}
                for data in params:
                    fields[data.field] = data.value

                    if data.field == 'AvgVolt':
                        voltage = data.value

                    if data.field == 'BalanceCells':
                        for index, bal in enumerate(data.get_bits()):
                            fields[f"Bal{index}"] = bal

                    if data.field == 'AvgVolt':
                        fields['SoC'] = bluetooth.ManualSoC().get_soc(data.value)

                if voltage == 0:
                    ser.close()
                    time.sleep(1)
                    ser.open()
                    time.sleep(1)

                data = {
                    "name": "Antw33-BMS",
                    "payload": json.dumps(fields),
                    'time': datetime.datetime.now().timestamp()
                }
                logger.debug(f"Incoming Sensor Data [{data['name']}]")
                task = {
                    "name": "write_sensor_data",
                    "data": data
                }
                main_task_queue.put(task)
                time.sleep(5)
            except:
                ser.close()
                time.sleep(1)
                ser.open()
                time.sleep(1)

    except Exception as ex:
        print(ex)
    finally:
        try:
            ser.close()
        except Exception as e:
            logger.warning(f"Something went wrong when trying to close Bluetooth as Serial Connection [{e}]")
