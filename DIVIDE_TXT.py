import os
import json
from pathlib import Path
import re


def list_json_keys(json_file: str) -> list:
    """
    Loads a single .json file and returns its top-level keys as a list.

    :param json_file: Path to the .json file.
    :return: List of top-level keys (or empty list if file unreadable).
    """
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {json_file}: {e}")
        return []
    return list(data.keys()) if isinstance(data, dict) else []


def pair_json_and_txt(json_dir: str, txt_dir: str) -> dict:
    """
    Finds .json files in `json_dir` and .txt files in `txt_dir` that share the same base filename.
    Returns a dict mapping each common base name to a tuple of (json_path, txt_path).

    :param json_dir: Path to directory containing .json files.
    :param txt_dir:  Path to directory containing .txt files.
    :return: Dict where keys are base filenames and values are (json_path, txt_path).
    """
    json_path = Path(json_dir)
    txt_path = Path(txt_dir)
    if not json_path.is_dir():
        raise ValueError(f"JSON directory not found: {json_dir}")
    if not txt_path.is_dir():
        raise ValueError(f"TXT directory not found: {txt_dir}")

    json_files = {p.stem: p for p in json_path.glob('*.json')}
    txt_files = {p.stem: p for p in txt_path.glob('*.txt')}
    common = set(json_files) & set(txt_files)
    return {stem: (json_files[stem], txt_files[stem]) for stem in sorted(common)}


def divide_txt_and_update_json(json_file: str, txt_file: str, root_output: str = 'DOC') -> None:
    """
    Splits the given .txt file into segments based on headers defined in the JSON metadata.
    Also updates the JSON file by adding a 'path' entry to each metadata dict pointing to its segment file.

    :param json_file: Path to the .json file containing header keys.
    :param txt_file:  Path to the .txt file to split.
    :param root_output: Root directory under which per-file subdirectories will be created.
    """
    json_path = Path(json_file)
    txt_path = Path(txt_file)
    if not json_path.is_file():
        raise ValueError(f"JSON file not found: {json_file}")
    if not txt_path.is_file():
        raise ValueError(f"TXT file not found: {txt_file}")

    # Load JSON metadata and extract keys
    try:
        data = json.loads(json_path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"Error reading JSON {json_file}: {e}")
        return
    keys = list(data.keys())
    if not keys:
        print(f"No keys found in JSON {json_file}")
        return

    content = txt_path.read_text(encoding='utf-8')
    # Build regex to match any key
    escaped = [re.escape(k) for k in keys]
    pattern = re.compile(r'(?m)^(' + '|'.join(escaped) + r')')
    matches = list(pattern.finditer(content))
    if not matches:
        print(f"No headers found in {txt_path.name}")
        return

    # Prepare output directories
    root_dir = Path(root_output)
    root_dir.mkdir(exist_ok=True)
    file_dir = root_dir / txt_path.stem
    file_dir.mkdir(exist_ok=True)

    # Process each segment
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        segment = content[start:end].strip()
        if not segment:
            continue
        header = match.group(1)
        # Sanitize for filename
        fname = re.sub(r'[\\/:*?"<>| ]', '_', header)
        segment_path = file_dir / f"{fname}.txt"
        segment_path.write_text(segment, encoding='utf-8')

        # Update JSON entries for this header
        for entry in data.get(header, []):
            entry['path'] = str(segment_path)
        print(f"Created segment '{segment_path.name}' and updated JSON for header '{header}'")

    # Write back updated JSON
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Updated JSON file with paths: {json_file}")

# Example overall process:
pairs = pair_json_and_txt('json_exports', 'temporary_DATA')
for stem, (jpath, tpath) in pairs.items():
    divide_txt_and_update_json(str(jpath), str(tpath))
