#!/usr/bin/env python3
"""
Module: scrape_collection_fedlex

This module performs the following steps:

1. Ensures that the directories 'data/fedlex/fedlex_data' and 'data/fedlex/fedlex_files'
   exist (creating them if necessary) and deletes any existing content in them.
2. Downloads (via a shallow git clone) the contents of the repository's `eli/cc` folder
   from https://github.com/droid-f/fedlex.git into the directory 'data/fedlex/fedlex_data'.
3. Flattens the directory structure in 'data/fedlex/fedlex_data' so that all files end up
   directly in that folder.
4. Downloads (via a shallow git clone) the contents of the repository's `eli/cc` folder
   from https://github.com/droid-f/fedlex-assets.git into the directory 'data/fedlex/fedlex_files'.
5. Flattens the directory structure in 'data/fedlex/fedlex_files'.
6. Processes the files in 'fedlex_files' as follows:
    - Replace the prefix "fedlex-data-admin-ch-eli-cc" with "fedlex-cc".
    - Remove the "-html" suffix that appears immediately before the extension.
    - Only keep files that (after these cleaning steps) have a base name ending in "-de".

For example, the file:

    fedlex-data-admin-ch-eli-cc-1-59_57_59-19841101-de-html.html

will be processed to become:

    fedlex-cc-1-59_57_59-19841101-de.html

and kept because its base name ends with "-de".

Usage:
    python scrape_collection_fedlex.py
"""

import os
import glob
import shutil
import subprocess

# Define constants for directories and repository URLs
FEDLEX_FILES_DIR = os.path.join("data", "fedlex", "fedlex_files_raw")

FEDLEX_REPO_URL = "https://github.com/droid-f/fedlex.git"
FEDLEX_ASSETS_REPO_URL = "https://github.com/droid-f/fedlex-assets.git"

TEMP_FEDLEX_ASSETS_DIR = "temp/temp_fedlex_assets"
CC_SUBDIR = os.path.join("eli", "cc")


def remove_dir_contents(directory: str):
    """
    Ensure that a directory exists and is empty.

    If the directory exists, its entire content is removed.
    Otherwise, the directory is created.
    """
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.makedirs(directory, exist_ok=True)


def flatten_directory(directory: str):
    """
    Flatten the directory by moving all files from any subdirectory
    directly into the specified top-level directory.
    If files with the same name are encountered, a numeric suffix is added.
    Finally, empty subdirectories are removed.
    """
    pattern = os.path.join(directory, "**", "*")
    for filepath in glob.iglob(pattern, recursive=True):
        if os.path.isfile(filepath):
            filename = os.path.basename(filepath)
            dst_path = os.path.join(directory, filename)
            # If a file with the same name exists, add a suffix.
            if os.path.exists(dst_path):
                base, ext = os.path.splitext(filename)
                counter = 1
                new_filename = f"{base}_{counter}{ext}"
                dst_path = os.path.join(directory, new_filename)
                while os.path.exists(dst_path):
                    counter += 1
                    new_filename = f"{base}_{counter}{ext}"
                    dst_path = os.path.join(directory, new_filename)
            shutil.move(filepath, dst_path)

    # Remove any empty directories (walk bottom-up).
    for root, dirs, _ in os.walk(directory, topdown=False):
        # Skip the top-level directory itself.
        if os.path.abspath(root) == os.path.abspath(directory):
            continue
        try:
            os.rmdir(root)
        except OSError:
            # Directory not empty.
            pass


def clone_repo(repo_url: str, clone_dir: str):
    """
    Clone a git repository (shallow clone) into a specified local directory.
    If the target directory already exists, it is removed first.
    """
    if os.path.exists(clone_dir):
        shutil.rmtree(clone_dir)
    subprocess.run(["git", "clone", "--depth", "1", repo_url, clone_dir], check=True)


def copy_cc_folder(src_base: str, dst: str):
    """
    Copy the contents of the 'eli/cc' folder from the source base directory
    (i.e. the cloned repository) into the destination directory.
    """
    src_cc = os.path.join(src_base, CC_SUBDIR)
    if not os.path.exists(src_cc):
        raise FileNotFoundError(
            f"Source folder '{src_cc}' not found in the repository."
        )

    for root, dirs, files in os.walk(src_cc):
        rel_path = os.path.relpath(root, src_cc)
        dst_dir = os.path.join(dst, rel_path)
        os.makedirs(dst_dir, exist_ok=True)
        for f in files:
            src_file_path = os.path.join(root, f)
            dst_file_path = os.path.join(dst_dir, f)
            shutil.copy2(src_file_path, dst_file_path)


def process_fedlex_files(directory: str):
    """
    Process files in the fedlex_files directory:
      - Replace "fedlex-data-admin-ch-eli-cc" with "fedlex-cc".
      - Remove the "-html" suffix before the file extension.
      - Only keep files whose base name (without extension) ends with "-de".
    """
    for filename in os.listdir(directory):
        src_path = os.path.join(directory, filename)
        if not os.path.isfile(src_path):
            continue  # Skip directories, if any.

        # Step 1: Replace prefix.
        new_name = filename.replace("fedlex-data-admin-ch-eli-cc", "fedlex-cc", 1)

        # Step 2: Remove the "-html" suffix before the extension.
        base, ext = os.path.splitext(new_name)
        if base.endswith("-html"):
            base = base[: -len("-html")]
        new_name = base + ext

        # Step 3: Only keep files that end with "-de" (in the base name).
        # Check the base name (without extension) for ending with "-de".
        if not base.endswith("-de"):
            # Remove file if it does not end with "-de"
            os.remove(src_path)
            continue

        # Rename the file if needed.
        dst_path = os.path.join(directory, new_name)
        if src_path != dst_path:
            # If the destination already exists, remove it first.
            if os.path.exists(dst_path):
                os.remove(dst_path)
            os.rename(src_path, dst_path)


def scrape_collection_fedlex():
    """
    Main function to orchestrate Fedlex data & file scraping and processing.
    """
    # Step 1: Prepare dir
    remove_dir_contents(FEDLEX_FILES_DIR)

    # Step 4: Clone the Fedlex-assets repository and copy the 'eli/cc' folder to FEDLEX_FILES_DIR
    clone_repo(FEDLEX_ASSETS_REPO_URL, TEMP_FEDLEX_ASSETS_DIR)
    copy_cc_folder(TEMP_FEDLEX_ASSETS_DIR, FEDLEX_FILES_DIR)
    shutil.rmtree(TEMP_FEDLEX_ASSETS_DIR)  # Cleanup the temporary directory

    # Step 5: Flatten the content in FEDLEX_FILES_DIR
    flatten_directory(FEDLEX_FILES_DIR)

    # Step 6: Process the files in FEDLEX_FILES_DIR according to the rules.
    process_fedlex_files(FEDLEX_FILES_DIR)

    print(
        "Fedlex data and files have been successfully scraped, flattened, and processed."
    )


if __name__ == "__main__":
    scrape_collection_fedlex()
