import asyncio
import pytest
import os

from unittest.mock import Mock, MagicMock

from errata_server.api_v1 import Endpoint


TEST_DIR = os.path.dirname(os.path.abspath(__file__))


class TestApiV1(object):

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
        request.uri = '/dep/api/beta/debian'
        await Endpoint.get(this, request)
        request.write.assert_called_with(b'[{"name": "DSA-1234-5", "packages": [{"architectures": "all"}]}]')
