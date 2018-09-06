"""
A Route represents the ordered sequence of values (method, path, data, headers,
status) describing data which we can receive at the specified address and a
method of access. Therefore the method of access and the address is a required
and other values can be omitted.

When data passed the headers Content-type and Content-length will be
automatically added in response. Of course, you can always override these
headers. Having sent the dict as data the header 'Content-type' with the
value 'application/json' will be added. When str passed, the following
scenarios are possible:

    * If the str is a path to the file existing in system, contents of this
    file will be load in a body of response. At the same time, if the
    extension of the file has a matching with one of  CTYPES values
    (the dictionary containing often used formats of data, such as “css”,
    “js”, “ttf”, etc), the Content-type will be taken there

    * If the str represents json, xml or html document, then the Content-type
    will have the corresponding values: 'application/json', 'application/xml'
    or 'text/html'

    * In all other cases, data will be transferred as 'text/plain'

Examples:
    # Passing methods
    route = Route('GET', ...)
    route = Route('POST', ...)
    route = Route('PUT', ...)
    route = Route('DELETE', ...)

    # Passing path, for example, main page
    route = Route('GET', r'/$')
    # another page
    route = Route('GET', r'/some/$')
    # by regex matching
    route = Route('GET', r'/item/[0-9]+/$')

    # Passing of data, for example, as text/plain
    route = Route('GET', r'/$', 'Hello world')
    # as text/plain too
    route = Route('GET', r'/$', '/home/user/path/to/the/same/txt/file.txt')
    # depending on the file extension, as image/jpg
    route = Route('GET', r'/$', '/home/user/path/to/the/same/img/file.jpg')
    # as text/html
    route = Route('GET', r'/$', '<html><a>Hello world</a></html>')
    # as application/json
    route = Route('GET', r'/$', {'key': 'value'})
    # as application/json too
    route = Route('GET', r'/$', "{'key': 'value'}")

    # Passing and override headers
    route = Route('GET', r'/$', None, {'X-HEADER': 'VALUE'})

    # Passing of status code
    route = Route('GET', r'/$', 'Internal error', None, 500)
"""


import json
from pathlib import Path
from xml.dom.minidom import parseString
from xml.parsers.expat import ExpatError


CTYPES = {
    '.htm': 'text/html',
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.xml': 'application/xml',
    '.csv': 'text/csv',
    '.txt': 'text/plain',
    '.csh': 'application/x-csh',
    '.sh': 'application/x-sh',

    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.ico': 'image/x-icon',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.tif': 'image/tiff',
    '.tiff': 'image/tiff',

    '.mp3': 'audio/mpeg',
    '.aac': 'audio/aac',
    '.mid': 'audio/midi',
    '.midi': 'audio/midi',
    '.oga': 'audio/ogg',
    '.wav': 'audio/x-wav',
    '.weba': 'audio/webm',
    '.3g2': 'audio/3gpp2',

    '.mpeg': 'video/mpeg',
    '.ogv': 'video/ogg',
    '.avi': 'video/x-msvideo',
    '.3gp': 'video/3gpp',
    '.webm': 'video/webm',

    '.7z': 'application/x-7z-compressed',
    '.bz': 'application/x-bzip',
    '.bz2': 'application/x-bzip2',
    '.jar': 'application/java-archive',
    '.tar': 'application/x-tar',
    '.zip': 'application/zip',
    '.rar': 'application/x-rar-compressed',

    '.ttf': 'font/ttf',
    '.otf': 'font/otf',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.eot': 'application/vnd.ms-fontobject',

    '.bin': 'application/octet-stream',
    '.swf': 'application/x-shockwave-flash',
    '.pdf': 'application/pdf',
}


class Method:
    ALLOWED = ['GET', 'POST', 'PUT', 'DELETE']
    GET, POST, PUT, DELETE = ALLOWED


def is_json(data):
    """ Checks if data is JSON content """
    try:
        json.loads(data)
    except ValueError:
        return False
    return True


def is_xml(data):
    """ Checks if data is XML content """
    try:
        parseString(data)
    except ExpatError:
        return False
    return True


def is_html(data):
    """ Lazy check if data is HTML content """
    if data.startswith('<!DOCTYPE html') or data.startswith('<html'):
        return True
    return False


def parse_response(obj):
    """ Parses a response data and select the suitable content-type
    :param obj: (str, dict) response data
    :return: (tuple) data (bytes), content-type (str)
    """
    if isinstance(obj, dict):
        return bytes(json.dumps(obj).encode()), 'application/json'
    elif isinstance(obj, str):
        try:
            with open(obj, 'rb') as f:
                data = f.read()
            return data, CTYPES.get(Path(obj).suffix, 'text/plain')
        except (FileNotFoundError, OSError, IOError):
            if is_json(obj):
                ctype = 'application/json'
            elif is_html(obj):
                ctype = 'text/html'
            elif is_xml(obj):
                ctype = 'application/xml'
            else:
                ctype = 'text/plain'
            return bytes(obj.encode()), ctype
    else:
        raise TypeError('Response data should be str or dict')


class Route:

    __slots__ = '__method', '__path', '__data', '__headers', '__status'

    def __init__(self, method, path, data=None, headers=None, status=200):
        """
        :param method: (str) - access method, can be GET, POST, PUT or DELETE
        :param path: (str) - describing the response address, can be regex
        :param data: (str, dict) - response data
        :param headers: (dict) - HTTP response headers
        :param status: (int) - code of the response status
        """
        self.__data = None
        self.__headers = {}

        try:
            if method.upper() in Method.ALLOWED:
                self.__method = method.upper()
            else:
                raise ValueError('Method "%s" is not allowed' % method)
        except AttributeError:
            raise TypeError('Method name should be str')

        try:
            if path.strip():
                self.__path = path
            else:
                raise ValueError('Path cannot be empty')
        except AttributeError:
            raise TypeError('Path should be str')

        if data:
            self.__data, ctype = parse_response(data)
            self.__headers['Content-type'] = ctype
            self.__headers['Content-length'] = len(self.data)

        if headers:
            try:
                self.__headers.update(headers)
            except (TypeError, ValueError):
                raise TypeError('Headers should be dict')

        try:
            self.__status = int(status)
        except (TypeError, ValueError):
            raise TypeError('Status code should be int')

    @staticmethod
    def cast(route):
        if route and isinstance(route, (list, tuple)):
            try:
                method, path, *opts = route
                data = opts[0] if len(opts) > 0 else None
                headers = opts[1] if len(opts) > 1 else None
                status = opts[2] if len(opts) > 2 else 200
                return Route(method, path, data, headers, status)
            except ValueError:
                raise ValueError('Route should contain method and path')
        else:
            raise TypeError('Route should be list or tuple')

    @property
    def method(self):
        return self.__method

    @property
    def path(self):
        return self.__path

    @property
    def data(self):
        return self.__data

    @property
    def headers(self):
        return self.__headers

    @property
    def status(self):
        return self.__status

    def __str__(self):
        return '<Route[method=%s, path=%s]>' % (self.method, self.path)
