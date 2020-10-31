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
