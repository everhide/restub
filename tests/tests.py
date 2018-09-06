"""
Generate private key and certificate before running tests.
For example, in Linux:
    openssl req -new -x509 -days 365 -nodes -out restub.crt -keyout restub.key
"""


import json
import logging
import unittest
import warnings
from pathlib import Path
from shutil import rmtree
from time import time

import requests

from restub.route import CTYPES, Method, Route
from restub.stub import Service


class ServiceArgsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        tests_path = Path(Path(__file__).parent).absolute()
        cls.key = Path(tests_path).joinpath('restub.key').as_posix()
        cls.crt = Path(tests_path).joinpath('restub.crt').as_posix()

    def test_port_change(self):
        port = 7777
        with Service(routes=[Method.GET, r'/$'], port=port) as srv:
            self.assertEqual(srv.port, port)

    def test_port_invalid(self):
        with self.assertRaises(TypeError):
            Service(routes=[Method.GET, r'/$'], port=None)

    def test_delay(self):
        idle = 0.5
        with Service(routes=[Method.GET, r'/$'], delay=idle) as srv:
            time_start = time()
            requests.get(srv.host)
            time_end = time()
        self.assertGreaterEqual(time_end - time_start, idle)

    def test_delay_invalid(self):
        with self.assertRaises(TypeError):
            Service(routes=[Method.GET, r'/$'], delay=None)

    def test_secure(self):
        secure_opts = {
            'secure': True, 'key': self.key, 'crt': self.crt
        }
        with warnings.catch_warnings():
            # https://github.com/urllib3/urllib3/issues/497
            warnings.simplefilter("ignore")
            with Service(routes=[Method.GET, r'/$'], **secure_opts) as srv:
                res = requests.get(srv.host, verify=self.crt)
                self.assertEqual(res.status_code, 200)

    def test_secure_without_key(self):
        secure_opts = {'secure': True, 'crt': self.crt}
        with self.assertRaises(ValueError):
            Service(routes=[Method.GET, r'/$'], **secure_opts)

    def test_secure_without_crt(self):
        secure_opts = {'secure': True, 'key': self.key}
        with self.assertRaises(ValueError):
            Service(routes=[Method.GET, r'/$'], **secure_opts)

    def test_trace(self):
        with self.assertLogs(Service.__module__, logging.INFO):
            with Service(routes=[Method.GET, r'/$'], trace=True) as srv:
                requests.get(srv.host)


class ServiceTest(unittest.TestCase):

    @Service(routes=[Method.GET, r'/$'], port=8081)
    def test_run_as_decorator(self):
        res = requests.get('http://localhost:8081/')
        self.assertEqual(res.status_code, 200)

    def test_run_as_context_manager(self):
        with Service(routes=[Method.GET, r'/$']) as srv:
            res = requests.get(srv.host)
            self.assertEqual(res.status_code, 200)

    def test_run_without_routes(self):
        with self.assertRaises(ValueError):
            Service(routes=None).start()

    def test_routes_set_through_args(self):
        with Service(routes=[Method.GET, r'/path/$']) as srv:
            res = requests.get('%s/path/' % srv.host)
            self.assertEqual(res.status_code, 200)

    def test_routes_set_through_method(self):
        srv = Service()
        srv.get(r'/path/$')
        srv.start()
        try:
            res = requests.get('%s/path/' % srv.host)
            self.assertEqual(res.status_code, 200)
        finally:
            srv.stop()

    def test_routes_set_combine(self):
        srv = Service(routes=[Method.GET, r'/path/$'])
        srv.post(r'/path/$')
        srv.start()
        try:
            get = requests.get('%s/path/' % srv.host)
            post = requests.post('%s/path/' % srv.host)
            self.assertTrue(get.status_code == post.status_code == 200)
        finally:
            srv.stop()

    def test_route_not_found(self):
        with Service(routes=[Method.GET, r'/$']) as srv:
            res = requests.get('%s/unknown_path' % srv.host)
            self.assertEqual(res.status_code, 404)

    def test_route_regex(self):
        with Service(routes=[Method.GET, r'/user/[0-9]+/$']) as srv:
            res = requests.get('%s/user/777/' % srv.host)
            self.assertEqual(res.status_code, 200)


class RouteTest(unittest.TestCase):

    def test_method_get(self):
        route = Route.cast([Method.GET, r'/$'])
        self.assertEqual(route.method, Method.GET)

    def test_method_post(self):
        route = Route.cast([Method.POST, r'/$'])
        self.assertEqual(route.method, Method.POST)

    def test_method_put(self):
        route = Route.cast([Method.PUT, r'/$'])
        self.assertEqual(route.method, Method.PUT)

    def test_method_delete(self):
        route = Route.cast([Method.DELETE, r'/$'])
        self.assertEqual(route.method, Method.DELETE)

    def test_method_case_insensitive(self):
        route = Route.cast(['GeT', r'/$'])
        self.assertEqual(route.method, Method.GET)

    def test_method_invalid_type(self):
        with self.assertRaises(TypeError):
            Route.cast([None, r'/$'])

    def test_method_invalid_value(self):
        with self.assertRaises(ValueError):
            Route.cast(['UNKNOWN_METHOD_NAME', r'/$'])

    def test_path_invalid_type(self):
        with self.assertRaises(TypeError):
            Route.cast([Method.GET, None])

    def test_path_empty(self):
        with self.assertRaises(ValueError):
            Route.cast([Method.GET, r' '])

    def test_data_type_str(self):
        test_plain = "Lorem ipsum dolor sit"
        route = Route.cast([Method.GET, r'/$', test_plain])
        self.assertEqual(test_plain, route.data.decode())

    def test_data_type_dict(self):
        test_dict = {"key": "value"}
        route = Route.cast([Method.GET, r'/$', test_dict])
        self.assertEqual(test_dict, json.loads(route.data.decode()))

    def test_data_type_none(self):
        route = Route.cast([Method.GET, r'/$', None])
        self.assertIsNone(route.data)

    def test_data_type_invalid(self):
        with self.assertRaises(TypeError):
            Route.cast([Method.GET, r'/$', 1])

    def test_data_ctype_plain(self):
        route = Route.cast([Method.GET, r'/$', 'Lorem ipsum'])
        self.assertEqual(route.headers['Content-type'], 'text/plain')

    def test_data_ctype_dict(self):
        route = Route.cast([Method.GET, r'/$', {"quote": "Lorem ipsum"}])
        self.assertEqual(route.headers['Content-type'], 'application/json')

    def test_data_ctype_xml(self):
        route = Route.cast([Method.GET, r'/$', '<?xml version="1.0"?><_/>'])
        self.assertEqual(route.headers['Content-type'], 'application/xml')

    def test_data_ctype_html(self):
        route = Route.cast([Method.GET, r'/$', '<html><a>Welcome</a></html>'])
        self.assertEqual(route.headers['Content-type'], 'text/html')

    def test_data_ctype_json(self):
        route = Route.cast([Method.GET, r'/$', '{"quote": "Lorem ipsum"}'])
        self.assertEqual(route.headers['Content-type'], 'application/json')

    def test_data_ctype_none(self):
        route = Route.cast([Method.GET, r'/$', None])
        self.assertNotIn('Content-type', route.headers)

    def test_data_ctype__from_file(self):
        if not Path.exists(Path().joinpath('temp_data')):
            Path('temp_data').mkdir()
        tmp = Path().joinpath('temp_data').absolute()
        files = [Path(tmp).joinpath('file%s' % ext) for ext in CTYPES.keys()]
        try:
            for f in files:
                open(f.as_posix(), 'a').close()
                ext = Path(f).suffix
                route = Route.cast([Method.GET, r'/$', f.as_posix()])
                self.assertEqual(CTYPES[ext], route.headers['Content-type'])
        finally:
            if Path(tmp).exists() and Path(tmp).is_dir():
                rmtree(tmp.as_posix())

    def test_data_ctype_override(self):
        header = {"Content-type": "text/html"}
        route = Route.cast([Method.GET, r'/$', 'test text', header])
        self.assertEqual(route.headers['Content-type'], header['Content-type'])

    def test_data_clen_str(self):
        test = "test text"
        route = Route.cast([Method.GET, r'/$', test])
        self.assertEqual(int(route.headers['Content-length']), len(test))

    def test_data_clen_dict(self):
        test = {"key": "value"}
        route = Route.cast([Method.GET, r'/$', test])
        ref_len = len(json.dumps(test))
        cast_len = int(route.headers['Content-length'])
        self.assertEqual(ref_len, cast_len)

    def test_headers_none(self):
        route = Route.cast([Method.GET, r'/$', None, None])
        self.assertEqual(route.headers, {})

    def test_headers_custom(self):
        header = {"CUSTOM-HEADER": "VALUE"}
        route = Route.cast([Method.GET, r'/$', None, header])
        self.assertDictEqual(route.headers, header)

    def test_headers_invalid(self):
        with self.assertRaises(TypeError):
            Route.cast([Method.GET, r'/$', None, 3.14])

    def test_status_default_200(self):
        route = Route.cast([Method.GET, r'/$'])
        self.assertEqual(route.status, 200)

    def test_status_override(self):
        route = Route.cast([Method.GET, r'/$', None, None, 404])
        self.assertEqual(route.status, 404)

    def test_status_invalid_type(self):
        with self.assertRaises(TypeError):
            Route.cast([Method.GET, r'/$', None, None, 'status'])


if __name__ == '__main__':
    unittest.main()
