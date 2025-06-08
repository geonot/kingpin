const path = require('path');

module.exports = {
  // Output directory for build files
  outputDir: 'dist',
  // Base URL for assets (useful if deploying to a subdirectory)
  publicPath: process.env.NODE_ENV === 'production' ? '/' : '/',

  devServer: {
    port: 8080, // Frontend dev server port
    proxy: {
      // Proxy API requests starting with /api to the Flask backend
      '/api': {
        target: 'http://127.0.0.1:5000', // Your Flask backend URL
        changeOrigin: true, // Recommended for virtual hosted sites
        ws: true, // Proxy websockets if needed
        // Optional: Rewrite path if backend expects different base
        // pathRewrite: { '^/api': '' },
      },
      // Removed slot proxy rules - these files should be served directly from Vue.js public/ directory
      // Assets proxy for shared assets from backend if needed
       '/assets': { target: 'http://127.0.0.1:5000/static/assets', changeOrigin: true, pathRewrite: {'^/assets': ''}},
    },
    // Optional: Allow external access to dev server
    // host: '0.0.0.0',
    // allowedHosts: 'all', // Use with caution
  },

  configureWebpack: {
    // No need to define separate entry points here if using standard Vue CLI setup
    // entry: { ... }

    resolve: {
      alias: {
        // Define aliases for easier imports
        '@': path.resolve(__dirname, 'src'),
        '@phaser': path.resolve(__dirname, 'src/phaser'),
        '@components': path.resolve(__dirname, 'src/components'),
        '@views': path.resolve(__dirname, 'src/views'),
        '@store': path.resolve(__dirname, 'src/store'),
        '@assets': path.resolve(__dirname, 'src/assets'),
        '@utils': path.resolve(__dirname, 'src/utils'), // Frontend utils if any
      },
      extensions: ['.js', '.vue', '.json'], // Standard extensions
    },
    // Optional: Performance hints
    performance: {
       hints: process.env.NODE_ENV === 'production' ? "warning" : false
    },
    // Optional: Source maps configuration
    devtool: process.env.NODE_ENV === 'production' ? 'source-map' : 'eval-source-map',
  },

  // Chain webpack config for more advanced modifications (e.g., plugins)
  chainWebpack: config => {
    // Example: Define global constants
    config.plugin('define').tap(definitions => {
      definitions[0]['process.env']['VUE_APP_VERSION'] = JSON.stringify(require('./package.json').version);
      // Add Vue.js feature flags to fix warnings
      definitions[0]['__VUE_PROD_HYDRATION_MISMATCH_DETAILS__'] = JSON.stringify(false);
      definitions[0]['__VUE_OPTIONS_API__'] = JSON.stringify(true);
      definitions[0]['__VUE_PROD_DEVTOOLS__'] = JSON.stringify(false);
      return definitions;
    });

     // Optimize Phaser build (optional, may vary based on Phaser version/setup)
     config.module
     .rule('phaser')
     .test(/phaser\.js$/)
     .use('expose-loader')
     .loader('expose-loader')
     .options({ exposes: ['phaser'] })
     .end();
  },

  // Disable CSS extraction in development for HMR, enable in production
  css: {
    extract: process.env.NODE_ENV === 'production',
    sourceMap: process.env.NODE_ENV !== 'production'
  },

  // Progressive Web App (PWA) plugin configuration (optional)
  // pwa: {
  //   name: 'Kingpin Casino',
  //   themeColor: '#4B0082',
  //   // ... other PWA options
  // }
};


