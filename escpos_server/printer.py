import contextlib
import logging
import threading
import time

import usb.core
import usb.util

from escpos_server.signals import shutdown_handlers
from escpos_server.status import Status, TYPE_OFFLINE

logger = logging.getLogger(__name__)

# Internal variables
_print_lock = threading.Lock()
_shutdown_requested = False
_last_poll = 0
_status = Status()

# Constants
POLL_INTERVAL = 1
VENDOR_ID_CUSTOM = 0x0dd4
# USB endpoints Let's hope these are constant across all ESC/POS printers
OUT_ENDPOINT_EPSON = 0x01
OUT_ENDPOINT_CUSTOM = 0x02
IN_ENDPOINT_EPSON = 0x82
IN_ENDPOINT_CUSTOM = 0x81
# ESC/POS parts
DLE = 0x10
EOT = 0x04
STATUS_PRINTER = 0x01
STATUS_OFFLINE = 0x02
STATUS_ERROR_CAUSE = 0x03
STATUS_PAPER = 0x04


class Printer:
    def __init__(self, usb_product):
        self.usb_product = usb_product
        self._dev = None
        self._endpoint_out = OUT_ENDPOINT_EPSON
        self._endpoint_in = IN_ENDPOINT_EPSON

    def open(self):
        logging.debug(f"Looking for USB device {self.usb_product}…")
        vendor_id, product_id = self.usb_product.split(":", 1)
        vendor_id = int("0x" + vendor_id, 16)
        product_id = int("0x" + product_id, 16)
        self._dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)

        if vendor_id == VENDOR_ID_CUSTOM:
            self._endpoint_out = OUT_ENDPOINT_CUSTOM
            self._endpoint_in = IN_ENDPOINT_CUSTOM

        if not self._dev:
            raise Exception("Could not find USB printer")

        logging.debug(f"Found USB device {self._dev.manufacturer} {self._dev.product} {self._dev.serial_number}")
        self._dev.reset()
        # For some reason, we may not call dev.set_configuration() because the kernel already handles the printer

        if len(self._dev.configurations()) > 1:
            logger.warning("USB device has more than one configuration, the first one will be picked")

        if len(self._dev.configurations()[0].interfaces()) > 1:
            logger.warning("USB device has more than one configuration, the first one will be picked")

        i = self._dev.configurations()[0].interfaces()[0].bInterfaceNumber

        # Not clear if this is necessary
        if self._dev.is_kernel_driver_active(i):
            self._dev.detach_kernel_driver(i)

    def write(self, data: bytes):
        logger.debug(f"Write to printer [{len(data)}]: {data!r}")
        self._dev.write(self._endpoint_out, data)

    def read(self, size=1024, timeout=25):
        data = self._dev.read(self._endpoint_in, 1024, 25)
        if data:
            data = bytes(data)
            logger.debug(f"Read from printer [{len(data)}]: {data!r}")
        return data

    def close(self):
        usb.util.dispose_resources(self._dev)

    def poll_status(self):
        poll_start = time.time()

        logger.debug(f"Sending status poll")
        self.write(bytes([DLE, EOT, STATUS_PAPER]))
        while not (paper_status := bytes(x for x in self.read())):
            if time.time() - poll_start > POLL_INTERVAL:
                # When the printer is not ready, e.g. cover open, it will just not respond
                # on USB or network interfaces. Therefore, polling STATUS_PRINTER is also pretty
                # useless.
                logger.info(f"Printer did not respond to polling")
                return Status(type=TYPE_OFFLINE)
            time.sleep(.001)

        status = Status.from_escpos(paper_status[0])
        logger.debug(f"Parsed status: {status!r}")
        return status


@contextlib.contextmanager
def printer(usb_product):
    with _print_lock:
        p = Printer(usb_product)
        try:
            p.open()
            yield p
        finally:
            p.close()


def get_status():
    return _status


def printer_loop(usb_product):
    global _status, _last_poll

    _last_poll = 0
    logging.info(f"Printer loop is running")
    while not _shutdown_requested:
        if time.time() - _last_poll > POLL_INTERVAL:
            with printer(usb_product) as p:
                _status = p.poll_status()
                _last_poll = time.time()


def start_printer_thread(usb_product):
    logging.info(f"USB device is set to {usb_product}")
    t = threading.Thread(
        target=printer_loop,
        args=(usb_product,),
        name="printer-loop",
    )

    def shutdown():
        global _shutdown_requested

        _shutdown_requested = True

    shutdown_handlers.append(shutdown)
    t.start()
