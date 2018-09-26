import asyncio
import pytest
import os

from unittest.mock import Mock, MagicMock

from errata_server.api_beta import Endpoint


class TestApiBeta(object):

    @pytest.mark.asyncio
    async def test_validate_config(self):
        endpoint = Endpoint('debian', os.path.join('tests', 'fixtures'))
        await endpoint.read_task
        assert endpoint.etag_base == b'c495526ab95c0959a3d7d858e0055838444c729e03f0be89d6f184227d7c14be'

    @pytest.mark.asyncio
    async def test_get(self):
        this = Mock()
        this.data = [{'name': 'DSA-1234-5', 'packages': [{'architectures': 'all'}]}]
        this.etag_base = None
        request = Mock()
        request.uri = '/dep/api/beta/debian'
        await Endpoint.get(this, request)
        request.write.assert_called_with(b'[{"name": "DSA-1234-5", "packages": [{"architectures": "all"}]}]')
