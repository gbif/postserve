#!/bin/sh -e

rm *~ -f
docker build -t mb.gbif.org:5000/postserve .
docker push mb.gbif.org:5000/postserve
