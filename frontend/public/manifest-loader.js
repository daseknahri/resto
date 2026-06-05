// Picks the PWA manifest based on the route: tenant-branded dynamic manifest
// for customer-facing pages, static manifest for owner/admin/auth pages.
//
// Kept as an external file (not inline in index.html) so the Content-Security
// Policy can use a strict `script-src 'self'` without needing 'unsafe-inline'
// or a per-build hash.
(function () {
  var path = location.pathname;
  var isDriver = path.startsWith('/driver');
  var isCustomer =
    !isDriver &&
    !path.startsWith('/owner') &&
    !path.startsWith('/waiter') &&
    !path.startsWith('/admin') &&
    !path.startsWith('/signin') &&
    !path.startsWith('/activate') &&
    !path.startsWith('/forgot') &&
    !path.startsWith('/reset');
  var href = isDriver
    ? '/driver-manifest.json'           // installs as a dedicated "Driver" app (start_url /driver)
    : (isCustomer ? '/app-manifest.json' : '/manifest.json');
  var link = document.createElement('link');
  link.rel = 'manifest';
  link.href = href;
  document.head.appendChild(link);
})();
