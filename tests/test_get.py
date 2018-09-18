import asyncio
import pytest

from unittest.mock import Mock, MagicMock

from errata_server.api_beta import Endpoint


class TestGet(object):

    @pytest.mark.asyncio
    async def test_get(self):
        this = Mock()
        this.data = [{'name': 'DSA-1234-5', 'packages': [{'architectures': 'all'}]}]
        this.etag_base = None
        request = Mock()
        request.uri = '/dep/api/beta/debian'
        await Endpoint.get(this, request)
        request.write.assert_called_with(b'[{"name": "DSA-1234-5", "packages": [{"architectures": "all"}]}]')
