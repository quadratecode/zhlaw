<?php
/**
 * Unified redirect script for both col-zh and col-ch collections
 * Handles URLs like: /col-zh/131.1 -> /col-zh/131.1-125.html (newest version)
 */

// Get parameters
$collection = isset($_GET['collection']) ? $_GET['collection'] : '';
$ordnungsnummer = isset($_GET['ordnungsnummer']) ? $_GET['ordnungsnummer'] : '';

// Validate collection
if (!in_array($collection, ['col-zh', 'col-ch'])) {
    header('HTTP/1.0 400 Bad Request');
    echo 'Invalid collection';
    exit;
}

// Sanitize the 'ordnungsnummer' to prevent security issues (allow only numbers and dots)
$ordnungsnummer = preg_replace('/[^0-9\.]/', '', $ordnungsnummer);

// Check that 'ordnungsnummer' is not empty
if (empty($ordnungsnummer)) {
    header('HTTP/1.0 400 Bad Request');
    echo 'Invalid ordnungsnummer';
    exit;
}

// Set the directory based on collection
$directory = __DIR__ . '/' . $collection . '/';

// Initialize variables
$highestNachtragsnummer = -1;
$highestNachtragsnummerStr = '';
$highestFile = '';

// Check if directory exists
if (!is_dir($directory)) {
    header('HTTP/1.0 404 Not Found');
    echo 'Collection not found';
    exit;
}

// Scan the directory for files
$files = scandir($directory);

// Loop through the files
foreach ($files as $file) {
    // Check if the file starts with the ordnungsnummer and matches the pattern
    $pattern = '/^' . preg_quote($ordnungsnummer, '/') . '\-([0-9]+)\.html$/';

    if (preg_match($pattern, $file, $matches)) {
        $nachtragsnummerStr = $matches[1];
        $nachtragsnummerInt = intval($nachtragsnummerStr);

        // Check if this nachtragsnummer is higher than the current highest
        if ($nachtragsnummerInt > $highestNachtragsnummer) {
            $highestNachtragsnummer = $nachtragsnummerInt;
            $highestNachtragsnummerStr = $nachtragsnummerStr;
            $highestFile = $file;
        } elseif ($nachtragsnummerInt == $highestNachtragsnummer) {
            // If equal, compare strings to handle leading zeros
            if ($nachtragsnummerStr > $highestNachtragsnummerStr) {
                $highestNachtragsnummerStr = $nachtragsnummerStr;
                $highestFile = $file;
            }
        }
    }
}

// Redirect to the highest file if found
if (!empty($highestFile)) {
    header('Location: /' . $collection . '/' . $highestFile);
    exit;
} else {
    header('HTTP/1.0 404 Not Found');
    echo 'No file found for ordnungsnummer ' . htmlspecialchars($ordnungsnummer);
    exit;
}
?>