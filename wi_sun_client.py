#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
'''Sample program for ECHONET-Lite.'''

import influxdb
import logging
import os
import sys
import time
from time import sleep
import serial
import yaml

logging.basicConfig(
    filename='log/wi_sun_client.log', level=logging.INFO,
    format='[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# TODO: remove such a sensitive info.
account = yaml.safe_load(open('./secret/b_route.yml'))


# TODO: revise name for more specific for my wi-sun device
class SimpleEchonetLiteClient():
    """ECHONET Lite Client"""

    RETRY_INTERVAL = 10  # sec
    CONF_LIFETIME = 24 * 60 * 60
    MAX_DURATION_SCAN = 7  # Should be < 15, but not work for 8 or large one.

    SERIAL_DEV = '/dev/ttyUSB0'
    CONFIG_FILE = './config/wi_sun_config.yml'

    EPCS = {
        '0xE0': b'\xE0',  # 積算電力量(正)
        '0xE1': b'\xE0',  # 積算電力量の単位
        '0xE3': b'\xE3',  # 積算電力量(逆)
        '0xE7': b'\xE7',  # 瞬時電力 [W]
        '0xE8': b'\xE8',   # 瞬時電流
        }

    def echonet_lite_frame(self, epc):
        """Return a set of params for frame command with given EPC."""

        return {
            'EHD': b'\x10\x81',
            'TID': b'\x00\x01',
            'SEOJ': b'\x05\xFF\x01',
            'DEOJ': b'\x02\x88\x01',
            'ESV': b'\x62',
            'OPC': b'\x01',
            'EPC': self.EPCS[epc],
            'PDC': b'\x00',
            }

    def __init__(self):
        # Define read timeout for serial dev to avoid to be freezed.
        ser_read_timeout = 10.0  # sec

        self.serial_dev = serial.Serial(
            self.SERIAL_DEV, baudrate=115200, timeout=ser_read_timeout)
        self.conf_force_update = False
        self.conf = self._get_config(self.CONFIG_FILE, self.conf_force_update)

        if not self.conf:
            scan_duration = 4
            self._auth_b_route()
            self.conf = self._auth_pana(scan_duration)
            with open(self.CONFIG_FILE, 'w') as cfpath:
                yaml.dump(self.conf, cfpath)

    def _get_config(self, conf_fpath, force_update=False):
        """Get config from existing file."""

        if os.path.exists(conf_fpath):
            age_of_file = time.time() - os.path.getmtime(conf_fpath)
            if age_of_file < self.CONF_LIFETIME and force_update is False:
                return yaml.safe_load(open(conf_fpath))
            return None
        return None

    def _auth_b_route(self):
        """Auth with B route account first for accessing the device."""

        # Send password
        pwd = "SKSETPWD C " + account['passwd'] + "\r\n"
        self.serial_dev.write(pwd.encode('utf-8'))
        logging.info('Send passwd for auth B route: "%s"' % pwd.rstrip())
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info('(Result) %s' % (
            self.serial_dev.readline().decode('utf-8').rstrip()))

        # Send B route ID
        bid = "SKSETRBID " + account['b_id'] + "\r\n"
        self.serial_dev.write(bid.encode('utf-8'))
        logging.info('Sent ID for auth B route: "%s"' % bid.rstrip())
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info('(Result) %s' % (
            self.serial_dev.readline().decode('utf-8').rstrip()))

    def _auth_pana(self, s_duration):
        """Auth for PANA connection after B route."""

        # incremented up to max val while negotiation
        scan_duration = s_duration

        scan_res = {}

        while "Channel" not in scan_res.keys():
            msg = "SKSCAN 2 FFFFFFFF " + str(scan_duration) + "\r\n"
            self.serial_dev.write(msg.encode())
            logging.info('Sent ID for auth PANA: "%s"' % msg.rstrip())

            flg_scan_end = False
            while not flg_scan_end:
                line = self.serial_dev.readline().decode('utf-8')
                logging.debug('Msg in auth PANA: %s' % line.rstrip())

                if line.startswith("EVENT 22"):  # Finished to scan.
                    flg_scan_end = True
                elif line.startswith("  "):  # Found values for access.
                    # In this case, "EVENT 20", returned values are given
                    # with two spaces ahead. Here is an example.
                    #
                    #   EVENT 20 FE80:0000:0000:0000:021D:1290:0003:8474
                    #   EPANDESC
                    #     Channel:39
                    #     Channel Page:09
                    #     Pan ID:FFFF
                    #     Addr:FFFFFFFFFFFFFFFF
                    #     LQI:A7
                    #     PairID:FFFFFFFF
                    cols = line.strip().split(':')
                    scan_res[cols[0]] = cols[1]
            scan_duration += 1

            if self.MAX_DURATION_SCAN < scan_duration and \
                    "Channel" not in scan_res.keys():
                print("Failed to authenticate PANA")
                sys.exit()

        # Convert MAC address into IPv6 local link address.
        self.serial_dev.write(
            str.encode("SKLL64 " + scan_res["Addr"] + "\r\n"))
        self.serial_dev.readline().decode(encoding='utf-8')
        scan_res['Addr'] = self.serial_dev.readline().decode(
            encoding='utf-8').strip()

        return scan_res

    def device_version(self):
        """Check device version"""

        self.serial_dev.write(b'SKVER\r\n')
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        return self.serial_dev.readline().decode('utf-8').rstrip()

    def connect(self):
        '''Negotiation to connect the device.'''

        msg = "SKSREG S2 " + self.conf['Channel']
        self.serial_dev.write(str.encode(msg + "\r\n"))
        logging.info('Conn with given channel: %s' % msg)
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info('(Result) %s' % (
            self.serial_dev.readline().decode(encoding='utf-8').rstrip()))

        msg = "SKSREG S3 " + self.conf['Pan ID']
        self.serial_dev.write(str.encode(msg + "\r\n"))
        logging.info('Set PanID: %s' % msg)
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info('(Result) %s' % (
            self.serial_dev.readline().decode(encoding='utf-8').rstrip()))

        msg = "SKJOIN " + self.conf['Addr']
        self.serial_dev.write(str.encode(msg + "\r\n"))
        logging.info('Set IPv6 addr: %s' % msg)
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info('(Result) %s' % (
            self.serial_dev.readline().decode(encoding='utf-8').rstrip()))

        # Waiting for connection.
        b_connected = False
        while not b_connected:
            line = self.serial_dev.readline().decode(
                encoding='utf-8', errors='ignore')

            if line.startswith("EVENT 24"):
                print('Error: Failed PANA connection')
                sys.exit()
            elif line.startswith("EVENT 25"):
                logging.info('Succeeded PANA connection')
                b_connected = True
        self.serial_dev.readline()

    def get_data(self, epc=None):
        """Get data from the device."""

        if epc == '0xE8':
            raw_data = self.get_raw_data(epc)
            r_phase_val = raw_data[0:4]
            t_phase_val = raw_data[4:8]
            return (int(r_phase_val, 16) / 10.0, int(t_phase_val, 16) / 10.0)
        else:
            return int(self.get_raw_data(epc), 16)

    def get_raw_data(self, epc=None):
        """Get raw hex data from the device."""

        el_frame = b''
        for eframe in self.echonet_lite_frame(epc).values():
            el_frame += eframe

        while True:
            # Send command.
            command = "SKSENDTO 1 {0} 0E1A 1 {1:04X} ".format(
                self.conf['Addr'], len(el_frame))
            logging.info('Sent cmd to get data: %s' % command.rstrip())
            self.serial_dev.write(str.encode(command) + el_frame)

            # Recv command.
            logging.info('(Echo back) %s' % self.serial_dev.readline())
            event = self.serial_dev.readline()  # Must be "EVENT 21"
            logging.info(
                '(Result) %s' % event.decode(encoding='utf-8').rstrip())
            cmd_res = self.serial_dev.readline()
            logging.info(
                '(Result) %s' % cmd_res.decode(encoding='utf-8').rstrip())

            data = self.serial_dev.readline().decode(encoding='utf-8').rstrip()
            logging.info('Res: %s' % data)

            # Check the data.
            if data.startswith('ERXUDP'):
                cols = data.strip().split(' ')
                res = cols[8]
                params = {}
                params['seoj'] = res[8:8+6]
                params['esv'] = res[20:20+2]

                # 'seoj' must be '028801' if using smart meter
                if params['seoj'] == "028801" and params['esv'] == "72":
                    if res[24:24+2] == epc[-2:]:
                        hex_power = data[-8:]
                        return hex_power

            sleep(self.RETRY_INTERVAL)

    def close_serial_dev(self):
        """Make the program close connection surely."""

        self.serial_dev.close()


class MyInflaxClient():
    """A simple influxdb client."""

    def __init__(self, host, dbname):
        # Check the dbname is existing first.
        self.client = influxdb.InfluxDBClient(host=host)
        if not {'name': dbname} in self.client.get_list_database():
            self.client.create_database(dbname)

        self.client = influxdb.InfluxDBClient(host=host, database=dbname)

    def write_points(self, data):
        self.client.write_points(data)


def main():
    """Program main"""

    retrieve_interval = 30  # sec
    timeout_each_data = 1  # sec

    try:
        influx_params = yaml.safe_load(open('./secret/influx.yml'))
        elcli = SimpleEchonetLiteClient()
        influx_cli = MyInflaxClient(influx_params['host'],
                                    influx_params['dbname'])

        # print(elcli.device_version())
        elcli.connect()

        # Target values for monitoring defined as a set of ID in Echonet and
        # measurement in influxdb.
        # NOTE: You can use any of measurement because influxdb registers data
        #       with given measurement.
        targets = {
            '0xE0': 'integ_energy',  # 積算電力量
            '0xE7': 'inst_energy',   # 瞬間電力量
            '0xE8': 'inst_current',  # 瞬間電力量
            }

        while True:
            json_obj = []
            for key in targets.keys():
                if key == '0xE0':  # Value is in kW, convert to W
                    val = int(elcli.get_data(key)) * 1000
                elif key == '0xE7':  # in W
                    val = int(elcli.get_data(key))
                elif key == '0xE8':
                    # Value is a combination of Amperes, but not interested
                    # in the second one in case of my device.
                    val = float(elcli.get_data(key)[0])

                json_obj.append({
                            'measurement': targets[key],
                            'tags': {'host': influx_params['host']},
                            'fields': {'value': val}
                        })

                sleep(timeout_each_data)

            influx_cli.write_points(json_obj)
            logging.info('Sent to influxdb: %s' % json_obj)
            sleep(retrieve_interval)

    finally:
        print("Closing serial port device ...")
        elcli.close_serial_dev()


if __name__ == '__main__':
    main()
