/* =========================
SHARED FETCH WRAPPER LIBRARY
========================= */

(function (global) {
  "use strict";

  function createSafeFetch() {
    const CACHE_TTL = 60000;

    return async function safeFetch(url, options = {}) {
      const timeout = options.timeout || 10000;
      const maxRetries = options.maxRetries || 2;
      const useCache = options.useCache !== false;
      const cacheKey = "cache_" + url;

      // Safe sessionStorage access
      if (useCache) {
        try {
          const cached =
            sessionStorage.getItem(
              cacheKey
            );

          if (cached) {
            const entry = JSON.parse(
              cached
            );

            if (
              Date.now() - entry.time <
              CACHE_TTL
            ) {
              return new Response(
                JSON.stringify(
                  entry.data
                ),
                { status: 200 }
              );
            }
          }
        } catch (storageError) {
          console.warn(
            "sessionStorage access failed:",
            storageError.message
          );
        }
      }

      let lastError;

      for (
        let attempt = 0;
        attempt <= maxRetries;
        attempt++
      ) {
        let timeoutId;

        try {
          const controller =
            new AbortController();

          timeoutId =
            setTimeout(
              function () {
                controller.abort();
              },
              timeout
            );

          const response =
            await fetch(url, {
              ...options,
              signal:
                controller.signal
            });

          clearTimeout(timeoutId);

          if (response.ok) {
            const data =
              await response.clone()
                .json();

            if (useCache) {
              try {
                sessionStorage.setItem(
                  cacheKey,
                  JSON.stringify({
                    data: data,
                    time: Date.now()
                  })
                );
              } catch (storageError) {
                console.warn(
                  "Cache write failed:",
                  storageError.message
                );
              }
            }

            return response;
          }

          if (response.status >= 500) {
            throw new Error(
              "Server error " +
              response.status
            );
          }

          return response;

        } catch (error) {
          if (timeoutId) {
            clearTimeout(timeoutId);
          }

          lastError = error;

          if (attempt < maxRetries) {
            const delay =
              Math.pow(2, attempt) *
              1000;

            await new Promise(
              function (resolve) {
                setTimeout(
                  resolve,
                  delay
                );
              }
            );
          }
        }
      }

      throw lastError ||
        new Error("Fetch failed");
    };
  }

  global.SafeFetchLib = {
    createSafeFetch: createSafeFetch
  };

})(typeof window !== "undefined" ? window : global);
