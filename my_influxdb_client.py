#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""My simple influxdb client"""

import influxdb

class MyInfluxdbClient():
    """A simple influxdb client."""

    def __init__(self, host, dbname):
        # Check the dbname is existing first.
        self.client = influxdb.InfluxDBClient(host=host)
        if not {'name': dbname} in self.client.get_list_database():
            self.client.create_database(dbname)

        self.client = influxdb.InfluxDBClient(host=host, database=dbname)

    def write_points(self, data):
        self.client.write_points(data)
