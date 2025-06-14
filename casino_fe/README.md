# Casino Frontend (Vue.js)

This directory contains the Vue.js frontend application for the casino platform.

## Prerequisites

- Node.js (version specified in `.nvmrc` if available, or latest LTS)
- npm or yarn

## Project Setup

1.  Navigate to the `casino_fe` directory:
    ```bash
    cd casino_fe
    ```

2.  Install dependencies:
    ```bash
    npm install
    # OR
    # yarn install
    ```

## Development Server

To start the development server (usually on `http://localhost:8080`):

```bash
npm run serve
# OR
# yarn serve
```

The development server is typically configured to proxy API requests to the backend (e.g., `http://localhost:5000/api`).

## Build for Production

To build the application for production:

```bash
npm run build
# OR
# yarn build
```
This will create a `dist` directory with the compiled assets.

## Linting and Formatting

To lint and fix files:
```bash
npm run lint
# OR (if configured in package.json)
# yarn lint
```

## Running Tests
(Instructions for running tests would go here - e.g., `npm run test:unit`)

## Key Directories

-   `public/`: Static assets and `index.html`.
-   `src/`: Main application source code.
    -   `assets/`: Static assets like images, fonts, and global styles.
    -   `components/`: Reusable Vue components.
    -   `views/`: Page-level components (routed components).
    -   `router/`: Vue Router configuration.
    -   `store/`: Vuex store modules.
    -   `services/`: API communication and other services.
    -   `main.js`: Application entry point.
    -   `App.vue`: Root Vue component.
