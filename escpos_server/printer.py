import logging
import queue
import threading
import time

import usb.core
from usb.core import USBTimeoutError

from escpos_server.signals import shutdown_handlers
from escpos_server.status import Status, TYPE_OFFLINE, TYPE_ONLINE

logger = logging.getLogger(__name__)

# Public to other modules
out_queue = queue.Queue()
in_queue = queue.Queue()
print_lock = threading.Lock()

# Internal variables
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

def get_status():
    return _status

def _poll(dev, endpoint_out, endpoint_in):
    global _status
    poll_start = time.time()

    dev.write(endpoint_out, bytes([DLE, EOT, STATUS_PAPER]), 100)
    while not (paper_status := bytes(x for x in dev.read(endpoint_in, 1024))):
        if time.time() - poll_start > POLL_INTERVAL:
            # When the printer is not ready, e.g. cover open, it will just not respond
            # on USB or network interfaces. Therefore, polling STATUS_PRINTER is also pretty
            # useless.
            logger.info(f"Printer did not respond to polling")
            _status = Status(type=TYPE_OFFLINE)
            return
        time.sleep(.001)
    logger.debug(f"Raw paper status: {paper_status!r}")

    _status = Status.from_escpos(paper_status[0])
    logger.debug(f"Status: {_status!r}")


def printer_loop_inner(usb_product):
    global _last_poll

    logging.info(f"Looking for USB device {usb_product}…")
    vendor_id, product_id = usb_product.split(":", 1)
    vendor_id = int("0x" + vendor_id, 16)
    product_id = int("0x" + product_id, 16)
    dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)

    if vendor_id == VENDOR_ID_CUSTOM:
        endpoint_out = OUT_ENDPOINT_CUSTOM
        endpoint_in = IN_ENDPOINT_CUSTOM
    else:
        endpoint_out = OUT_ENDPOINT_EPSON
        endpoint_in = IN_ENDPOINT_EPSON

    if not dev:
        raise Exception("Could not find USB printer")
    logging.info(f"Found USB device {dev.manufacturer} {dev.product} {dev.serial_number}")

    dev.reset()
    # For some reason, we may not call dev.set_configuration() because the kernel already handles the printer

    if len(dev.configurations()) > 1:
        logger.warning("USB device has more than one configuration, the first one will be picked")

    if len(dev.configurations()[0].interfaces()) > 1:
        logger.warning("USB device has more than one configuration, the first one will be picked")

    i = dev.configurations()[0].interfaces()[0].bInterfaceNumber

    # Not clear if this is necessary
    if dev.is_kernel_driver_active(i):
        dev.detach_kernel_driver(i)

    while not _shutdown_requested:
        if time.time() - _last_poll > POLL_INTERVAL and print_lock.acquire(blocking=False):
            try:
                _poll(dev, endpoint_out, endpoint_in)
            finally:
                print_lock.release()
                _last_poll = time.time()

        try:
            while True:
                data_in = out_queue.get(block=False)
                logger.debug(f"Write to printer: {data_in!r}")
                dev.write(endpoint_out, data_in)
        except queue.Empty:
            pass

        try:
            while data_out := dev.read(endpoint_in, 1024, 25):
                data_out = bytes(x for x in data_out)
                logger.debug(f"Read from printer: {data_out!r}")
                in_queue.put(data_out)
        except USBTimeoutError:
            pass

        time.sleep(.001)


def printer_loop(usb_product):
    while not _shutdown_requested:
        try:
            printer_loop_inner(usb_product)
        except:
            logger.exception("Printer loop failed, restart in 5s")
            time.sleep(5)


def start_printer_thread(usb_product):
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
