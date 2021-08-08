# Airthings Wave Plus MQTT Data Publisher

This is a slightly altered version of [Airthings/waveplus-reader](https://github.com/Airthings/waveplus-reader) which can be used to publish data from [Airthings Wave Plus](https://www.airthings.com/en/wave-plus) indoor air quality monitor to an MQTT broker.

Personally I use this with various tags to publish data to [Home Assistant](https://www.home-assistant.io).

# Requirements

See [Airthings/waveplus-reader](https://github.com/Airthings/waveplus-reader) for base requirements. Python module `tableprint` is not needed by this app anymore. In addition, you need to install [Paho MQTT Python module](https://www.eclipse.org/paho/index.php?page=clients/python/index.php).

```bash
$ pip install paho-mqtt
```

# Sample configuration

Include `config.properties` to the same directory with the app. Here's a sample config file:

```
waveplus.serial=1234567890

mqtt.hostname=192.168.0.1
mqtt.port=1883
mqtt.username=mqtt-user
mqtt.password=secret
mqtt.topic=/home/airthings/waveplus
mqtt.clientId=airthings-waveplus-mqtt-data-publisher
```

# Running

You can run the app as follows

```bash
$ python waveplus_mqtt_data_publisher.py
```

An example message sent to the MQTT broker

```json
{
  "radon_long_term": 33,
  "temperature": 25.23,
  "voc": 142.0,
  "radon_short_term": 55,
  "humidity": 50.0,
  "pressure": 1005.06,
  "co2": 656.0
}
```
