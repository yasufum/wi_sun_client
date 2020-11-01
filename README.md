## Setup

Install requied packages. This tool uses InfluxDB as a data store.

```sh
$ sudo apt install python3 python3-pip \
  influxdb
$ pip3 install -r requirements.txt
```

I recommend to use grafana as a monitor of stored data. You can install grafana
by following official
[instruction](https://grafana.com/docs/grafana/latest/installation/).
OSS release is enough for us to use this tool. No need to install
Enterprise edition.

For ubuntu, grafana is not included in the defualt source list. So, you need to
add the entry by yourself before running `apt-get`.

```sh
sudo apt-get install -y apt-transport-https
sudo apt-get install -y software-properties-common wget
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -

echo "deb https://packages.grafana.com/oss/deb beta main" | sudo tee -a /etc/apt/sources.list.d/grafana.list
```

Now you are ready to install.

```sh
sudo apt-get update
sudo apt-get install grafana
```

InfluxDB client is not mandatry, but useful for managing the DB.

```sh
$ sudo apt install influxdb-client
```


## Run

You should update two config files before running this tool. Both files include
some sensitive info, such as user accout or so. You have to exclude these
information from your git repository.

* `secret/b_route.yml`: Your B route ID and password.
* `secret/influx.yml`: Name of database, host info and user account.

After setup configs, you can run the script.

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
[1]の低圧スマート電力量メータクラス規定に記載されたデータ種別のうち、以下を
サポートしています。なおいくつかのデータは便宜上値の単位を変更しています。
例えば積算電力量はデバイスからkWhとして取得されますが、
grafanaでは表示する場合はSI接頭辞を付けてしまい`1.6k[kWh]`のようになります。
このようなケースを避けるため、デバイスからの取得値はkWhではなくWhとして
grafanaでは`1.6M[Wh]`となるようにしています。

* 積算電力量計測値(正方向計測値)
  * 単位: Wh (デバイスから[kWh]で取得したものを[Wh]へ変換)

* 瞬時電力計測値
  * 単位: W

* 瞬時電流計測値(T相, R相の2種類のうちT相のみ)
  * 単位: A (デバイスから0.1[A]として取得したものを[A]へ変換)


## References

[1] [ECHONET機器オブジェクト詳細規定](https://echonet.jp/wp/wp-content/uploads/pdf/General/Standard/Release/Release_H_jp/Appendix_H.pdf), p.312-319
