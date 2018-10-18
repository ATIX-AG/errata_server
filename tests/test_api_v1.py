import asyncio
import pytest
import os

from unittest.mock import Mock, MagicMock

from errata_server.api_beta import Endpoint


TEST_DIR = os.path.dirname(os.path.abspath(__file__))


class TestApiBeta(object):
    GET_DATA = \
        b'[{"name": "DSA-1234-1", "title": "base-camp -- security update", "'\
        b'issued": "01 Jan 1000", "affected_source_package": "base-camp", "p'\
        b'ackages": [{"name": "base-camp", "version": "3.2.1+u1", "architect'\
        b'ure": "amd64", "component": "main", "release": "stretch"}], "descr'\
        b'iption": "A terribly long string to describe what is up.", "cves":'\
        b' ["CVE-1000-1000000"], "severity": "high", "scope": "remote"}, {"n'\
        b'ame": "DSA-2345-1", "title": "second-base -- security update", "is'\
        b'sued": "02 Jan 1000", "affected_source_package": "second-base", "p'\
        b'ackages": [{"name": "libsecond-base", "version": "2.1-1+u1", "arch'\
        b'itecture": "amd64", "component": "main", "release": "stretch"}, {"'\
        b'name": "second-base-common", "version": "2.2-1+u1", "architecture"'\
        b': "all", "component": "main", "release": "stretch"}], "description'\
        b'": "Here is something going on, too", "cves": ["CVE-1000-1000001"]'\
        b', "severity": "not yet assigned", "scope": "local", "dbts_bugs": ['\
        b'10]}]'

    def setup(self):
        self.endpoint = Endpoint('debian', os.path.join(TEST_DIR, 'fixtures'))

    @pytest.mark.asyncio
    async def test_validate_config(self):
        await self.endpoint.read_task
        assert self.endpoint.etag_base == b'abbd247d7efc27b5d2d487387aee289edb1bf26c043d3232a12f34a9f0c16ab5'

    @pytest.mark.asyncio
    async def test_get_no_data(self):
        await self.endpoint.read_task
        self.endpoint.data = None
        request = Mock()
        request.uri = b'/dep/api/beta/debian?releases=stretch'
        request.setETag.return_value = False
        await self.endpoint.get(request)
        request.write.assert_called_with(b'Service temporarily unavailable')

    @pytest.mark.asyncio
    async def test_get(self):
        request = Mock()
        request.uri = b'/dep/api/beta/debian?releases=stretch'
        request.setETag.return_value = False
        await self.endpoint.get(request)
        request.write.assert_called_with(self.GET_DATA)

    @pytest.mark.asyncio
    async def test_get_with_alias(self):
        request = Mock()
        request.uri = b'/dep/api/beta/debian?releases=stretch/updates'
        request.setETag.return_value = False
        await self.endpoint.get(request)
        request.write.assert_called_with(self.GET_DATA)

    @pytest.mark.asyncio
    async def test_get_with_whitespace(self):
        request = Mock()
        request.uri = b'/dep/api/beta/debian?releases=blue, stretch'
        request.setETag.return_value = False
        await self.endpoint.get(request)
        request.write.assert_called_with(self.GET_DATA)

    @pytest.mark.asyncio
    async def test_get_invalid(self):
        request = Mock()
        request.uri = b'/dep/api/beta/debian?releases=blue'
        request.setETag.return_value = False
        await self.endpoint.get(request)
        request.write.assert_called_with(b'[]')

    @pytest.mark.asyncio
    async def test_get_etag(self):
        request = Mock()
        request.uri = b'/dep/api/beta/debian?releases=stretch'
        request.setETag.return_value = True
        await self.endpoint.get(request)
        request.write.assert_not_called()
        request.setETag.assert_called_with(b'c45b9b107d88ae65b41e4fb186fe4e83e6df9e0005724dfdbc352ebfff1e56a8')
