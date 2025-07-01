# Stage 1: Build the Vue.js application
FROM node:18-alpine AS build-stage

WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Build the application
# The VUE_APP_API_BASE_URL will be set at runtime by the environment serving the app,
# or through Nginx reverse proxy configuration.
# For the build itself, it might use a default or placeholder.
RUN npm run build

# Stage 2: Serve the application with Nginx
FROM nginx:1.25-alpine

# Copy built assets from the build stage
COPY --from=build-stage /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
