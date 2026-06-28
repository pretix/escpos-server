import argparse
import logging

from escpos_server.printer import start_printer_thread
from escpos_server.server import start_tcp_listen_thread
from escpos_server.signals import setup_signals


def main():
    parser = argparse.ArgumentParser(
        prog='escpos-server',
        description='ESC/POS server',
    )
    #parser.add_argument("filename")
    parser.add_argument("--usb-product", required=True)
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=9101)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
    )

    setup_signals()
    start_printer_thread(args.usb_product)
    start_tcp_listen_thread(args.listen_host, args.listen_port)
