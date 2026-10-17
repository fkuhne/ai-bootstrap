# syntax=docker/dockerfile:1
# The web UI's image (docs/foundations.md#the-web-ui): Node installs the packages, checks and
# builds the app, then nginx serves the build and forwards /api to the backend. Node isn't in the
# final image.

# The source with its packages, where the gates run: docker compose run --rm frontend-checks
FROM node:24.21.0-alpine3.24 AS dev
WORKDIR /app
# The lockfile alone first, so a change to the source reuses the installed packages.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
ENV NPM_CONFIG_UPDATE_NOTIFIER=false
COPY . .
CMD ["npm", "run", "check"]

FROM dev AS build
# The app's name, in the page's title and its sidebar: APP_NAME, as for the API.
ARG APP_NAME=ai-bootstrap
RUN VITE_APP_NAME="$APP_NAME" npm run build

# nginx's non-root variant, pinned to one stable release: it runs as the user nginx and listens
# on 8080, since a user that isn't root can't open a port below 1024.
FROM nginxinc/nginx-unprivileged:1.30.5-alpine3.24 AS runtime
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
