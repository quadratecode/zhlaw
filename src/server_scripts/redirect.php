<?php
// redirector.php
// This script constructs dynamic URLs for laws, weheras the user can only enter www.zhlaw.ch/col-zh/<ordnungsnummer>
// and be redirected to the newest version


// Set the directory to the current directory (col-zh/)
$directory = './';

// Get the 'ordnungsnummer' from the query parameter
$ordnungsnummer = isset($_GET['ordnungsnummer']) ? $_GET['ordnungsnummer'] : '';

// Sanitize the 'ordnungsnummer' to prevent security issues (allow only numbers and dots)
$ordnungsnummer = preg_replace('/[^0-9\.]/', '', $ordnungsnummer);

// Check that 'ordnungsnummer' is not empty
if (empty($ordnungsnummer)) {
    header('HTTP/1.0 400 Bad Request');
    echo 'Invalid ordnungsnummer';
    exit;
}

// Initialize variables
$highestNachtragsnummer = -1; // Start with -1 so any non-negative integer will be higher
$highestNachtragsnummerStr = ''; // To keep track of the original string with leading zeros
$highestFile = '';

// Scan the directory for files
$files = scandir($directory);

// Loop through the files
foreach ($files as $file) {
    // Check if the file starts with the ordnungsnummer and matches the pattern
    // The filename should be in the format ordnungsnummer-nachtragsnummer.html
    $pattern = '/^' . preg_quote($ordnungsnummer, '/') . '\-([0-9]+)\.html$/';

    if (preg_match($pattern, $file, $matches)) {
        $nachtragsnummerStr = $matches[1];
        // Convert nachtragsnummer to integer for comparison
        $nachtragsnummerInt = intval($nachtragsnummerStr);

        // Check if this nachtragsnummer is higher than the current highest
        if ($nachtragsnummerInt > $highestNachtragsnummer) {
            $highestNachtragsnummer = $nachtragsnummerInt;
            $highestNachtragsnummerStr = $nachtragsnummerStr; // Keep the string with leading zeros
            $highestFile = $file;
        } elseif ($nachtragsnummerInt == $highestNachtragsnummer) {
            // If the integer values are equal, compare the strings to keep the one with the highest value considering leading zeros
            if ($nachtragsnummerStr > $highestNachtragsnummerStr) {
                $highestNachtragsnummerStr = $nachtragsnummerStr;
                $highestFile = $file;
            }
        }
    }
}

// Redirect to the highest file if found
if (!empty($highestFile)) {
    // Redirect to the file
    header('Location: ' . $highestFile);
    exit;
} else {
    // No matching files found
    header('HTTP/1.0 404 Not Found');
    echo 'No file found for ordnungsnummer ' . htmlspecialchars($ordnungsnummer);
    exit;
}
?>
