// Cache names
const STATIC_CACHE = 'static-v1';
const DYNAMIC_CACHE = 'dynamic-v1';

// URLs to cache
const STATIC_URLS = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
  // Add other static assets
];

const DYNAMIC_URLS = [
  '/dashboard',
  '/api/food-log',
  '/get_recommendations',
  // Add other dynamic endpoints
];

// Install event
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(STATIC_URLS);
    })
  );
});

// Activate event
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Fetch event with network-first strategy for dynamic content
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  // Check if this is a dynamic URL
  if (DYNAMIC_URLS.some(dynamicUrl => url.pathname.includes(dynamicUrl))) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Clone the response before caching
          const responseToCache = response.clone();
          caches.open(DYNAMIC_CACHE).then((cache) => {
            cache.put(event.request, responseToCache);
          });
          return response;
        })
        .catch(() => {
          // If network fails, try to get from cache
          return caches.match(event.request);
        })
    );
  } else {
    // For static content, use cache-first strategy
    event.respondWith(
      caches.match(event.request)
        .then((response) => {
          return response || fetch(event.request);
        })
    );
  }
}); 