# -*- coding: utf-8 -*-

import sys
import click

from twisted.internet import asyncioreactor
asyncioreactor.install()

from twisted.web import server
from twisted.web.resource import NoResource
from twisted.internet import reactor, endpoints
from twisted.python import log

from errata_server.api_beta import Endpoint


@click.command()
@click.option('--port', help='Port number to serve on', default=8015, type=int)
@click.option('--datapath', help='Path where the data files are located', default='/srv/errata', type=str)
def main(port, datapath):
    # build document tree
    root = NoResource()
    dep = NoResource()
    root.putChild(b'dep', dep)
    api = NoResource()
    dep.putChild(b'api', api)
    apibeta = NoResource()
    api.putChild(b'beta', apibeta)
    apibeta.putChild(b'debian', Endpoint('debian', datapath))  # served at /api/beta/debian
    apibeta.putChild(b'ubuntu', Endpoint('ubuntu', datapath))  # served at /api/beta/ubuntu

    # run server
    log.startLogging(sys.stdout)
    endpoints.serverFromString(reactor, "tcp:{}".format(port)).listen(server.Site(root))
    reactor.run()


if __name__ == '__main__':
    main()
