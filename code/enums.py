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
    }

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
        SGP40: "SGP40"
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