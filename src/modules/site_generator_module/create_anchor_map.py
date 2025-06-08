# src/modules/site_generator_module/create_anchor_map.py
import os
import json
import re
from bs4 import BeautifulSoup
from tqdm import tqdm


def create_anchor_map(public_dir):
    """
    Scans generated HTML files to create a JSON map of all laws,
    their versions, and available anchor IDs.
    """
    print("Building anchor map...")
    anchor_map = {}
    law_dirs = ["col-zh", "col-ch"]

    for law_dir_name in law_dirs:
        collection_path = os.path.join(public_dir, law_dir_name)
        if not os.path.isdir(collection_path):
            continue

        # Group files by ordnungsnummer
        law_files = {}
        for filename in os.listdir(collection_path):
            if filename.endswith(".html"):
                match = re.match(r"([\d\.]+)-(\d+)\.html", filename)
                if match:
                    ordnungsnummer, nachtragsnummer = match.groups()
                    if ordnungsnummer not in law_files:
                        law_files[ordnungsnummer] = []
                    law_files[ordnungsnummer].append(
                        {
                            "nachtragsnummer": nachtragsnummer,
                            "path": os.path.join(collection_path, filename),
                        }
                    )

        # Process each law
        for ordnungsnummer, versions in tqdm(
            law_files.items(), desc=f"Mapping {law_dir_name} anchors"
        ):
            anchor_map[ordnungsnummer] = {"newest": "0", "anchors": {}}

            # Find the newest version
            if versions:
                newest_version = max(versions, key=lambda v: int(v["nachtragsnummer"]))
                anchor_map[ordnungsnummer]["newest"] = newest_version["nachtragsnummer"]

            # Extract anchors for each version
            for version in versions:
                nachtragsnummer = version["nachtragsnummer"]
                try:
                    with open(version["path"], "r", encoding="utf-8") as f:
                        soup = BeautifulSoup(f, "html.parser")

                    # Find all IDs from provision and subprovision containers
                    anchor_ids = set()
                    for container_class in [
                        "provision-container",
                        "subprovision-container",
                    ]:
                        for container in soup.find_all("div", class_=container_class):
                            # Find the anchor target within the container
                            p_tag = container.find("p", {"id": True})
                            if p_tag:
                                anchor_ids.add(f"#{p_tag['id']}")

                    anchor_map[ordnungsnummer]["anchors"][nachtragsnummer] = sorted(
                        list(anchor_ids)
                    )
                except Exception as e:
                    print(f"  Warning: Could not process {version['path']}: {e}")

    # Write the map to a file
    output_path = os.path.join(public_dir, "anchor_map.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(anchor_map, f)

    print(f"Anchor map successfully created at {output_path}")


if __name__ == "__main__":
    # Example usage
    public_dir = "public"
    create_anchor_map(public_dir)
