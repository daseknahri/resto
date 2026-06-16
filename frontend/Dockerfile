FROM node:26-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=auto
ARG VITE_ADMIN_API_BASE_URL=auto
ARG VITE_PLATFORM_PUBLIC_HOSTS=localhost,127.0.0.1
ARG VITE_PUBLIC_DEMO_TENANT_SLUG=
ARG VITE_APP_NAME=Resto_Menu
ARG VITE_MAPS_URL=https://maps.google.com
ARG VITE_CONTACT_PHONE=
ARG VITE_CONTACT_MESSAGE=Hello_I_would_like_to_place_an_order.
ARG VITE_SENTRY_DSN=
ARG VITE_SENTRY_ENVIRONMENT=production
ARG VITE_SENTRY_RELEASE=
ARG VITE_SENTRY_TRACES_SAMPLE_RATE=0

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_ADMIN_API_BASE_URL=${VITE_ADMIN_API_BASE_URL}
ENV VITE_PLATFORM_PUBLIC_HOSTS=${VITE_PLATFORM_PUBLIC_HOSTS}
ENV VITE_PUBLIC_DEMO_TENANT_SLUG=${VITE_PUBLIC_DEMO_TENANT_SLUG}
ENV VITE_APP_NAME=${VITE_APP_NAME}
ENV VITE_MAPS_URL=${VITE_MAPS_URL}
ENV VITE_CONTACT_PHONE=${VITE_CONTACT_PHONE}
ENV VITE_CONTACT_MESSAGE=${VITE_CONTACT_MESSAGE}
ENV VITE_SENTRY_DSN=${VITE_SENTRY_DSN}
ENV VITE_SENTRY_ENVIRONMENT=${VITE_SENTRY_ENVIRONMENT}
ENV VITE_SENTRY_RELEASE=${VITE_SENTRY_RELEASE}
ENV VITE_SENTRY_TRACES_SAMPLE_RATE=${VITE_SENTRY_TRACES_SAMPLE_RATE}

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runner

# R13: non-root nginx.
# nginx:1.27-alpine ships with a built-in `nginx` user (UID 101 / GID 101).
# To run without root we must:
#   1. Replace /etc/nginx/nginx.conf so pid, temp, and cache paths live under
#      /tmp (writable by any user) not /var/run / /var/cache (owned by root).
#   2. Fix ownership of the html root and the conf.d directory.
#   3. Drop to USER 101 (numeric) before CMD.
# The server block in nginx.conf listens on 8080 (unprivileged); the compose
# file maps container:8080 to host:3000 so no external reference changes.

# Write a slim global nginx.conf that redirects all writable paths under /tmp.
RUN printf 'worker_processes auto;\n\
pid /tmp/nginx.pid;\n\
\n\
events {\n\
    worker_connections 1024;\n\
}\n\
\n\
http {\n\
    include       /etc/nginx/mime.types;\n\
    default_type  application/octet-stream;\n\
    sendfile      on;\n\
    keepalive_timeout 65;\n\
\n\
    # R13: redirect all nginx temp/cache dirs to /tmp so they are writable\n\
    # by the non-root nginx user (UID 101) without any volume mounts.\n\
    client_body_temp_path  /tmp/nginx_client_body;\n\
    proxy_temp_path        /tmp/nginx_proxy;\n\
    fastcgi_temp_path      /tmp/nginx_fastcgi;\n\
    uwsgi_temp_path        /tmp/nginx_uwsgi;\n\
    scgi_temp_path         /tmp/nginx_scgi;\n\
\n\
    include /etc/nginx/conf.d/*.conf;\n\
}\n' > /etc/nginx/nginx.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

# Fix ownership so nginx (UID 101) can read conf and html.
RUN chown -R 101:101 /usr/share/nginx/html /etc/nginx/conf.d \
    && chmod -R 755 /usr/share/nginx/html

USER 101

# Expose the unprivileged port the server block listens on.
EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD wget -qO- http://127.0.0.1:8080/health >/dev/null || exit 1
