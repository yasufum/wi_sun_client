#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
'''Sample program for ECHONET-Lite.'''

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

    MAX_DURATION_SCAN = 7  # Should be < 15, but not work for 8 or large one.
    DATA_INTERVAL = 10  # sec
    CONF_LIFETIME = 24 * 60 * 60

    SERIAL_DEV = '/dev/ttyUSB0'
    CONFIG_FILE = './config/wi_sun_config.yml'

    EPCS = {
        'E0': b'\xE0',  # 積算電力量(正) [kWh]
        'E3': b'\xE3',  # 積算電力量(逆) [kWh]
        'E7': b'\xE7',  # 瞬時電力 [W]
        'E8': b'\xE8',   # 瞬時電流 [A]
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
        # TODO: add desc for the value '115200'.
        self.serial_dev = serial.Serial(self.SERIAL_DEV, 115200)
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

        pwd = "SKSETPWD C " + account['passwd'] + "\r\n"
        self.serial_dev.write(pwd.encode('utf-8'))
        logging.info('Send passwd for auth B route: "%s"' % pwd.rstrip())
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info('(Result) %s' % (
            self.serial_dev.readline().decode('utf-8').rstrip()))

        # Bルート認証ID設定
        bid = "SKSETRBID " + account['b_id'] + "\r\n"
        self.serial_dev.write(bid.encode('utf-8'))
        logging.info('Sent ID for auth B route: "%s"' % bid.rstrip())
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info('(Result) %s' % (
            self.serial_dev.readline().decode('utf-8').rstrip()))

    def _auth_pana(self, s_duration):
        """Auth for PANA connection after B route."""

        scan_duration = s_duration  # it's incremented up to max val
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

        # MACアドレスをIPV6リンクローカルアドレスに変換
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
                    if res[24:24+2] == epc:
                        hex_power = data[-8:]
                        int_power = int(hex_power, 16)

                        # TODO: make it to return value, not printing
                        print("EPC: {0}, VALUE: {1}".format(
                            epc, int_power))

            sleep(self.DATA_INTERVAL)

    def close_serial_dev(self):
        """Make the program close connection surely."""

        self.serial_dev.close()


def main():
    """Program main"""

    try:
        elcli = SimpleEchonetLiteClient()
        # print(elcli.device_version())
        elcli.connect()
        elcli.get_data('E7')

    finally:
        print("Closing serial port device ...")
        elcli.close_serial_dev()


if __name__ == '__main__':
    main()
