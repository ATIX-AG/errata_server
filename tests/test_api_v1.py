import asyncio
import pytest
import os

from unittest.mock import Mock, MagicMock

from errata_server.api_v1 import Endpoint


TEST_DIR = os.path.dirname(os.path.abspath(__file__))


class TestApiV1(object):
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

    @pytest.mark.asyncio
    async def test_validate_config(self):
        endpoint = Endpoint('debian', os.path.join(TEST_DIR, 'fixtures'))
        await endpoint.read_task
        assert endpoint.etag_base == b'abbd247d7efc27b5d2d487387aee289edb1bf26c043d3232a12f34a9f0c16ab5'

    @pytest.mark.asyncio
    async def test_get(self):
        this = Mock()
        this.data = [{'name': 'DSA-1234-5', 'packages': [{'architectures': 'all'}]}]
        this.etag_base = None
        request = Mock()
        request.uri = b'/dep/api/v1/debian'
        await Endpoint.get(this, request)
        request.write.assert_called_with(b'[{"name": "DSA-1234-5", "packages": [{"architectures": "all"}]}]')

    @pytest.mark.asyncio
    async def test_get2(self):
        endpoint = Endpoint('debian', os.path.join(TEST_DIR, 'fixtures'))
        await endpoint.read_task
        request = Mock()
        request.uri = b'/dep/api/v1/debian?releases=stretch'
        request.setETag.return_value = False
        await endpoint.get(request)
        request.write.assert_called_with(self.GET_DATA)

    @pytest.mark.asyncio
    async def test_get_with_alias(self):
        endpoint = Endpoint('debian', os.path.join(TEST_DIR, 'fixtures'))
        await endpoint.read_task
        request = Mock()
        request.uri = b'/dep/api/v1/debian?releases=stretch/updates'
        request.setETag.return_value = False
        await endpoint.get(request)
        request.write.assert_called_with(self.GET_DATA)

    @pytest.mark.asyncio
    async def test_get_invalid(self):
        endpoint = Endpoint('debian', os.path.join(TEST_DIR, 'fixtures'))
        await endpoint.read_task
        request = Mock()
        request.uri = b'/dep/api/v1/debian?releases=blue'
        request.setETag.return_value = False
        await endpoint.get(request)
        request.write.assert_called_with(b'Bad request')
