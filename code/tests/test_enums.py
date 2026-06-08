import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enums import SensorModel, Dimension


class TestSensorModel:
    def test_existing_sensor_names_unchanged(self):
        assert SensorModel.get_sensor_name(SensorModel.SDS011) == "SDS011"
        assert SensorModel.get_sensor_name(SensorModel.PMS7003) == "PMS7003"

    def test_new_firmware_sensor_names(self):
        assert SensorModel.get_sensor_name(SensorModel.VIRTUAL_SENSOR) == "VIRTUAL_SENSOR"
        assert SensorModel.get_sensor_name(SensorModel.SEN66) == "SEN66"
        assert SensorModel.get_sensor_name(SensorModel.LSM6DS) == "lsm6ds"
        assert SensorModel.get_sensor_name(SensorModel.TSL2591) == "TSL_2591"
        assert SensorModel.get_sensor_name(SensorModel.SHTC3) == "SHTC3"

    def test_unknown_sensor_returns_fallback(self):
        assert SensorModel.get_sensor_name(999) == "Unknown Sensor"


class TestDimension:
    def test_existing_dimension_labels_unchanged(self):
        assert Dimension.get_name(Dimension.PM2_5) == "PM2.5"
        assert Dimension.get_unit(Dimension.PM2_5) == "µg/m³"

    def test_new_firmware_dimension_labels(self):
        assert Dimension.get_name(Dimension.ADJUSTED_TEMP_CUBE) == "Adjusted Temperature Air Cube"
        assert Dimension.get_unit(Dimension.ADJUSTED_TEMP_CUBE) == "°C"
        assert Dimension.get_name(Dimension.UVI) == "UV Index"
        assert Dimension.get_unit(Dimension.UVI) == "UV Index"
        assert Dimension.get_name(Dimension.LUX) == "Lux"
        assert Dimension.get_unit(Dimension.LUX) == "lx"
        assert Dimension.get_name(Dimension.THERMAL_ARRAY) == "Thermal Image"
        assert Dimension.get_unit(Dimension.ACCELERATION_X) == "m/s²"
        assert Dimension.get_name(Dimension.GYRO_Z) == "gyro Z"

    def test_dimensions_without_firmware_metadata_return_unknown(self):
        for dim_id in (
            Dimension.VISIBLE,
            Dimension.INFRARED,
            Dimension.FULL_SPECTRUM,
            Dimension.RAW_LUMINOSITY,
        ):
            assert Dimension.get_name(dim_id) == "Unknown"
            assert Dimension.get_unit(dim_id) == "Unknown"

    def test_dimensions_with_name_but_no_unit_return_unknown_unit(self):
        assert Dimension.get_name(Dimension.UVS) == "UVS"
        assert Dimension.get_unit(Dimension.UVS) == "Unknown"
