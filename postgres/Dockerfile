# PostgreSQL for Diente Azul: the official image, minus `gosu`, not root.
#
# The official image starts as root and drops to `postgres` through `gosu`,
# a Go binary built with go1.24.6 — the newest gosu release there is. An
# image scanner counts that runtime's advisories against the image: 46 of
# the 57 findings Docker Scout reports on postgres:15.19-alpine3.24, both
# criticals among them. Started as `postgres` the entrypoint never reaches
# gosu, so it is removed rather than rebuilt.
#
# Removing it in a layer on top is not enough, and that is measured: the
# file stays in the layer below and the scanner goes on counting it (57
# findings before and after). Hence the second stage — the filesystem is
# copied into an empty image, which leaves no layer that ever held it.
#
# That copy drops the image's metadata, so it is declared again below. On
# a version bump, set PG_VERSION to match; the build fails if it does not.
#
# To move to a new PostgreSQL release: change the reference here and in the
# two `services.postgres` of .github/workflows/ci.yml (CI cannot build an
# image for a service container, so those run the official one), then the
# tag `dienteazul-postgres:<version>` wherever it is named. A new tag is
# what makes Compose build again instead of reusing an image it already has;
# for the same reason a change to this file on the same PostgreSQL release
# bumps the suffix (`15.19-1`), which counts our own rebuilds.
#
# The weekly audit compares the digest below with what `postgres:15-alpine`
# points at and fails when the pin falls behind; a new major also means
# changing that tag in .github/workflows/security-audit.yml.
FROM postgres:15.19-alpine3.24@sha256:f7d23353e1b15400d22ebe31189f4d314b87a4c129cc400c8c2d8d4ca127bf81 AS upstream

RUN rm /usr/local/bin/gosu

# CVE-2026-85091 — heap overflow in zlib's non-blocking gz* writes, in zlib
# 1.3.1.2 through 1.3.2. Alpine fixed it in 1.3.2-r1; the official image
# pinned above was built before that and ships 1.3.2-r0. Named with its
# version so the build fails rather than quietly keeping the old package.
# Goes when the pin moves to an image that already carries it.
RUN apk add --no-cache 'zlib>=1.3.2-r1'

FROM scratch

COPY --from=upstream / /

ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=en_US.utf8 \
    PG_MAJOR=15 \
    PG_VERSION=15.19 \
    PGDATA=/var/lib/postgresql/data

RUN test "$(postgres --version)" = "postgres (PostgreSQL) $PG_VERSION"

VOLUME /var/lib/postgresql/data

# uid 70 in this image, the owner of every data directory it has created.
USER postgres

ENTRYPOINT ["docker-entrypoint.sh"]

STOPSIGNAL SIGINT

EXPOSE 5432

CMD ["postgres"]
