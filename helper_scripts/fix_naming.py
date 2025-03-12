import os
import re


def rename_files(root_dir):
    # Regex pattern to identify an 8-digit number surrounded by dashes
    pattern = re.compile(r"-(\d{8})-")

    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            new_filename = re.sub(pattern, "-", filename)
            if new_filename != filename:
                old_file_path = os.path.join(dirpath, filename)
                new_file_path = os.path.join(dirpath, new_filename)
                os.rename(old_file_path, new_file_path)
                print(f"Renamed '{old_file_path}' to '{new_file_path}'")


# Specify the path to the root directory where your folders are located
root_directory = "data/zhlex/zhlex_files"
rename_files(root_directory)
