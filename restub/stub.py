"""
The Service can be run as a context manager, a decorator of function or as a
class instance:
Examples:
    # Run as the a context manager
    with Service(routes=['GET', r'/$']) as srv:
        # your requests here

    # Run as decorator
    @Service(routes=['GET', r'/$'])
    def stubbed_func():
        # your requests here

    # Run as class instance
    srv = Service(routes=['GET', r'/$'])
    srv.start()
    # your requests here
    srv.stop()

Before the run of a Service stub at least one route has to be defined.
Examples:
    # Adds a routes, like this:
    Service(routes=['GET', r'/$'])
    Service(routes=('GET', r'/$'))
    Service(routes=[('GET', r'/$'), ('POST', r'/$')])
    Service(routes=(['GET', r'/$'], ['POST', r'/$']))

    # Or add a routes through self-titled methods:
    srv = Service()
    srv.get(r'/$') # srv.post(r'/$') ...

By default, the Service is available at the address "http://localhost:8081" or
"https://localhost:8081" if the secure mode was enabled. The address where the
Service is started can be received through the "host" property.
"""


import logging
import re
from collections import defaultdict
from errno import EADDRINUSE
from functools import wraps
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import zip_longest
from pathlib import Path
from ssl import wrap_socket
from threading import Thread
from time import sleep
from types import FunctionType

from restub.route import Method, Route


logging.basicConfig(
    format='[%(asctime)s.%(msecs)03d] %(message)s \n',
    datefmt='%H:%M:%S',
    level=logging.INFO
)


def handler_factory(server):

    class Handler(BaseHTTPRequestHandler):

        def do_GET(self):
            self.proceed()

        def do_POST(self):
            self.proceed()

        def do_PUT(self):
            self.proceed()

        def do_DELETE(self):
            self.proceed()

        def proceed(self):
            route = server.resolve(self.command, self.path)
            if not route:
                self.send_error(404)
                self.end_headers()
                server.log('Not found %s "%s"' % (self.command, self.path))
                return

            self.send_response(route.status)

            for header in route.headers:
                self.send_header(header, route.headers[header])
            self.end_headers()

            sleep(server.delay)

            if route.data:
                self.wfile.write(bytes(route.data))

            self.print_info(route)
            self.request.close()

        def print_info(self, route):
            hres = [
                'Server: %s' % self.version_string(),
                'Date: %s' % self.date_time_string()
            ]
            hres += ['%s: %s' % (k, v) for k, v in route.headers.items()]
            hreq = ['%s: %s' % (k, v) for k, v in self.headers.items()]
            padding = max(len(header) for header in hreq) + 10
            payload = self.get_payload()

            sline, cols, hdrs = 'Method %s "%s", status: %d', '%-*s%s', ''
            sline = sline % (self.command, self.path, route.status)
            cols = cols % (padding, 'Request headers:', 'Response headers:')

            for req, res in zip_longest(hreq, hres, fillvalue=None):
                req = '%s %s' % (chr(9899), req) if req else ''
                res = '%s %s' % (chr(9898), res) if res else ''
                hdrs += '%-*s %s\n' % (padding - 1, req, res)

            info = {'start_line': sline, 'columns': cols, 'headers': hdrs}
            if payload:
                info['payload'] = '%s Payload: %s' % (chr(10503), payload)

            fmt = '{d[start_line]}\n{d[columns]}\n{d[headers]}{d[payload]}'
            server.log(fmt.format(d=defaultdict(str, **info)))

        def get_payload(self):
            if self.command in ['POST', 'PUT', 'DELETE']:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length:
                    return self.rfile.read(content_length)
            return None

        def log_message(self, *args, **kwargs):
            return

        def version_string(self):
            return 'Restub Service'

    return Handler


class Service:

    def __init__(self, routes=None, port=8081, **kwargs):
        """
        :param routes: (list, tuple) - route or list of routes
        :param port: (int) - port, by default is 8081
        :param kwargs:
            trace (bool) - trace log, by default is False
            delay (int, float) - delay per response in seconds, by default is 0
            secure (bool) - use ssl, by default is False`
            key (str) - absolute file path to ssl private key
            crt (str) - absolute file path to ssl certificate
        """
        self._server = None
        self._routes = []

        if routes:
            if not isinstance(routes, (list, tuple)):
                raise TypeError('Routes should be list or tuple')
            if all(isinstance(route, (list, tuple)) for route in routes):
                self._routes = [Route.cast(route) for route in routes]
            else:
                self._routes = [Route.cast(routes)]

        self.__set_port(port)
        self.__set_trace(kwargs.get('trace', False))
        self.__set_delay(kwargs.get('delay', 0))
        self.__set_crt(kwargs.get('crt', ''))
        self.__set_key(kwargs.get('key', ''))
        self.__set_secure(kwargs.get('secure', False))

    def start(self):
        if self._routes:
            self._server = self._create(attempts=3)
            self.log('Service:%d is running at %s' % (self.port, self.host))
            Thread(target=self._server.serve_forever, daemon=True).start()
        else:
            raise ValueError('Routes not defined')

    def stop(self):
        if self._server:
            self._server.server_close()
            self.log('Service:%d was stopped' % self.port)

    def get(self, path, data=None, headers=None, status=200):
        self._routes.append(Route(Method.GET, path, data, headers, status))

    def post(self, path, data=None, headers=None, status=200):
        self._routes.append(Route(Method.POST, path, data, headers, status))

    def put(self, path, headers=None, status=200):
        self._routes.append(Route(Method.PUT, path, None, headers, status))

    def delete(self, path, data=None, headers=None, status=200):
        self._routes.append(Route(Method.DELETE, path, data, headers, status))

    def resolve(self, method, path):
        for route in self._routes:
            if route.method == method and re.match(route.path, path, re.U):
                return route
        return None

    def log(self, message):
        if self.trace:
            logger = logging.getLogger(__name__)
            logger.info(message)

    def _create(self, attempts):
        while attempts >= 0:
            # Socket is slowly closed, so need more attempts for fast re-open
            try:
                if self.secure:
                    server = HTTPServer(self.socket, handler_factory(self))
                    server.socket = wrap_socket(
                        server.socket,
                        keyfile=self.key,
                        certfile=self.crt,
                        server_side=True
                    )
                    return server
                else:
                    return HTTPServer(self.socket, handler_factory(self))
            except OSError as e:
                if e.errno == EADDRINUSE:
                    sleep(0.5)
                    attempts -= 1
                else:
                    raise
        raise OSError('Port is already busy or operation not permitted')

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args, **kwargs):
        self.stop()

    def __call__(self, obj):
        if isinstance(obj, FunctionType):
            @wraps(obj)
            def wrapper(*args, **kwargs):
                with self:
                    return obj(*args, **kwargs)
            return wrapper
        return obj

    @property
    def socket(self):
        return 'localhost', self.port

    @property
    def host(self):
        proto = 'https' if self.secure else 'http'
        return '%s://%s:%d' % (proto, self.socket[0], self.socket[1])

    def __get_port(self):
        return self.__port

    def __get_trace(self):
        return self.__trace

    def __get_delay(self):
        return self.__delay

    def __get_secure(self):
        return self.__secure

    def __get_key(self):
        return self.__key

    def __get_crt(self):
        return self.__crt

    def __set_port(self, port):
        try:
            self.__port = int(port)
        except (TypeError, ValueError):
            raise TypeError('port should be int')

    def __set_trace(self, trace):
        self.__trace = bool(trace)

    def __set_delay(self, delay):
        try:
            self.__delay = float(delay)
        except (TypeError, ValueError):
            raise TypeError('delay should be int or float')

    def __set_secure(self, secure):
        if secure:
            if not self.crt:
                raise ValueError('crt not exists but ssl is enabled')
            if not self.key:
                raise ValueError('key not exists but ssl is enabled')
        self.__secure = secure

    def __set_key(self, key):
        try:
            self.__key = key if Path(key).exists() else False
        except TypeError:
            raise TypeError('key should be str')

    def __set_crt(self, crt):
        try:
            self.__crt = crt if Path(crt).exists() else False
        except TypeError:
            raise TypeError('crt should be str')

    port = property(__get_port, __set_port)
    trace = property(__get_trace, __set_trace)
    delay = property(__get_delay, __set_delay)
    secure = property(__get_secure, __set_secure)
    key = property(__get_key, __set_key)
    crt = property(__get_crt, __set_crt)
