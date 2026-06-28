# escpos-server

Local server to expose and monitor a USB ESC/POS printer via network.

The server will open two ports, one raw TCP port that behaves like the printer itself, and one HTTP port with a web API.

## Usage

```
usage: escpos-server [-h] --usb-product USB_PRODUCT 
                     [--listen-host LISTEN_HOST] [--listen-port LISTEN_PORT]
                     [--web-host WEB_HOST] [--web-port WEB_PORT]
                     [--verbose]

ESC/POS server

options:
  -h, --help            show this help message and exit
  --usb-product USB_PRODUCT
  --listen-host LISTEN_HOST
  --listen-port LISTEN_PORT
  --web-host WEB_HOST
  --web-port WEB_PORT
  --verbose
```

Example:

```
$ escpos-server --usb-product 04b8:0202
```

## Web API

```
$ curl http://127.0.0.1:8101/
{"status": {"type": "online", "paper_end": false, "paper_near_end": false}}
```