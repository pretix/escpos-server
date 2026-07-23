import logging
import socketserver
import threading

from usb.core import USBTimeoutError

from escpos_server import printer
from escpos_server.signals import shutdown_handlers

logger = logging.getLogger(__name__)


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client = ":".join(str(a) for a in self.client_address)
        logger.info(f"New TCP connection from {client}")
        self.request.settimeout(0.001)

        with printer.printer(self.server.usb_product) as p:
            while not self.server._shutdown_requested:
                try:
                    data_from_tcp = self.request.recv(1024)
                    logger.debug(f"TCP data received [{len(data_from_tcp)}]: {data_from_tcp!r}")
                    if not data_from_tcp:
                        logger.info(f"TCP connection from {client} closed")
                        return
                except TimeoutError:
                    pass
                else:
                    if data_from_tcp:
                        p.write(data_from_tcp)

                try:
                    data_from_printer = p.read()
                    if data_from_printer:
                        logger.debug(f"TCP data to be sent [{len(data_from_printer)}]: {data_from_printer!r}")
                        self.request.sendall(data_from_printer)
                except USBTimeoutError:
                    pass


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def __init__(self, *args, **kwargs):
        self.usb_product = kwargs.pop("usb_product")
        super().__init__(*args, **kwargs)
        self._shutdown_requested = False

    def handle_shutdown(self):
        self._shutdown_requested = True
        self.server_close()
        self.shutdown()


def tcp_server(host, port, usb_product):
    with ThreadingServer((host, port), TCPHandler, usb_product=usb_product) as server:
        shutdown_handlers.append(server.handle_shutdown)
        server.serve_forever()


def start_tcp_listen_thread(host, port, usb_product):
    t = threading.Thread(
        target=tcp_server,
        args=(host, port, usb_product),
        name="tcp-server",
    )
    t.start()
