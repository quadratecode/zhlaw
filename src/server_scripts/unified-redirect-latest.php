<?php
/**
 * Unified redirect script for handling /latest URLs
 * Handles URLs like: /col-zh/131.1/latest -> /col-zh/131.1-125.html (newest version)
 */

// Get the request URI
$requestUri = $_SERVER['REQUEST_URI'];

// Parse the URI to extract collection, ordnungsnummer, and anchor
if (!preg_match('~^/(col-[^/]+)/([^/]+)/latest(?:\?.*)?(?:#(.*))?$~', $requestUri, $matches)) {
    http_response_code(404);
    echo "Invalid URL format";
    exit;
}

$collection = $matches[1];
$ordnungsnummer = $matches[2];
$anchor = isset($_SERVER['REQUEST_URI']) && strpos($_SERVER['REQUEST_URI'], '#') !== false 
    ? substr($_SERVER['REQUEST_URI'], strpos($_SERVER['REQUEST_URI'], '#')) 
    : '';

// Security: validate collection
if (!in_array($collection, ['col-zh', 'col-ch'])) {
    http_response_code(400);
    echo "Invalid collection";
    exit;
}

// Security: validate ordnungsnummer format
if (!preg_match('/^[\d.]+$/', $ordnungsnummer)) {
    http_response_code(400);
    echo "Invalid ordnungsnummer format";
    exit;
}

// Directory where the HTML files are stored
$directory = __DIR__ . '/' . $collection . '/';

if (!is_dir($directory)) {
    http_response_code(404);
    echo "Collection not found";
    exit;
}

// Find all files matching the ordnungsnummer pattern
$pattern = $directory . $ordnungsnummer . '-*.html';
$files = glob($pattern);

if (empty($files)) {
    http_response_code(404);
    echo "No files found for ordnungsnummer: " . htmlspecialchars($ordnungsnummer);
    exit;
}

// Extract nachtragsnummer from each file and find the highest
$maxNachtragsnummer = -1;
$latestFile = null;

foreach ($files as $file) {
    $filename = basename($file);
    if (preg_match('/^' . preg_quote($ordnungsnummer, '/') . '-(\d+)\.html$/', $filename, $fileMatches)) {
        $nachtragsnummer = intval($fileMatches[1]);
        
        if ($nachtragsnummer > $maxNachtragsnummer) {
            $maxNachtragsnummer = $nachtragsnummer;
            $latestFile = $filename;
        }
    }
}

if ($latestFile === null) {
    http_response_code(404);
    echo "No valid files found";
    exit;
}

// Check if anchor exists in the latest version (if anchor is provided)
$anchorExists = true;
if ($anchor && $anchor !== '#') {
    // Load the anchor map
    $mapFile = __DIR__ . '/anchor-maps/' . str_replace('col-', '', $collection) . '/' . $ordnungsnummer . '-map.json';
    
    if (file_exists($mapFile)) {
        $anchorMap = json_decode(file_get_contents($mapFile), true);
        
        // Parse the anchor
        if (preg_match('/^#seq-\d+-prov-(\d+[a-z]?)(?:-sub-(\d+))?/', $anchor, $anchorMatches)) {
            $provision = $anchorMatches[1];
            $subprovision = isset($anchorMatches[2]) ? $anchorMatches[2] : null;
            
            // Check if anchor exists in latest version
            if (isset($anchorMap['provisions'][$provision])) {
                $provData = $anchorMap['provisions'][$provision];
                
                if ($subprovision) {
                    $anchorExists = isset($provData['subprovisions'][$subprovision]) &&
                                  in_array(strval($maxNachtragsnummer), $provData['subprovisions'][$subprovision]['versions']);
                } else {
                    $anchorExists = in_array(strval($maxNachtragsnummer), $provData['versions']);
                }
            } else {
                $anchorExists = false;
            }
        }
    }
}

// Build the redirect URL
$redirectUrl = '/' . $collection . '/' . $latestFile;

// Add parameters if anchor doesn't exist
if ($anchor && !$anchorExists) {
    $redirectUrl .= '?redirected=true&anchor_missing=true';
}

// Add the anchor
$redirectUrl .= $anchor;

// Perform the redirect
header('Location: ' . $redirectUrl, true, 302);
exit;