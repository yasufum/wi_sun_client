#!/usr/bin/env python3
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


class MyPowerMeter():
    """ECHONET Lite Client"""

    MAX_DURATION_SCAN = 7  # Should be < 15, but not work for 8 or large one.
    DATA_INTERVAL = 10  # sec
    CONF_LIFETIME = 24 * 60 * 60

    SERIAL_DEV = '/dev/ttyUSB0'
    CONFIG_FILE = './config/wi_sun_config.yml'

    EPC = 'E8'
    epcs = {
        'E0': b'\xE0',  # 積算電力量(正)
        'E3': b'\xE3',  # 積算電力量(逆)
        'E7': b'\xE7',  # 瞬時電力
        'E8': b'\xE8',   # 瞬時電流
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
            'EPC': self.epcs[epc],
            'PDC': b'\x00',
            }

    def __init__(self):
        # TODO: add desc for the value '115200'.
        self.serial_dev = serial.Serial(self.SERIAL_DEV, 115200)
        self.conf = self._get_config(self.CONFIG_FILE)

        if not self.conf:
            scan_duration = 4
            self._auth_b_route()
            self.conf = self._auth_pana(scan_duration)
            with open(self.CONFIG_FILE, 'w') as cfpath:
                yaml.dump(self.conf, cfpath)

    def _get_config(self, conf_fpath):
        """Get config from existing file."""

        if os.path.exists(conf_fpath):
            if time.time() - os.path.getmtime(conf_fpath) > self.CONF_LIFETIME:
                return yaml.safe_load(open(conf_fpath))
            return None
        return None

    def _auth_b_route(self):
        """Auth with B route account first for accessing the device."""

        pwd = "SKSETPWD C " + account['passwd'] + "\r\n"
        self.serial_dev.write(pwd.encode('utf-8'))
        logging.info('(Echo back) %s' % (
            self.serial_dev.readline().decode('utf-8').rstrip()))
        logging.info('Passwd: %s' % (
            self.serial_dev.readline().decode('utf-8').rstrip()))

        # Bルート認証ID設定
        bid = "SKSETRBID " + account['b_id'] + "\r\n"
        self.serial_dev.write(bid.encode('utf-8'))
        logging.info('(Echo back) %s' % (
            self.serial_dev.readline().decode('utf-8').rstrip()))
        logging.info('BID: %s' % (
            self.serial_dev.readline().decode('utf-8').rstrip()))

    def _auth_pana(self, s_duration):
        """Auth for PANA connection next."""

        scan_duration = s_duration
        scan_res = {}

        while "Channel" not in scan_res.keys():
            # アクティブスキャン（IE あり）を行う
            # 時間かかります。10秒ぐらい？
            msg = "SKSCAN 2 FFFFFFFF " + str(scan_duration) + "\r\n"
            self.serial_dev.write(msg.encode())

            # スキャン1回について、スキャン終了までのループ
            scan_end = False
            while not scan_end:
                line = self.serial_dev.readline().decode('utf-8')
                logging.info(line.rstrip())

                if line.startswith("EVENT 22"):
                    # スキャン終わったよ（見つかったかどうかは関係なく）
                    scan_end = True
                elif line.startswith("  "):
                    # スキャンして見つかったらスペース2個あけてデータがやってくる
                    # 例
                    #  Channel:39
                    #  Channel Page:09
                    #  Pan ID:FFFF
                    #  Addr:FFFFFFFFFFFFFFFF
                    #  LQI:A7
                    #  PairID:FFFFFFFF
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
        logging.info('(Echo back) %s' % (
            self.serial_dev.readline().decode('utf-8').rstrip()))
        return self.serial_dev.readline().decode('utf-8').rstrip()

    def connect(self):
        '''Negotiation to connect the device.'''

        self.serial_dev.write(
            str.encode("SKSREG S2 " + self.conf['Channel'] + "\r\n"))
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info(
            self.serial_dev.readline().decode(encoding='utf-8').rstrip())

        # PanID設定
        self.serial_dev.write(
            str.encode("SKSREG S3 " + self.conf['Pan ID'] + "\r\n"))
        logging.info('PanID設定')
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info(
            self.serial_dev.readline().decode(encoding='utf-8').rstrip())

        # PANA 接続シーケンス
        self.serial_dev.write(
            str.encode("SKJOIN " + self.conf['Addr'] + "\r\n"))
        logging.info('PANA接続シーケンス')
        logging.info('(Echo back) %s' % self.serial_dev.readline())
        logging.info(
            self.serial_dev.readline().decode(encoding='utf-8').rstrip())

        # PANA 接続完了待ち
        b_connected = False
        while not b_connected:
            line = self.serial_dev.readline().decode(
                encoding='utf-8', errors='ignore')

            if line.startswith("EVENT 24"):
                print("Error: Failed to connection PANA")
                sys.exit()
            elif line.startswith("EVENT 25"):
                logging.info('Succeeded to connection PANA')
                b_connected = True
        self.serial_dev.readline()

    def get_data(self):
        """Get data from the device."""

        el_frame = b''
        for eframe in self.echonet_lite_frame(self.EPC).values():
            el_frame += eframe

        while True:
            # コマンド送信
            command = "SKSENDTO 1 {0} 0E1A 1 {1:04X} ".format(
                self.conf['Addr'], len(el_frame))
            logging.info('Command to get data: %s' % command.rstrip())
            self.serial_dev.write(str.encode(command) + el_frame)

            # コマンド受信
            eb = self.serial_dev.readline()  # エコーバック
            logging.info('(Echo back) %s' % eb)
            event = self.serial_dev.readline()  # EVENT 21
            cmd_res = self.serial_dev.readline()  # 成功ならOKを返す
            logging.info('EVENT: %s, CMD_RES: %s' % (event, cmd_res))

            # 返信データ取得
            # data = self.serial_dev.readline().decode(
            #         encoding='utf-8', errors='ignore')
            data = self.serial_dev.readline().decode(encoding='utf-8').rstrip()
            logging.info('Res data: %s' % data)
            # data = str(data).replace("b'", '').replace("\\r\\n'", '').split()
            # print(data[0])

            # データチェック
            if data.startswith('ERXUDP'):
                cols = data.strip().split(' ')
                res = cols[8]
                params = {}
                params['seoj'] = res[8:8+6]
                params['esv'] = res[20:20+2]
                # スマートメーター(028801)なら
                if params['seoj'] == "028801" and params['esv'] == "72":
                    if res[24:24+2] == self.EPC:
                        hex_power = data[-8:]
                        int_power = int(hex_power, 16)
                        print("EPC: {0}, VALUE: {1}".format(
                            self.EPC, int_power))

            sleep(self.DATA_INTERVAL)

    def close_serial_dev(self):
        """Make the program close connection surely."""

        self.serial_dev.close()


def main():
    """Program main"""

    try:
        my_pow = MyPowerMeter()
        # print(my_pow.device_version())
        my_pow.connect()
        my_pow.get_data()

    finally:
        print("Closing serial port device ...")
        my_pow.close_serial_dev()


if __name__ == '__main__':
    main()
