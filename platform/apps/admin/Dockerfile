FROM node:20-alpine AS base

WORKDIR /app
ENV NODE_ENV=production

FROM base AS deps
COPY package.json ./
RUN npm install --omit=dev --no-audit --no-fund && npm cache clean --force

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN apk add --no-cache dumb-init
COPY --from=deps /app/node_modules ./node_modules
COPY --chown=node:node package.json ./
COPY --chown=node:node server.js ./
USER node
EXPOSE 4100
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=5 CMD node -e "fetch('http://127.0.0.1:4100/health').then((r)=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["dumb-init", "node", "server.js"]
