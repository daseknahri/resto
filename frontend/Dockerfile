FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=auto
ARG VITE_ADMIN_API_BASE_URL=auto
ARG VITE_APP_NAME=Resto Menu
ARG VITE_MAPS_URL=https://maps.google.com
ARG VITE_CONTACT_PHONE=
ARG VITE_CONTACT_MESSAGE=Hello, I would like to place an order.

ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_ADMIN_API_BASE_URL=${VITE_ADMIN_API_BASE_URL}
ENV VITE_APP_NAME=${VITE_APP_NAME}
ENV VITE_MAPS_URL=${VITE_MAPS_URL}
ENV VITE_CONTACT_PHONE=${VITE_CONTACT_PHONE}
ENV VITE_CONTACT_MESSAGE=${VITE_CONTACT_MESSAGE}

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runner

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 \
  CMD wget -qO- http://127.0.0.1:3000/health >/dev/null || exit 1
