import logging
import queue
import socketserver
import threading

from escpos_server import printer
from escpos_server.signals import shutdown_handlers

logger = logging.getLogger(__name__)


class TCPHandler(socketserver.BaseRequestHandler):
    def _clear_queues(self):
        try:
            while printer.out_queue.get_nowait():
                pass
        except queue.Empty:
            pass
        try:
            while printer.in_queue.get_nowait():
                pass
        except queue.Empty:
            pass

    def handle(self):
        client = ":".join(str(a) for a in self.client_address)
        logger.info(f"New TCP connection from {client}")
        self.request.settimeout(0.001)

        while not printer.print_lock.acquire(blocking=True, timeout=1):
            logger.debug(f"Waiting for lock to be released by other thread…")
        self._clear_queues()

        while not self.server._shutdown_requested:
            try:
                while out_data := printer.in_queue.get_nowait():
                    logger.debug(f"Sending data [{len(out_data)}]: {out_data!r}")
                    self.request.sendall(out_data)
            except queue.Empty:
                pass

            try:
                data_in = self.request.recv(1024)
            except TimeoutError:
                continue
            if not data_in:
                logger.info(f"TCP connection from {client} closed")
                printer.print_lock.release()
                return

            logger.debug(f"Received data [{len(data_in)}]: {data_in!r}")
            printer.out_queue.put(data_in)


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shutdown_requested = False

    def handle_shutdown(self):
        self._shutdown_requested = True
        self.server_close()
        self.shutdown()


def tcp_server(host, port):
    with ThreadingServer((host, port), TCPHandler) as server:
        shutdown_handlers.append(server.handle_shutdown)
        server.serve_forever()


def start_tcp_listen_thread(host, port):
    t = threading.Thread(
        target=tcp_server,
        args=(host, port),
        name="tcp-server",
    )
    t.start()
