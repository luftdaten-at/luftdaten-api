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

    _model_names = {
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
        return cls._model_names.get(sensor_model, "Unknown Sensor")
    
class LdProduct():
    AIR_AROUND = 1
    AIR_CUBE = 2
    AIR_STATION = 3
    AIR_BADGE = 4
    AIR_BIKE = 5