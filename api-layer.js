/**
 * CryptoVision API Layer
 * Handles all API calls with:
 * - 10-second timeout
 * - 2 retries with exponential backoff
 * - sessionStorage caching (~60s TTL)
 * - Graceful error handling
 */

const APILayer = (() => {
  'use strict';

  const CONFIG = {
    TIMEOUT: 10000,
    MAX_RETRIES: 2,
    CACHE_TTL: 60000,
    RETRY_DELAY: 1000
  };

  const CACHE = new Map();

  /**
   * Get cached value if valid
   */
  function getFromCache(key) {
    const cached = CACHE.get(key);
    if (!cached) return null;

    const now = Date.now();
    if (now - cached.timestamp > CONFIG.CACHE_TTL) {
      CACHE.delete(key);
      return null;
    }

    return cached.data;
  }

  /**
   * Store in cache
   */
  function setInCache(key, data) {
    CACHE.set(key, {
      data: data,
      timestamp: Date.now()
    });
  }

  /**
   * Fetch with timeout
   */
  function fetchWithTimeout(url, timeout = CONFIG.TIMEOUT) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    return fetch(url, { signal: controller.signal })
      .then((response) => {
        clearTimeout(timeoutId);
        return response;
      })
      .catch((error) => {
        clearTimeout(timeoutId);
        throw error;
      });
  }

  /**
   * Retry logic with exponential backoff
   */
  async function fetchWithRetry(url, retries = CONFIG.MAX_RETRIES) {
    let lastError;

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const response = await fetchWithTimeout(url);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        return await response.json();
      } catch (error) {
        lastError = error;

        if (attempt < retries) {
          const delay = CONFIG.RETRY_DELAY * Math.pow(2, attempt);
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
      }
    }

    throw lastError;
  }

  /**
   * Main fetch function with cache
   */
  async function fetch(url) {
    if (!url || typeof url !== 'string') {
      throw new Error('Invalid URL');
    }

    // Check cache first
    const cached = getFromCache(url);
    if (cached) {
      return cached;
    }

    try {
      const data = await fetchWithRetry(url);
      setInCache(url, data);
      return data;
    } catch (error) {
      console.error('APILayer fetch error:', {
        url: url,
        error: error.message
      });
      throw error;
    }
  }

  /**
   * Clear cache
   */
  function clearCache() {
    CACHE.clear();
  }

  /**
   * Get cache info (for debugging)
   */
  function getCacheInfo() {
    return {
      size: CACHE.size,
      items: Array.from(CACHE.keys())
    };
  }

  return {
    fetch: fetch,
    clearCache: clearCache,
    getCacheInfo: getCacheInfo
  };
})();
