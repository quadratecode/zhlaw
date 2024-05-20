<?php
$directory = 'col-zh/';
$prefix = isset($_GET['prefix']) ? $_GET['prefix'] : '';

// Open the directory
$files = scandir($directory);

// Initialize the highest number
$highestNumber = 0;
$highestFile = '';

// Regex to capture files starting with the specified prefix and ending in .html
$pattern = "/^" . preg_quote($prefix) . "\-(\d+)([a-z]?\.html)$/i";

// Loop through the files
foreach ($files as $file) {
    if (preg_match($pattern, $file, $matches)) {
        // Compute a composite number for comparison, adding a numeric value for any letter suffixes
        $currentNumber = intval($matches[1]) * 10 + (empty($matches[2]) ? 0 : ord($matches[2]) - ord('a') + 1);
        if ($currentNumber > $highestNumber) {
            $highestNumber = $currentNumber;
            $highestFile = $file;
        }
    }
}

// Redirect to the highest numbered file
if (!empty($highestFile)) {
    header("Location: $directory$highestFile");
    exit;
}
?>
