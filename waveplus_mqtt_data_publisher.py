# MIT License
#
# Copyright (c) 2018-2021 Airthings AS, troinine
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# https://airthings.com

# ===============================
# Module import dependencies
# ===============================

from bluepy.btle import UUID, Peripheral, Scanner, DefaultDelegate
import paho.mqtt.publish as publish
import sys
import time
import struct
import json

def getConfig():
    keys = {}
    with open('config.properties') as f:
        for line in f:
            if '=' in line:
                name, value = line.split('=', 1)
                keys[name.strip()] = value.strip()

    return keys


# ====================================
# Utility functions for WavePlus class
# ====================================

def parseSerialNumber(ManuDataHexStr):
    if ManuDataHexStr is None or ManuDataHexStr == "None":
        SN = "Unknown"
    else:
        ManuData = bytearray.fromhex(ManuDataHexStr)

        if ((ManuData[1] << 8) | ManuData[0]) == 0x0334:
            SN = ManuData[2]
            SN |= (ManuData[3] << 8)
            SN |= (ManuData[4] << 16)
            SN |= (ManuData[5] << 24)
        else:
            SN = "Unknown"
    return str(SN)


# ===============================
# Class WavePlus
# ===============================

class WavePlus():

    def __init__(self, SerialNumber):
        self.periph = None
        self.curr_val_char = None
        self.MacAddr = None
        self.SN = SerialNumber
        self.uuid = UUID("b42e2a68-ade7-11e4-89d3-123b93f75cba")

    def connect(self, retry_limit=3):
        attempt = 0
        while attempt < retry_limit:
            try:
                if self.MacAddr is None:
                    self._discover_device()
                if self.periph is None:
                    self.periph = Peripheral(self.MacAddr)
                if self.curr_val_char is None:
                    self.curr_val_char = self.periph.getCharacteristics(uuid=self.uuid)[0]
                return
            except (Exception) as e:
                print(f"Connection attempt {attempt + 1} failed: {e}")
                self.disconnect()
                attempt += 1
                time.sleep(1)

        print("ERROR: Could not connect after several attempts.")
        sys.exit(1)

    def _discover_device(self):
        scanner = Scanner().withDelegate(DefaultDelegate())
        for _ in range(50):
            devices = scanner.scan(0.1)
            for dev in devices:
                ManuData = dev.getValueText(255)
                SN = parseSerialNumber(ManuData)
                if SN == self.SN:
                    self.MacAddr = dev.addr
                    return
        print("ERROR: Could not find device after scanning.")
        sys.exit(1)

    def read(self):
        if self.curr_val_char is None:
            print("ERROR: Devices are not connected.")
            sys.exit(1)
        rawdata = self.curr_val_char.read()
        rawdata = struct.unpack('<BBBBHHHHHHHH', rawdata)
        sensors = Sensors()
        sensors.set(rawdata)
        return sensors

    def disconnect(self):
        if self.periph is not None:
            self.periph.disconnect()
            self.periph = None
            self.curr_val_char = None


# ===================================
# Class Sensor and sensor definitions
# ===================================

NUMBER_OF_SENSORS = 7
SENSOR_IDX_HUMIDITY = 0
SENSOR_IDX_RADON_SHORT_TERM_AVG = 1
SENSOR_IDX_RADON_LONG_TERM_AVG = 2
SENSOR_IDX_TEMPERATURE = 3
SENSOR_IDX_REL_ATM_PRESSURE = 4
SENSOR_IDX_CO2_LVL = 5
SENSOR_IDX_VOC_LVL = 6


class Sensors():
    def __init__(self):
        self.sensor_version = None
        self.sensor_data = [None] * NUMBER_OF_SENSORS
        self.sensor_units = ["%rH", "Bq/m3", "Bq/m3", "degC", "hPa", "ppm", "ppb"]

    def set(self, rawData):
        self.sensor_version = rawData[0]
        if self.sensor_version == 1:
            self.sensor_data[SENSOR_IDX_HUMIDITY] = rawData[1] / 2.0
            self.sensor_data[SENSOR_IDX_RADON_SHORT_TERM_AVG] = self.conv2radon(rawData[4])
            self.sensor_data[SENSOR_IDX_RADON_LONG_TERM_AVG] = self.conv2radon(rawData[5])
            self.sensor_data[SENSOR_IDX_TEMPERATURE] = rawData[6] / 100.0
            self.sensor_data[SENSOR_IDX_REL_ATM_PRESSURE] = rawData[7] / 50.0
            self.sensor_data[SENSOR_IDX_CO2_LVL] = rawData[8] * 1.0
            self.sensor_data[SENSOR_IDX_VOC_LVL] = rawData[9] * 1.0
        else:
            print("ERROR: Unknown sensor version.\n")
            print("GUIDE: Contact Airthings for support.\n")
            sys.exit(1)

    def conv2radon(self, radon_raw):
        radon = "N/A"  # Either invalid measurement, or not available
        if 0 <= radon_raw <= 16383:
            radon = radon_raw
        return radon

    def getValue(self, sensor_index):
        return self.sensor_data[sensor_index]

    def getUnit(self, sensor_index):
        return self.sensor_units[sensor_index]


class DataPublisher():

    def __init__(self, config):
        self.config = config
        self.client_id = config['mqtt.clientId']
        self.username = config['mqtt.username']
        self.password = config['mqtt.password']
        self.topic = config['mqtt.topic']
        self.hostname = config['mqtt.hostname']
        self.port = int(config['mqtt.port'])

    def publish(self, serial, data):
        topic = self.topic
        id = self.config.get('waveplus.' + serial + '.id')

        if id is not None:
            topic = self.topic + '/' + id
            print('Wave Plus with serial {} has id {}'.format(serial, id))

        print('Publishing data {} to topic {}'.format(data, topic))

        publish.single(
            topic,
            json.dumps(data),
            hostname=self.hostname,
            port=self.port,
            client_id=self.client_id,
            auth= {'username': self.username, 'password': self.password})


Config = getConfig()
serials = [serial.strip() for serial in Config['waveplus.serial'].split(',')]
publisher = DataPublisher(Config)

for serial in serials:
    waveplus = WavePlus(serial)

    try:
        print("Retrieving data from Wave Plus with serial: %s" % serial)

        waveplus.connect()
        sensors = waveplus.read()

        data = {
            "serial": serial,
            "humidity": sensors.getValue(SENSOR_IDX_HUMIDITY),
            "radon_short_term": sensors.getValue(SENSOR_IDX_RADON_SHORT_TERM_AVG),
            "radon_long_term": sensors.getValue(SENSOR_IDX_RADON_LONG_TERM_AVG),
            "temperature": sensors.getValue(SENSOR_IDX_TEMPERATURE),
            "pressure": sensors.getValue(SENSOR_IDX_REL_ATM_PRESSURE),
            "co2": sensors.getValue(SENSOR_IDX_CO2_LVL),
            "voc": sensors.getValue(SENSOR_IDX_VOC_LVL)
        }

        publisher.publish(serial, data)

        waveplus.disconnect()

    finally:
        waveplus.disconnect()
