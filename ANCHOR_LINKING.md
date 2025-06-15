# Anchor Linking with PHP Built-in Server

## Problem
The PHP built-in server (`php -S localhost:8000`) doesn't support `.htaccess` files or Apache mod_rewrite rules, causing 404 errors for URLs like `/col-zh/170.4/latest`.

## Solution
Use the provided `router.php` script which emulates the rewrite rules.

## Usage

### For public_test directory:
```bash
cd /home/rdm/github/zhlaw/public_test
php -S localhost:8000 router.php
```

### For public directory (after building the site):
```bash
cd /home/rdm/github/zhlaw/public
php -S localhost:8000 router.php
```

## How it Works
1. The router intercepts requests to `/col-zh/170.4/latest` or `/col-ch/170.4/latest`
2. It calls the appropriate `redirect-latest.php` script
3. The redirect script finds the latest version and redirects to it (e.g., `170.4-125.html`)

## Important Limitations
- **Anchors are not sent to the server**: The fragment part of URLs (e.g., `#seq-0-prov-1-sub-2`) is never sent to the server by browsers
- The server-side anchor validation in `redirect-latest.php` won't work as intended
- However, the browser will still jump to the anchor after the redirect completes

## Alternative Solutions
1. Use Apache or Nginx for proper `.htaccess` support
2. Modify the application to use query parameters instead of anchors for server-side validation
3. Implement client-side JavaScript for anchor validation

## File Locations
- Router script: `public/router.php` or `public_test/router.php`
- Unified redirect scripts: `public/unified-redirect.php` and `public/unified-redirect-latest.php`
- These handle both col-zh and col-ch collections from a single location

## Benefits of Unified Scripts
- Single point of maintenance for redirect logic
- No duplicate code across collections
- Easier to add new collections in the future
- Consistent behavior across all collections