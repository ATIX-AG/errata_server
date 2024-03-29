# -*- coding: utf-8 -*-

import os
import asyncio
import aiofiles
import simplejson
import hashlib

from typing import (
    Any,
    Dict,
    List,
    Set,
    Tuple,
)

from urllib.parse import urlparse, parse_qs

from twisted.web import server
from twisted.web.resource import Resource
from twisted.web.http import Request
from twisted.internet import inotify
from twisted.python import filepath, log


async def read_json(filename: str) -> Any:
    json_data = []
    async with aiofiles.open(filename, 'r') as fd:
        while True:
            line = await fd.readline()
            if not line:
                break
            json_data.append(line)
    return simplejson.loads('\n'.join(json_data))


# make sure we have a list of entries without leading or trailing whitespaces
def sanitize_query_list(query_list: List[bytearray]) -> Set[str]:
    return set(entry.strip() for entry in b','.join(query_list).decode('utf-8').split(','))


class Endpoint(Resource):
    isLeaf = True

    def __init__(self, operatingsystem: str, datapath: str, *args, **kwargs) -> None:
        super(Endpoint, self).__init__(*args, **kwargs)

        # initialize in memory database
        self.operatingsystem = operatingsystem
        self.datapath = datapath
        self.data = None
        self.releases: Set = set()
        self.components: Set = set()
        self.architectures: Set = set()
        self.release_aliases: Dict = dict()
        self.data_lock = asyncio.Lock()
        self.data_semaphore = asyncio.Semaphore(2)
        self.etag = None

        # set up data directory notifier
        self.notifier = inotify.INotify()
        self.notifier.startReading()
        self.notifier.watch(filepath.FilePath(datapath), callbacks=[self.notify])

        # read initial data
        self.read_task = asyncio.ensure_future(self.read_data())

    # non-blocking coroutines

    async def get(self, request: Request) -> None:
        try:
            if self.data is None:
                await asyncio.wait_for(self.read_task, timeout=30)
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
                releases = set(self.release_aliases.get(release) for release in sanitize_query_list(query[b'releases']))
                releases &= self.releases

            components = None
            if b'components' in query:
                components = sanitize_query_list(query[b'components'])
                components &= self.components

            architectures = None
            if b'architectures' in query:
                architectures = sanitize_query_list(query[b'architectures'])
                architectures.add('all')
                architectures &= self.architectures

            # generate filtered results
            def transform(item):
                result = item.copy()
                if releases is not None:
                    result['packages'] = [package for package in result['packages'] if package['release'] in releases]
                if components is not None:
                    result['packages'] = [package for package in result['packages'] if package['component'] in components]
                if architectures is not None:
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

    async def read_data(self) -> None:
        if self.data_semaphore.locked():
            return
        async with self.data_semaphore:
            async with self.data_lock:
                try:
                    log.msg("Reading config for operatingsystem {}".format(self.operatingsystem))
                    config_data = await read_json(os.path.join(self.datapath, "{}_config.json".format(self.operatingsystem)))
                    releases, components, architectures, release_aliases = await self.validate_config(config_data)
                    log.msg("Found releases: {}; components: {}; architectures: {}".format(releases, components, architectures))
                    log.msg("Release aliases: {}".format(release_aliases))
                    log.msg("Reading data for operatingsystem {}".format(self.operatingsystem))
                    new_data = await read_json(os.path.join(self.datapath, "{}_errata.json".format(self.operatingsystem)))
                    log.msg("Parsing data for operatingsystem {}".format(self.operatingsystem))
                    await self.validate_data(new_data)
                    hasher = hashlib.sha256()
                    hasher.update(simplejson.dumps(config_data).encode('utf8'))
                    hasher.update(simplejson.dumps(new_data).encode('utf8'))
                    log.msg("Pivoting data for operatingsystem {}".format(self.operatingsystem))
                    self.releases, self.components, self.architectures, self.release_aliases = releases, components, architectures, release_aliases
                    self.data = new_data
                    decoded_etag_base = hasher.hexdigest()
                    log.msg("Hash of new data: {}".format(decoded_etag_base))
                    self.etag_base = decoded_etag_base.encode('utf-8')
                except Exception as e:
                    log.err("An Exception occurred while reading data for operatingsystem {} ({})".format(self.operatingsystem, e))

    # This is supposed to throw an exception if something is wrong
    @staticmethod
    async def validate_data(data: str) -> None:
        assert isinstance(data, list), "Errata list should be a list"
        for item in data:
            assert isinstance(item, dict), "Erratum should be a dict"
            assert isinstance(item['packages'], list), "Erratum must have a 'packages' list"
            for package in item['packages']:
                assert isinstance(package, dict), "Erratum's package must be a dict"
                assert isinstance(package['release'], str), "Erratum's package must have 'release'"
                assert isinstance(package['component'], str), "Erratum's package must have 'component'"
                assert isinstance(package['architecture'], str), "Erratum's package must have 'architecture'"
        return data

    @staticmethod
    async def validate_config(config: Any) -> Tuple[Set, Set, Set, Dict]:
        releases: Set = set()
        components: Set = set()
        architectures: Set = set()
        release_aliases: Dict = {}
        assert isinstance(config, dict), "Config must be a dict"
        releases_dict = config['releases']
        assert isinstance(releases_dict, dict), "'releases' must be a dict"
        for release_name, release in releases_dict.items():
            assert isinstance(release_name, str), "releases-key must be a string"
            assert isinstance(release, dict), "releases-value must be a dict"
            aliases = release.get('aliases', [])
            assert isinstance(aliases, list), "'aliases' must be a list"
            for alias in aliases:
                assert isinstance(alias, str), "'aliases'-value must be a string"
                assert alias not in release_aliases, "'aliases'-value must not exist twice"
                release_aliases[alias] = release_name
            # Make the map idempotent for convenience
            release_aliases[release_name] = release_name
            assert isinstance(release['components'], list), "'components' must be a list"
            components.update(release['components'])
            assert isinstance(release['architectures'], list), "'architectures' must be a list"
            architectures.update(release['architectures'])
        releases.update(releases_dict.keys())
        for item in components:
            assert isinstance(item, str), "'components'-value must be a string"
        for item in architectures:
            assert isinstance(item, str), "'architectures'-value must be a string"
        return releases, components, architectures, release_aliases

    # Callbacks

    def render_GET(self, request: Request) -> server.NOT_DONE_YET:
        asyncio.ensure_future(self.get(request))
        return server.NOT_DONE_YET

    def notify(self, _, path: filepath.FilePath, mask: int) -> None:
        if path.path.endswith("{}_config.json".format(self.operatingsystem).encode('utf8')):
            log.msg("event {} on {}".format(', '.join(inotify.humanReadableMask(mask)), path.path))
            asyncio.ensure_future(self.read_data())
