#!/bin/sh
# The image runs the app as the unprivileged 'app' user. When the container
# starts as root (the default), give 'app' ownership of the writable bind-mounts
# and then switch to 'app', so existing host bind-mounts keep working without a
# manual chown. If the container was started as a non-root user, for example with
# `docker run --user`, run the command unchanged.
set -e

if [ "$(id -u)" = "0" ]; then
    # Data (SQLite DB) and secrets (cookies) are small, so chown them recursively.
    chown -R app:app /app/data /app/secrets 2>/dev/null || true
    # Music can be large or on a network share. Only chown the mount point, so
    # new downloads can be written without recursing over the whole library.
    chown app:app /music 2>/dev/null || true
    exec gosu app "$@"
fi

exec "$@"
