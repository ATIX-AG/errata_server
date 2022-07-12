# -*- coding: utf-8 -*-

import sys
import click

from twisted.internet import asyncioreactor
asyncioreactor.install()

from twisted.web import server
from twisted.web.resource import NoResource
from twisted.internet import reactor, endpoints
from twisted.python import log

from errata_server import api_beta
from errata_server import api_v1


@click.command()
@click.option('--port', help='Port number to serve on', default=8015, type=int)
@click.option('--datapath', help='Path where the data files are located', default='/srv/errata', type=str)
@click.option('--beta/--no-beta', help='Serve beta api', default=False)
def main(port: int, datapath: str, beta: bool) -> None:
    # build document tree
    root = NoResource()
    dep = NoResource()
    root.putChild(b'dep', dep)
    api = NoResource()
    dep.putChild(b'api', api)
    # --- beta api ---
    if beta:
        apibeta = NoResource()
        api.putChild(b'beta', apibeta)
        apibeta.putChild(b'debian', api_beta.Endpoint('debian', datapath))  # served at /api/beta/debian
        apibeta.putChild(b'ubuntu', api_beta.Endpoint('ubuntu', datapath))  # served at /api/beta/ubuntu
        apibeta.putChild(b'ubuntu-esm', api_beta.Endpoint('ubuntu-esm', datapath))  # served at /api/beta/ubuntu-esm
    # --- api v1 ---
    apiv1 = NoResource()
    api.putChild(b'v1', apiv1)
    apiv1.putChild(b'debian', api_v1.Endpoint('debian', datapath))  # served at /api/v1/debian
    apiv1.putChild(b'ubuntu', api_v1.Endpoint('ubuntu', datapath))  # served at /api/v1/ubuntu
    apiv1.putChild(b'ubuntu-esm', api_v1.Endpoint('ubuntu-esm', datapath))  # served at /api/v1/ubuntu-esm

    # run server
    log.startLogging(sys.stdout)
    endpoints.serverFromString(reactor, r"tcp:interface=\:\::port={}".format(port)).listen(server.Site(root))
    reactor.run()


if __name__ == '__main__':
    main()
