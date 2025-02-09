#!/usr/bin/env python3
import os
import re


def delete_numeric_updated_files(root_dir):
    # This regex will match file names that end with '-<number>-updated.json'
    pattern = re.compile(r".*-(\d+)-updated\.json$")

    # Walk over all subdirectories starting at root_dir
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            if pattern.match(filename):
                print(f"Deleting file: {full_path}")
                try:
                    os.remove(full_path)
                except Exception as e:
                    print(f"Error deleting {full_path}: {e}")


if __name__ == "__main__":
    # Set the root directory to search.
    root_directory = "data/zhlex/zhlex_files"
    delete_numeric_updated_files(root_directory)
