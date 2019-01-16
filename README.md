Slick Errata Server for Katello
===

This `errata_server` provides an HTTP interface for obtaining Debian and Ubuntu errata as parsed by the companion `errata_parser` project (https://github.com/ATIX-AG/errata_parser).

It is ultimately intended as an errata source for Debian and Ubuntu repositories within Katello (https://github.com/Katello/katello).
However, at the time of writing the needed changes to Katello have not yet been merged.

Since this errata server ultimately just provides an interface to retrieve lists of errata in JSON format, it can be considered a stand alone errata service.
The errata server is written in python, and uses twisted and asyncio.
It is intended to run within a Docker container.


# Prerequisites

* A working Docker installation (https://docs.docker.com/install/)
* Access to the `python:3.7-alpine` Docker image (https://hub.docker.com/_/python)
* Input data as provided by the `errata_parser` companion project (https://github.com/ATIX-AG/errata_parser)


# Quick Start

To build the relevant container image use:

    docker build -t errata_server:latest .

To run the errata server on your local machine you can use:

    docker run --rm\
      --mount type=volume,source=errata,target=/srv/errata,readonly \
      --name errata_server \
      -p 127.0.0.1:80:8015 \
      errata_server:latest

If you have not yet provided the needed input data by using the `errata_parser` companion project, the container will complain as follows:

    2019-01-23 13:45:55+0000 [-] "An Exception occurred while reading data for operatingsystem debian ([Errno 2] No such file or directory: '/srv/errata/debian_config.json')"
    2019-01-23 13:45:55+0000 [-] "An Exception occurred while reading data for operatingsystem ubuntu ([Errno 2] No such file or directory: '/srv/errata/ubuntu_config.json')"

The server is designed to continually monitor the `/srv/errata/` location for new input data, so you can still generate the needed errata lists after starting the server.
You can also periodically rerun the errata parser to update your local errata lists.
For more on using the `errata_parser`, see the `README.md` file here:
https://github.com/ATIX-AG/errata_parser

You can use the `-d` or `--detach` flag with the `docker run` command to send the container to the background.
For more on the `docker run` command, see the docker documentation:
https://docs.docker.com/engine/reference/commandline/run/


## HTTP API Usage

Once the server is up and running, you can now use the provided HTTP API.
Using the container run from the previous section as an example, it will provide errata lists in JSON format in the following locations (provided the server has received the relevant input data):

    http://127.0.0.1/dep/api/v1/debian
    http://127.0.0.1/dep/api/v1/ubuntu

These base locations will provide all errata information for Debian and Ubuntu respectively, that the server knows about.
These complete errata lists can now be filtered by appending the above lists with a combination of "releases", "components", and "architectures", as used by Debian package repositories.

The format goes as follows:

    ?releases=<releases>&components=<components>&architectures=<architectures>

Where `<releases>`, `<components>`, and `<architectures>` are comma seperated lists.

A subset of the above is also acceptable:

    ?releases=<releases>

A full example:

    http://127.0.0.1/dep/api/v1/debian?releases=stretch&components=main,contrib&architectures=amd64,i386

Note that filtering by "releases" and "components" will generally eliminate entire errata, while filtering by "architectures" will simply result in errata that do not contain the binary packages of the architectures not filtered for.
