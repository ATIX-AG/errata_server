# -*- coding: utf-8 -*-

import os
import asyncio
import aiofiles
import simplejson
import hashlib

from urllib.parse import urlparse, parse_qs

from twisted.web import server
from twisted.web.resource import Resource
from twisted.internet import inotify
from twisted.python import filepath, log


class Endpoint(Resource):
    isLeaf = True

    def __init__(self, operatingsystem, datapath, *args, **kwargs):
        super(Endpoint, self).__init__(*args, **kwargs)

        # initialize in memory database
        self.operatingsystem = operatingsystem
        self.datapath = datapath
        self.data = None
        self.releases = set(['stretch', 'wheezy'])
        self.components = set(['main', 'contrib'])
        self.architectures = set(['all'])
        self.data_lock = asyncio.Lock()
        self.data_semaphore = asyncio.Semaphore(2)
        self.etag = None

        # set up data directory notifier
        self.notifier = inotify.INotify()
        self.notifier.startReading()
        self.notifier.watch(filepath.FilePath(datapath), callbacks=[self.notify])

        # read initial data
        asyncio.ensure_future(self.read_data())

    # non-blocking coroutines

    async def get(self, request):
        try:
            if self.data is None:
                request.setResponseCode(503)
                request.write(b'Service temporarily unavailable')
                return

            raw_query = urlparse(request.uri).query
            query = parse_qs(raw_query)

            # Check for etag matching
            if self.etag_base:
                hasher = hashlib.sha256()
                hasher.update(self.etag_base)
                hasher.update(raw_query)
                if request.setETag(hasher.hexdigest().encode('utf-8')):
                    # Etag matched; do not send a body
                    return

            # decode query parameter
            releases = None
            if b'releases' in query:
                releases = set(b','.join(query[b'releases']).decode('utf-8').split(','))
                if releases - self.releases:
                    raise Exception('Invalid query for releases')

            components = None
            if b'components' in query:
                components = set(b','.join(query[b'components']).decode('utf-8').split(','))
                if components - self.components:
                    raise Exception('Invalid query for components')

            architectures = None
            if b'architectures' in query:
                architectures = set(b','.join(query[b'architectures']).decode('utf-8').split(','))
                architectures.add('all')
                if set(architectures) - self.architectures:
                    raise Exception('Invalid query for architectures')

            # generate filtered results
            def transform(item):
                result = item.copy()
                if releases:
                    result['packages'] = [package for package in result['packages'] if package['release'] in releases]
                if components:
                    result['packages'] = [package for package in result['packages'] if package['component'] in components]
                if architectures:
                    result['packages'] = [package for package in result['packages'] if package['architecture'] in architectures]
                return result, bool(result['packages'])

            result = [value for value, pred in map(transform, self.data) if pred]

            # deliver results
            request.setHeader(b'content-type', b'application/json; charset=utf-8')
            request.write(simplejson.dumps(result).encode('utf-8'))
        except Exception as e:
            log.err("An exception occurred while handling request ({})".format(e))
            request.setResponseCode(400)
            request.write('Bad request'.encode('utf-8'))
        finally:
            request.finish()

    async def read_data(self):
        if self.data_semaphore.locked():
            return
        async with self.data_semaphore:
            async with self.data_lock:
                try:
                    log.msg("Reading data for operatingsystem {}".format(self.operatingsystem))
                    json_data = []
                    releases = set()
                    components = set()
                    architectures = set('all')
                    hasher = hashlib.sha256()
                    async with aiofiles.open(os.path.join(self.datapath, "{}_errata.json".format(self.operatingsystem)), 'r') as fd:
                        async for line in fd:
                            json_data.append(line)
                    log.msg("Parsing data for operatingsystem {}".format(self.operatingsystem))
                    new_data = simplejson.loads('\n'.join(json_data))
                    hasher.update(simplejson.dumps(new_data).encode('utf8'))
                    await self.validate_data(new_data)
                    log.msg("Pivoting data for operatingsystem {}".format(self.operatingsystem))
                    self.data = new_data
                    self.etag_base = hasher.hexdigest().encode('utf-8')
                    log.msg("Hash of new data: {}".format(self.etag_base))
                except Exception as e:
                    log.err("An Exception occurred while reading data for operatingsystem {} ({})".format(self.operatingsystem, e))

    # This is supposed to throw an exception if something is wrong
    async def validate_data(self, data):
        assert isinstance(data, list)
        for item in data:
            assert isinstance(item, dict)
            assert isinstance(item['packages'], list)
            for package in item['packages']:
                assert isinstance(package, dict)
                assert isinstance(package['release'], str)
                assert isinstance(package['component'], str)
                assert isinstance(package['architecture'], str)

    # Callbacks

    def render_GET(self, request):
        asyncio.ensure_future(self.get(request))
        return server.NOT_DONE_YET

    def notify(self, _, filepath, mask):
        log.msg("event {} on {}".format(', '.join(inotify.humanReadableMask(mask)), filepath))

        # TODO: Be more specific
        asyncio.ensure_future(self.read_data())
