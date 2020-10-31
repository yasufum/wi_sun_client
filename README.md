## Setup

Install requied packages.

```sh
$ sudo apt install python3 python3-pip
$ pip3 install -r requirements.txt
```

## Run

You should update `secret/b_route.yml` with your B route ID and password
before running this tool.

Now, you can run the script.

```sh
$ python3 wi_sun_clinet.py
```

NOTE: If you cannot access your device because for permission denied, add
your account into `dialout`group.

```sh
$ gpasswd -a USERNAME dialout
```

## Supported Data (in Japanese)

[ECHONET機器オブジェクト詳細規定](https://echonet.jp/wp/wp-content/uploads/pdf/General/Standard/Release/Release_H_jp/Appendix_H.pdf)
[1]の低圧スマート電力量メータクラス規定に記載されたデータ種別のうち、以下をサポート。

* 積算電力量計測値(正方向計測値)
  * 単位: kWh

* 瞬時電力計測値
  * 単位: W

* 瞬時電流計測値(T相, R相の2種類)
  * 単位: 0.1A

## References

[1] [ECHONET機器オブジェクト詳細規定](https://echonet.jp/wp/wp-content/uploads/pdf/General/Standard/Release/Release_H_jp/Appendix_H.pdf), p.312-319
