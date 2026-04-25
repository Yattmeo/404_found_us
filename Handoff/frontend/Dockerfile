# Stage 1: build
FROM node:18-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# The app is served under /sales/ by nginx
ENV PUBLIC_URL=/sales
RUN npm run build

# Stage 2: serve built static files
FROM node:18-alpine

WORKDIR /app

RUN npm install -g serve

COPY --from=build /app/build ./build

EXPOSE ${FRONTEND_PORT:-3000}

CMD serve -s build -l ${FRONTEND_PORT:-3000}
