FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better layer caching.
COPY package.json package-lock.json* ./
RUN npm install

COPY . .

EXPOSE 5173

# --host binds Vite to 0.0.0.0 so it's reachable outside the container.
CMD ["npm", "run", "dev", "--", "--host"]
