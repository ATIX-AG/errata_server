import pytest
import os
import asyncio

from unittest.mock import Mock

from errata_server.api_beta import Endpoint as BetaEndpoint
from errata_server.api_v1 import Endpoint as V1Endpoint


TEST_DIR = os.path.dirname(os.path.abspath(__file__))


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


@pytest.fixture(params=(BetaEndpoint, V1Endpoint), ids=["beta", "v1"])
def endpoint(request):
    yield request.param('debian', os.path.join(TEST_DIR, 'fixtures'))


@pytest.mark.asyncio
async def test_validate_config(endpoint):
    await endpoint.read_task
    assert endpoint.etag_base == b'abbd247d7efc27b5d2d487387aee289edb1bf26c043d3232a12f34a9f0c16ab5'


@pytest.mark.asyncio
async def test_get_no_data(endpoint):
    await endpoint.read_task
    endpoint.data = None
    request = Mock()
    request.uri = b'/dep/api/beta/debian?releases=stretch'
    request.setETag.return_value = False
    await endpoint.get(request)
    request.write.assert_called_with(b'Service temporarily unavailable')


@pytest.mark.asyncio
async def test_get(endpoint):
    request = Mock()
    request.uri = b'/dep/api/beta/debian?releases=stretch'
    request.setETag.return_value = False
    await endpoint.get(request)
    request.write.assert_called_with(GET_DATA)
    request.setHeader.assert_any_call(b'cache-control', b'public, no-cache')


@pytest.mark.asyncio
async def test_get_with_alias(endpoint):
    request = Mock()
    request.uri = b'/dep/api/beta/debian?releases=stretch/updates'
    request.setETag.return_value = False
    await endpoint.get(request)
    request.write.assert_called_with(GET_DATA)


@pytest.mark.asyncio
async def test_get_with_whitespace(endpoint):
    request = Mock()
    request.uri = b'/dep/api/beta/debian?releases=blue, stretch'
    request.setETag.return_value = False
    await endpoint.get(request)
    request.write.assert_called_with(GET_DATA)


@pytest.mark.asyncio
async def test_get_invalid(endpoint):
    request = Mock()
    request.uri = b'/dep/api/beta/debian?releases=blue'
    request.setETag.return_value = False
    await endpoint.get(request)
    request.write.assert_called_with(b'[]')


@pytest.mark.asyncio
async def test_get_etag(endpoint):
    request = Mock()
    request.uri = b'/dep/api/beta/debian?releases=stretch'
    request.setETag.return_value = True
    await endpoint.get(request)
    request.write.assert_not_called()
    request.setHeader.assert_any_call(b'cache-control', b'public, no-cache')
    request.setETag.assert_called_with(b'c45b9b107d88ae65b41e4fb186fe4e83e6df9e0005724dfdbc352ebfff1e56a8')


@pytest.mark.asyncio
async def test_notify_ignores_unrelated_file(endpoint, monkeypatch):
    await endpoint.read_task

    ensure_future = Mock()
    monkeypatch.setattr(asyncio, 'ensure_future', ensure_future)
    endpoint.read_data = Mock(return_value=object())

    path = Mock()
    path.path = b'/srv/errata/unrelated.json'
    endpoint.notify(None, path, 0)

    ensure_future.assert_not_called()


@pytest.mark.asyncio
async def test_notify_reloads_config_file(endpoint, monkeypatch):
    await endpoint.read_task

    ensure_future = Mock()
    monkeypatch.setattr(asyncio, 'ensure_future', ensure_future)
    reload_marker = object()
    endpoint.read_data = Mock(return_value=reload_marker)

    path = Mock()
    path.path = b'/srv/errata/debian_config.json'
    endpoint.notify(None, path, 0)

    endpoint.read_data.assert_called_once_with()
    ensure_future.assert_called_once_with(reload_marker)


@pytest.mark.asyncio
async def test_response_cache_hit(endpoint):
    request = Mock()
    request.uri = b'/dep/api/beta/debian?releases=stretch'
    request.setETag.return_value = False
    await endpoint.get(request)

    info = endpoint.cached_build_response.cache_info()
    assert info.misses == 1
    assert info.hits == 0

    request2 = Mock()
    request2.uri = b'/dep/api/beta/debian?releases=stretch'
    request2.setETag.return_value = False
    await endpoint.get(request2)

    request2.write.assert_called_with(GET_DATA)
    info = endpoint.cached_build_response.cache_info()
    assert info.misses == 1
    assert info.hits == 1


@pytest.mark.asyncio
async def test_response_cache_normalizes_query(endpoint):
    request = Mock()
    request.uri = b'/dep/api/beta/debian?releases=stretch&architectures=amd64'
    request.setETag.return_value = False
    await endpoint.get(request)

    request2 = Mock()
    request2.uri = b'/dep/api/beta/debian?architectures=amd64&releases=stretch'
    request2.setETag.return_value = False
    await endpoint.get(request2)

    info = endpoint.cached_build_response.cache_info()
    assert info.misses == 1
    assert info.hits == 1


@pytest.mark.asyncio
async def test_response_cache_cleared_after_reload(endpoint):
    request = Mock()
    request.uri = b'/dep/api/beta/debian?releases=stretch'
    request.setETag.return_value = False
    await endpoint.get(request)
    assert len(endpoint.response_cache) == 1

    await endpoint.read_data()

    assert len(endpoint.response_cache) == 0
