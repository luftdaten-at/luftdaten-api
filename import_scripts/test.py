def import_sensor_community_archive():
    """
    https://archive.sensor.community/csv_per_month 
    month, sonsor_type, csv

    run every month to gather new data

    only one time download all data

    csv format:
    sensor_id;sensor_type;location;lat;lon;timestamp;dim1,...,dimN

    transform csv to this format:
    {
        "station": {
            "time": "2024-04-29T08:25:20.766Z",
            "device": "00112233AABB",
            "firmware": "1.2",
            "location": {
                "lat": 48.20194899118805,
                "lon": 16.337324948208195,
                "height": 5.3
            }
        },
        "sensors": {
            "1": { "type": 1, "data": { "2": 5.0, "3": 6.0, "5": 7.0, "6": 0.67, "7": 20.0, "8": 100 }},
            "2": { "type": 6, "data": { "6": 0.72, "7": 20.1 }}
        }
    }

    TODO: enums
    1. Add dimension names of SensorCommunity to enums
    2. Add SensorTypes to enums
    """
    pass