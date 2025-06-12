

import os
import spacy
from spacy.pipeline import EntityRuler
import json
from spacy import displacy


# === Configuration ===
input_directory = "RAW_TXT"
output_directory = "temporary_DATA"

# === Custom Entity Patterns ===
PRIMARY_PATTERNS = [
    {"label": "SUM", "pattern": [{"TEXT": "Sumário"}, {"TEXT": ":", "OP": "!"}]},
    {"label": "SUM:", "pattern": [{"TEXT": "Sumário"}]},
    {
    "label": "DES",
    "pattern": [
        {   # header must start the sentence / line
            "LOWER": {"IN": ["despacho", "aviso", "declaração", "edital", "deliberação"]}
        },
        {   # optional words between the header and “n.º”
            "LOWER": {"IN": ["conjunto", "de", "da", "do",
                             "retificação", "retificacao"]},
            "OP": "*"
        },
        {   # mandatory “n.º” (or “nº”)
            "TEXT": {"IN": ["n.º", "nº"]}
        },
        { "LIKE_NUM": True },          # e.g. 47, 128, 16
        #{ "TEXT": "/", "OP": "?" },    # optional slash
       # { "LIKE_NUM": True, "OP": "?" },# e.g. /2025
        { "IS_PUNCT": True, "OP": "!" }
    ]
},
     {
        "label": "HEADER_DATE_CORRESPONDENCIA",
        "pattern": [
            {"LIKE_NUM": True},
            {"IS_PUNCT": True, "TEXT": "-"},
            {"IS_ALPHA": True, "LENGTH": 1},
            {"IS_SPACE": True, "OP": "?"},
            {"LIKE_NUM": True},
            {"LOWER": "de"},
            {"LOWER": {"IN": [
                "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
            ]}},
            {"LOWER": "de"},
            {"LIKE_NUM": True},
            {"TEXT": {"REGEX": "^[\\n\\r]+$"}, "OP": "*"},  # newline token(s)
            {"LOWER": "número"},
            {"LIKE_NUM": True},
            {"TEXT": {"REGEX": "^[\\n\\r]+$"}, "OP": "*"},  # newline token(s)
            {"TEXT": {"REGEX": "^CORRESPONDÊNCIA$"}}
        ]
    },
    {
        "label": "HEADER_DATE_CORRESPONDENCIA",
        "pattern": [
            {"LIKE_NUM": True},
            {"LOWER": "de"},
            {"LOWER": {"IN": [
                "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
            ]}},
            {"LOWER": "de"},
            {"LIKE_NUM": True},
            {"IS_ALPHA": True, "LENGTH": 1},
            {"IS_PUNCT": True, "TEXT": "-"},
            {"LIKE_NUM": True},
            {"TEXT": {"REGEX": "^[\\n\\r]+$"}, "OP": "*"},  # newline token(s)
            {"LOWER": "número"},
            {"LIKE_NUM": True},
            {"TEXT": {"REGEX": "^[\\n\\r]+$"}, "OP": "*"},  # newline token(s)
            {"TEXT": {"REGEX": "^CORRESPONDÊNCIA$"}}

        ]
    },
    {
        "label": "HEADER_DATE",
        "pattern": [
            {"LIKE_NUM": True},
            {"IS_PUNCT": True, "TEXT": "-"},
            {"IS_ALPHA": True, "LENGTH": 1},
            {"IS_SPACE": True, "OP": "?"},
            {"LIKE_NUM": True},
            {"LOWER": "de"},
            {"LOWER": {"IN": [
                "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
            ]}},
            {"LOWER": "de"},
            {"LIKE_NUM": True},
            {"TEXT": {"REGEX": "^[\\n\\r]+$"}, "OP": "*"},  # newline token(s)
            {"LOWER": "número"},
            {"LIKE_NUM": True},
        ]
    },
    {
        "label": "HEADER_DATE",
        "pattern": [
            {"LIKE_NUM": True},
            {"LOWER": "de"},
            {"LOWER": {"IN": [
                "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
            ]}},
            {"LOWER": "de"},
            {"LIKE_NUM": True},
            {"IS_ALPHA": True, "LENGTH": 1},
            {"IS_PUNCT": True, "TEXT": "-"},
            {"LIKE_NUM": True},
            {"TEXT": {"REGEX": "^[\\n\\r]+$"}, "OP": "*"},  # newline token(s)
            {"LOWER": "número"},
            {"LIKE_NUM": True}

        ]
    },
   {
    "label": "SECRETARIA",
    "pattern": [
        {"TEXT": {"IN": ["PRESIDÊNCIA", "SECRETARIA"]}},       # anchor on SECRETARIA
        {"IS_UPPER": True, "OP": "+"}, 
         {"IS_PUNCT": True, "OP": "*"},
        {"TEXT": "\n", "OP": "?"},
         {"IS_PUNCT": True, "OP": "*"},
        {"IS_UPPER": True, "OP": "+"},
    ]
},
]




# === Setup NLP ===
nlp = spacy.load("pt_core_news_lg")

# Add general/primary patterns second
ruler_primary = nlp.add_pipe("entity_ruler", name="ruler_primary")
ruler_primary.add_patterns(PRIMARY_PATTERNS)




def truncate_after_ent(doc, label):
    """
    Truncate the text starting from the first token of the last entity with the given label.
    The entity itself will also be removed.
    """
    ents = [ent for ent in doc.ents if ent.label_ == label]
    if not ents:
        return doc.text
    last_ent = ents[-1]
    return doc[:last_ent.start].text

def remove_ent(doc, label):
    """
    Remove all entities with the given label from the document.
    Returns the cleaned text with those entities removed.
    """
    spans_to_remove = [ent for ent in doc.ents if ent.label_ == label]

    # Sort by start_char in reverse to avoid shifting offsets during deletion
    spans_to_remove = sorted(spans_to_remove, key=lambda x: x.start_char, reverse=True)

    text = doc.text
    for span in spans_to_remove:
        text = text[:span.start_char] + text[span.end_char:]

    return text




def truncate_before_second_des(doc, des_keys):
    """
    Find the first DES entity (ent.label_ == "DES" and ent.text in des_keys)
    that appears twice, and return the substring of the original text
    starting at that second occurrence. If no DES repeats, return the full text.
    """
    counts = {}
    for ent in doc.ents:
        if ent.label_ == "DES" and ent.text in des_keys:
            counts[ent.text] = counts.get(ent.text, 0) + 1
            if counts[ent.text] == 2:
                # use start_char to slice the original text
                return doc.text[ent.start_char:]
    return doc.text

from spacy.tokens import Span

def add_json_key_entity(doc, key, label="JSON_KEY"):
    """
    If `key` appears in doc.text, create a Span for it and
    append it to doc.ents under the given `label`.
    """
    if not key:
        return doc
    start_char = doc.text.find(key)
    if start_char == -1:
        return doc
    end_char = start_char + len(key)
    span = doc.char_span(start_char, end_char, label=label)
    if span is not None:
        doc.ents = list(doc.ents) + [span]
    return doc



def process_txt_and_truncate(input_dir: str,
                             json_dir: str = "json_exports",
                             output_dir: str = "temporary_DATA"):
    """
    For each .txt file in input_dir:
      1. Load the corresponding .json from json_dir and get its first top-level key.
      2. Read the .txt.
      3. Count how many times that key appears.
      4. If it appears at least twice, truncate the text before the second occurrence.
      5. Write the (possibly truncated) text to output_dir under the same filename.
      6. Print the filename, key, count, and whether truncation occurred.
    """
    os.makedirs(output_dir, exist_ok=True)

    for filename in sorted(os.listdir(input_dir)):
        if not filename.lower().endswith(".txt"):
            continue

        base = os.path.splitext(filename)[0]
        json_path = os.path.join(json_dir, base + ".json")

        # 1) Load first JSON key
        try:
            with open(json_path, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            key = next(iter(data.keys()))
        except (FileNotFoundError, StopIteration):
            key = None

        print(f"\n== {filename} ==")
        if not key:
            print("  (no JSON key found)")
            continue
        print(f"  JSON key: {key!r}")

        # 2) Read text
        txt_path = os.path.join(input_dir, filename)
        with open(txt_path, "r", encoding="utf-8") as tf:
            text = tf.read()

        # 3) Count occurrences
        count = text.count(key)
        print(f"  Occurrences: {count}")

        truncated = text
        truncated_flag = False

        # 4) Truncate before second occurrence if needed
        if count >= 2:
            first_pos = text.find(key)
            second_pos = text.find(key, first_pos + len(key))
            if second_pos != -1:
                truncated = text[second_pos:]
                truncated_flag = True

        # 5) Write out
        out_path = os.path.join(output_dir, filename)
        with open(out_path, "w", encoding="utf-8") as out_f:
            out_f.write(truncated)

        # 6) Report
        status = "truncated" if truncated_flag else "unchanged"
        print(f"  Action: {status} (written to {out_path})")



process_txt_and_truncate("RAW_TXT", json_dir="json_exports")