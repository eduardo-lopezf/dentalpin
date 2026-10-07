# syntax=docker/dockerfile:1.6
#
# Multi-stage build for the Diente Azul documentation portal.
#
# Build context MUST be the repository root (or at minimum the `docs/`
# folder), because VitePress' `srcDir` is configured as `..` — pointing one
# level up from `docs/portal/` to `docs/` so all existing markdown is
# rendered without duplication.
#
# Coolify usage:
#   - Repository:        martinezsalmeron/dienteazul
#   - Build context:     /                  (repo root)
#   - Dockerfile path:   docs/portal/Dockerfile
#   - Exposed port:      80
#   - Domain:            docs.dienteazul.com
#   - TLS:               Coolify (Let's Encrypt)

# ---- Builder ----------------------------------------------------------------
FROM node:24-alpine AS builder
WORKDIR /build

# Copy the entire docs tree so VitePress can read it.
COPY docs/ ./docs/

WORKDIR /build/docs/portal

# Install deps and build the static site.
# We use `npm install` rather than `npm ci` until a package-lock.json is
# committed; the lockfile lands in a follow-up PR once the dep set settles.
RUN npm install --no-audit --no-fund \
 && npm run build

# ---- Runtime ----------------------------------------------------------------
# The slim variant: nginx.conf uses nothing beyond the core (try_files, gzip,
# headers, a regex location), and the full image's extra modules — XSLT,
# image filter, GeoIP, njs — bring libxml2, libtiff and curl along with
# their advisories: 18 findings in Docker Scout there, 2 here.
#
# Pinned to a version and its digest (the multi-arch index) rather than a
# floating tag. The weekly audit compares the digest with what
# `nginx:alpine-slim` points at and fails when the pin falls behind.
FROM nginx:1.31.6-alpine-slim@sha256:f761b94f2cb9e8e05e2943d5f773609596113ef69b54e2433a996d109a8f78b7 AS runtime

# Those 2: zlib (CVE-2026-85091) and pcre2 (CVE-2026-103111), both fixed in
# Alpine after this image was built. Named with their versions so the build
# fails rather than quietly keeping the old packages; the line goes when
# the pin moves to an image that carries them.
RUN apk add --no-cache 'zlib>=1.3.2-r1' 'pcre2>=10.49-r0'

# Replace the default config with ours (clean URLs, gzip, cache headers).
COPY docs/portal/nginx.conf /etc/nginx/conf.d/default.conf

# Static site output from the builder.
COPY --from=builder /build/docs/portal/.vitepress/dist/ /usr/share/nginx/html/

EXPOSE 80

# Healthcheck so Coolify can detect a broken build.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1
