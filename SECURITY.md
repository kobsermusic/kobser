# Security

## Reporting a vulnerability

Please report security problems privately through the Security tab of this repository (Report a vulnerability) and not in a public issue.

## What to keep in mind

kobser is meant for your own server and for people you trust.

- At login, kobser derives a Subsonic token from the password and stores the token in its SQLite database (`data/kobser/kobser.db`). The password itself is never stored. The token gives access to the Subsonic API for that user, so keep the database private.
- The apps send the session token in a request header, and in the URL for audio streams and cover art, so it can appear in the access logs of a reverse proxy. If kobser is reachable from the internet, use HTTPS through a reverse proxy such as Caddy, nginx or Traefik so that the token is never sent unencrypted.
- Each user can do what their Navidrome account allows. In addition, logged-in users can add songs to their library and delete songs from it.
- Downloaded files are written only inside the library folder, and file names are cleaned to prevent path traversal.
- The container runs the app as a non-root user.

## Supported versions

Security fixes are released in the latest version only.
