from enum import Enum


CURRENT_TIME_RANGE_MINUTES = 20 # in minutes, indicates how long a measurement is considered for current data

class Dimension():
    PM0_1 = 1
    PM1_0 = 2
    PM2_5 = 3
    PM4_0 = 4
    PM10_0 = 5
    HUMIDITY = 6
    TEMPERATURE = 7
    VOC_INDEX = 8
    NOX_INDEX = 9
    PRESSURE = 10
    CO2 = 11
    O3 = 12
    AQI = 13
    GAS_RESISTANCE = 14
    TVOC = 15
    NO2 = 16
    SGP40_RAW_GAS = 17
    SGP40_ADJUSTED_GAS = 18
    ADJUSTED_TEMP_CUBE = 19
    UVS = 20
    LIGHT = 21
    ALTITUDE = 22
    UVI = 23
    LUX = 24
    ACCELERATION_X = 25
    ACCELERATION_Y = 26
    ACCELERATION_Z = 27
    GYRO_X = 28
    GYRO_Y = 29
    GYRO_Z = 30
    THERMAL_ARRAY = 31
    VISIBLE = 32
    INFRARED = 33
    FULL_SPECTRUM = 34
    RAW_LUMINOSITY = 35

    # Dictionary für die Einheiten der Dimensionen
    _units = {
        PM0_1: "µg/m³",
        PM1_0: "µg/m³",
        PM2_5: "µg/m³",
        PM4_0: "µg/m³",
        PM10_0: "µg/m³",
        HUMIDITY: "%",
        TEMPERATURE: "°C",
        VOC_INDEX: "Index",
        NOX_INDEX: "Index",
        PRESSURE: "hPa",
        CO2: "ppm",
        O3: "ppb",
        AQI: "Index",
        GAS_RESISTANCE: "Ω",
        TVOC: "ppb",
        NO2: "ppb",
        SGP40_RAW_GAS: "Ω",
        SGP40_ADJUSTED_GAS: "Ω",
        ADJUSTED_TEMP_CUBE: "°C",
        ACCELERATION_X: "m/s²",
        ACCELERATION_Y: "m/s²",
        ACCELERATION_Z: "m/s²",
        GYRO_X: "radians/s",
        GYRO_Y: "radians/s",
        GYRO_Z: "radians/s",
        UVI: "UV Index",
        LUX: "lx",
    }

    _names = {
        PM0_1: "PM0.1",
        PM1_0: "PM1.0",
        PM2_5: "PM2.5",
        PM4_0: "PM4.0",
        PM10_0: "PM10.0",
        HUMIDITY: "Humidity",
        TEMPERATURE: "Temperature",
        VOC_INDEX: "VOC Index",
        NOX_INDEX: "NOx Index",
        PRESSURE: "Pressure",
        CO2: "CO2",
        O3: "Ozone (O3)",
        AQI: "Air Quality Index (AQI)",
        GAS_RESISTANCE: "Gas Resistance",
        TVOC: "Total VOC",
        NO2: "Nitrogen Dioxide (NO2)",
        SGP40_RAW_GAS: "SGP40 Raw Gas",
        SGP40_ADJUSTED_GAS: "SGP40 Adjusted Gas",
        ADJUSTED_TEMP_CUBE: "Adjusted Temperature Air Cube",
        UVS: "UVS",
        LIGHT: "Light",
        ALTITUDE: "Altitude",
        UVI: "UV Index",
        LUX: "Lux",
        ACCELERATION_X: "acceleration X",
        ACCELERATION_Y: "acceleration Y",
        ACCELERATION_Z: "acceleration Z",
        GYRO_X: "gyro X",
        GYRO_Y: "gyro Y",
        GYRO_Z: "gyro Z",
        THERMAL_ARRAY: "Thermal Image",
    }

    _sensor_community_names = {
        PM0_1: "P01",
        PM1_0: "P1",
        PM2_5: "P2",
        PM4_0: "P4",
        PM10_0: "P10",
        HUMIDITY: "humidity",
        TEMPERATURE: "temperature",
        PRESSURE: "pressure",
        CO2: "co2_ppm",
        O3: "ozone_ppb",
        TVOC: "tvoc",
        NO2: "no2_ppb",
    }

    _sensor_community_names_import = {
        PM0_1: "P01",
        PM1_0: "P10",
        PM2_5: "P2",
        PM4_0: "P4",
        PM10_0: "P1",
        HUMIDITY: "humidity",
        TEMPERATURE: "temperature",
        PRESSURE: "pressure",
        CO2: "co2_ppm",
        O3: "ozone_ppb",
        TVOC: "tvoc",
        NO2: "no2_ppb",
    }

    # outlider factor
    ALPHA = 0.1

    _filter_thresholds = {
        PM2_5: (0, 999)
    }

    @classmethod
    def get_filter_threshold(cls, dim: int) -> tuple[float, float]:
        return cls._filter_thresholds.get(dim, (-float('inf'), float('inf')))

    @classmethod
    def get_unit(cls, dimension_id: int) -> str:
        """
        Gibt die Einheit der angegebenen Dimension zurück.
        :param dimension_id: Die ID der Dimension
        :return: Die zugehörige Einheit oder 'Unknown', wenn keine Einheit vorhanden ist
        """
        return cls._units.get(dimension_id, "Unknown")

    @classmethod
    def get_name(cls, dimension_id: int) -> str:
        """
        Gibt den Namen der angegebenen Dimension zurück.
        :param dimension_id: Die ID der Dimension
        :return: Der zugehörige Name oder 'Unknown', wenn kein Name vorhanden ist
        """
        return cls._names.get(dimension_id, "Unknown")

    @classmethod
    def get_dimension_from_sensor_community_name(cls, sensor_community_name: str):
        return {v:k for k, v in cls._sensor_community_names.items()}.get(sensor_community_name, None)
    
    @classmethod
    def get_dimension_from_sensor_community_name_import(cls, sensor_community_name: str):
        return {v:k for k, v in cls._sensor_community_names_import.items()}.get(sensor_community_name, None)


class SensorModel():
    SEN5X = 1
    BMP280 = 2
    BME280 = 3
    BME680 = 4
    SCD4X = 5
    AHT20 = 6
    SHT30 = 7
    SHT31 = 8
    AGS02MA = 9
    SHT4X = 10
    SGP40 = 11
    DHT22 = 12
    SDS011 = 13
    SHT35 = 14
    SPS30 = 15
    PMS5003 = 16
    PMS7003 = 17
    VIRTUAL_SENSOR = 18
    LTR390 = 19
    BMP388 = 20
    BMP390 = 21
    LSM6DS = 22
    SEN66 = 23
    MLX90640 = 24
    TSL2591 = 25
    SEN63C = 26
    SEN62 = 27
    BMP581 = 28
    SHTC3 = 29

    _names = {
        SEN5X: "SEN5X",
        BMP280: "BMP280",
        BME280: "BME280",
        BME680: "BME680",
        SCD4X: "SCD4X",
        AHT20: "AHT20",
        SHT30: "SHT30",
        SHT31: "SHT31",
        AGS02MA: "AGS02MA",
        SHT4X: "SHT4X",
        SGP40: "SGP40",
        DHT22: "DHT22",
        SDS011: "SDS011",
        SHT35: "SHT35",
        SPS30: "SPS30",
        PMS5003: "PMS5003",
        PMS7003: "PMS7003",
        VIRTUAL_SENSOR: "VIRTUAL_SENSOR",
        LTR390: "LTR390",
        BMP388: "BMP388",
        BMP390: "BMP390",
        LSM6DS: "lsm6ds",
        SEN66: "SEN66",
        MLX90640: "MLX90640",
        TSL2591: "TSL_2591",
        SEN63C: "SEN63C",
        SEN62: "SEN62",
        BMP581: "BMP581",
        SHTC3: "SHTC3",
    }

    _manufacturer = {
        SEN5X: "Sensirion",
        BMP280: "Bosch Sensortec",
        BME280: "Bosch Sensortec",
        BME680: "Bosch Sensortec",
        SCD4X: "Sensirion",
        AHT20: "ASAIR",
        SHT30: "Sensirion",
        SHT31: "Sensirion",
        AGS02MA: "ASAIR",
        SHT4X: "Sensirion",
        SGP40: "Sensirion",
        DHT22: "ASAIR",
        SDS011: "Nova Fitness",
        SHT35: "Sensirion",
        SPS30: "Sensirion",
        PMS5003: "Plantower",
        PMS7003: "Plantower",
        VIRTUAL_SENSOR: "Luftdaten.at",
        SEN66: "Sensirion",
        MLX90640: "Mouser Electronics",
        TSL2591: "ams OSRAM",
        SEN63C: "Sensirion",
        SEN62: "Sensirion",
        BMP581: "Bosch Sensortec",
        SHTC3: "Sensirion",
    }

    @classmethod
    def get_sensor_name(cls, sensor_model):
        return cls._names.get(sensor_model, "Unknown Sensor")


class LdProduct():
    AIR_AROUND = 1
    AIR_CUBE = 2
    AIR_STATION = 3
    AIR_BADGE = 4
    AIR_BIKE = 5


class Source():
    LD = 1
    LDTTN = 2
    SC = 3

    _names = {
        LD: "Luftdaten.at",
        LDTTN: "Luftdaten.at TTN LoRaWAN",
        SC: "sensor.community"
    }

    @classmethod
    def get_name(cls, source_id: int) -> str:
        """
        Gibt den Namen der angegebenen Source zurück.
        :param source_id: Die ID der Source
        :return: Der zugehörige Name oder 'Unknown', wenn kein Name vorhanden ist
        """
        return cls._names.get(source_id, "Unknown")


class Precision(str, Enum):
    MAX = "all"
    HOURLY = "hour"
    DAYLY = "day"
    WEEKLY = "week"
    MONTHLY = "month"
    YEARYLY = "year"

    __to_time_frame = {
        MAX: "milliseconds",
        HOURLY: "hour",
        DAYLY: "day",
        WEEKLY: "week",
        MONTHLY: "month",
        YEARYLY: "year",
    }

    @classmethod
    def get_time_frame(cls, precision: str):
        return cls.__to_time_frame[precision]


class OutputFormat(str, Enum):
    JSON = "json"
    CSV = "csv"

class Order(str, Enum):
    MIN="min"
    MAX="max"
