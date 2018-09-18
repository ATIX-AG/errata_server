FROM python:3.7-alpine
RUN apk --no-cache add build-base
WORKDIR /errata_server
COPY . .
RUN pip install .
CMD errata_server
