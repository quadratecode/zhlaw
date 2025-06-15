<?php
/**
 * Router script for PHP's built-in web server
 * This emulates the .htaccess rewrite rules for handling /latest URLs
 * 
 * Usage: php -S localhost:8000 router.php
 * 
 * NOTE: This file is only for local development with PHP's built-in server.
 * Production servers (Apache/Nginx) will ignore this file and use .htaccess instead.
 */

// Get the requested URI
$uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);

// Check if this is a /latest URL that needs redirection
if (preg_match('#^/(col-zh|col-ch)/([^/]+)/latest/?$#', $uri, $matches)) {
    // Include the unified redirect script
    require __DIR__ . '/unified-redirect-latest.php';
    exit;
}

// Check if this is a simple law redirect (e.g., /col-zh/131.1)
if (preg_match('#^/(col-zh|col-ch)/([0-9.]+)/?$#', $uri, $matches)) {
    $_GET['collection'] = $matches[1];
    $_GET['ordnungsnummer'] = $matches[2];
    
    // Include the unified redirect script
    require __DIR__ . '/unified-redirect.php';
    exit;
}

// For all other requests, check if the file exists
$filePath = __DIR__ . $uri;

// If it's a directory, try to serve index.html
if (is_dir($filePath)) {
    $indexPath = rtrim($filePath, '/') . '/index.html';
    if (file_exists($indexPath)) {
        $filePath = $indexPath;
    }
}

// If the file exists, let PHP's built-in server handle it
if (file_exists($filePath) && is_file($filePath)) {
    return false; // Let PHP's built-in server handle the file
}

// If no file found, return 404
http_response_code(404);
echo "The requested resource $uri was not found on this server.";