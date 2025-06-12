import os
import spacy
from spacy.pipeline import EntityRuler
import json
from spacy import displacy

from people import extract_people_from_chunk


# === CONFIG ===
INPUT_DIR = "RAW_TXT"
OUTPUT_DIR = "json_exports"

# === Custom Entity Patterns ===
PRIMARY_PATTERNS = [
    {"label": "SUM", "pattern": [{"TEXT": "Sumário"}, {"TEXT": ":", "OP": "!"}]},
    {"label": "SUM:", "pattern": [{"TEXT": "Sumário"}]},
    # ⬇️  Replace the old DES block with this pattern
    # --- replace the old “DES” block with this ---
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
}



,
    

]

COMPOSED_PATTERNS = [
    {
    "label": "SEC_DES_SUM",
    "pattern": [
        {"IS_UPPER": True, "OP": "+"},
        {"IS_SPACE": True, "OP": "*"},
        {"IS_UPPER": True, "OP": "+"},
        {"IS_SPACE": True, "OP": "*"},
        {"LOWER": {"IN": ["despacho", "aviso"]}},
        {"IS_SPACE": True, "OP": "*"},
        {"TEXT": "n.º", "OP": "?"},
        {"IS_SPACE": True, "OP": "*"},
        {"LIKE_NUM": True},
        {"IS_SPACE": True, "OP": "*"},
        {"TEXT": "Sumário"},
        {"TEXT": ":", "OP": "?"}
    ]
},


]


# === Helper Functions ===



def extract_text_between_labels(doc, start_label: str, end_label: str) -> str | None:
    start, end = None, None
    for ent in doc.ents:
        if ent.label_ == start_label and start is None:
            start = ent.end
        elif ent.label_ == end_label and start is not None:
            end = ent.start
            break
    return doc[start:end].text.strip() if start is not None and end is not None else None

def group_by_despacho_with_metadata(extracted_doc) -> dict:
    result = {}
    current_secretaria = None

    des_ents = [ent for ent in extracted_doc.ents if ent.label_ == "DES"]
    secretaria_ents = [ent for ent in extracted_doc.ents if ent.label_ == "SECRETARIA"]
    all_ents = sorted(secretaria_ents + des_ents, key=lambda x: x.start)

    for i, ent in enumerate(all_ents):
        if ent.label_ == "SECRETARIA":
            current_secretaria = ent.text

        elif ent.label_ == "DES" and current_secretaria:
            start = ent.start
            end = all_ents[i + 1].start if i + 1 < len(all_ents) else len(extracted_doc)
            chunk = extracted_doc[start:end].text.replace(current_secretaria, "").strip()

            metadata = {
                "chunk":      chunk,
                "data":       "",
                "autor":      extract_people_from_chunk(chunk),
                "pessoas":    [],
                "serie":      "",
                "secretaria": current_secretaria,
                "PDF":        filename
            }

            # ← only add the first one per title
            key = ent.text.replace("\n", "")
            if key not in result:
                result[key] = [metadata]

    return result




def save_secretaria_dict_to_json(secretaria_dict, txt_filename, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    json_filename = os.path.splitext(txt_filename)[0] + ".json"
    json_path = os.path.join(output_dir, json_filename)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(secretaria_dict, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON saved to: {json_path}")

# === Setup NLP ===
nlp = spacy.load("pt_core_news_lg")


# Add composed/override patterns first
ruler_composed = nlp.add_pipe("entity_ruler", name="ruler_composed", before="ner")
ruler_composed.add_patterns(COMPOSED_PATTERNS)

# Add general/primary patterns second
ruler_primary = nlp.add_pipe("entity_ruler", name="ruler_primary", after="ruler_composed")
ruler_primary.add_patterns(PRIMARY_PATTERNS)


# === Process All TXT Files ===
for filename in os.listdir(INPUT_DIR):
    if not filename.endswith(".txt"):
        continue

    filepath = os.path.join(INPUT_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    doc = nlp(text)

    if not any(ent.label_ in {"SUM", "TEXTO", "DES", "HEADER_DATE", "SECRETARIA", "SEC_DES_SUM"} for ent in doc.ents):
        print(f"❌ No custom entities in: {filename}")
        continue

    extracted = extract_text_between_labels(doc, "SUM", "SEC_DES_SUM")
    if not extracted:
        print(f"⚠️ Could not extract between SUM and SEC_DES_SUM in: {filename}")
        continue

    extracted_doc = nlp(extracted)
    secretaria_dict = group_by_despacho_with_metadata(extracted_doc)


    save_secretaria_dict_to_json(secretaria_dict, filename, output_dir=OUTPUT_DIR)