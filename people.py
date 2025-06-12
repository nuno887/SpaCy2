import spacy
import re
# Load the spaCy model
nlp = spacy.load("pt_core_news_lg")

TRIM_KEYWORDS = ["anexo", "nota curricular", "secretaria"]

UNWANTED_WORDS = [
    "formação", "profissional", "infraestruturas", "despacho", "conjunto", "madeira",
    "câmara", "chefe", "estudos", "coordenação", "autoridade", "assuntos",
    "fiscais", "regional", "secretária", "&", "diretor", "diretora",
    "habilitações", "literárias", "professor", "professora", "convidado", "convidada",
    "sistemas", "informação", "tecnologias", "especialista", "recursos", "humanos",
    "apoio", "família", "idosa", "idoso", "assistente",
    "vogal", "conselho", "diretivo", "bilhete", "identidade", "inspetora", "tributária",
    "tributário", "secundária", "bolseiro", "bolseira", "investigador", "investigadora"
]

# Lista de títulos que podem anteceder nomes próprios
NAME_TITLES = [
    # Acadêmicos e Profissionais
    "Licenciado", "Licenciada",
    "Doutor", "Doutora",
    "Mestre", "Mestra",
    "Mestrando", "Mestranda",
    "Doutorando", "Doutoranda",
    "Pós-Doutor", "Pós-Doutora",
]

def fallback_regex_name_extraction(text: str, known_entities: list[str]) -> list[str]:
    pattern = r"\b(" + "|".join(NAME_TITLES) + r")\s+([A-ZÁÉÍÓÚÂÊÔÃÕÀÇ][\w\-']+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÀÇ][\w\-']+)+)"
    matches = re.findall(pattern, text)
    new_names = [" ".join(match) for match in matches]
    # Remove duplicatas e nomes já encontrados
    return [name for name in new_names if name not in known_entities]

def remove_single_word_entities(entities):
    return [e for e in entities if len(e.split()) > 1]

def trim_after_keywords(text, keywords):
    text_lower = text.lower()
    cut_index = len(text)
    for kw in keywords:
        index = text_lower.find(kw.lower())
        if index != -1 and index < cut_index:
            cut_index = index
    return text[:cut_index].strip()

def normalize_and_deduplicate(entities):
    normalized = [" ".join(e.split()) for e in entities]
    return sorted(set(normalized), key=len)

def keep_shortest_prefix_entities(entities):
    sorted_entities = sorted(set(entities), key=lambda x: (len(x.split()), x))
    result = []
    for ent in sorted_entities:
        ent_tokens = ent.split()
        is_extension = False
        for kept in result:
            kept_tokens = kept.split()
            if ent_tokens[:len(kept_tokens)] == kept_tokens:
                is_extension = True
                break
        if not is_extension:
            result.append(ent)
    return result

def remove_entities_with_unwanted_words(entities, unwanted_words):
    unwanted_words_lower = [w.lower() for w in unwanted_words]
    filtered = []
    for ent in entities:
        ent_words = ent.lower().split()
        if not any(word in ent_words for word in unwanted_words_lower):
            filtered.append(ent)
    return filtered

def remove_titles_from_entities(entities, titles):
    titles_lower = [t.lower() for t in titles]
    cleaned = []
    for ent in entities:
        ent_words = ent.strip().split()
        # Se o primeiro termo for um título, remove
        if ent_words and ent_words[0].lower().rstrip('.') in titles_lower:
            cleaned.append(" ".join(ent_words[1:]))
        else:
            cleaned.append(ent)
    return cleaned

# ✅ MAIN FUNCTION: extract from chunk
def extract_people_from_chunk(text: str) -> list[str]:
    doc = nlp(text)
    person_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "PER"]

    person_entities = remove_single_word_entities(person_entities)
    person_entities = [trim_after_keywords(p, TRIM_KEYWORDS) for p in person_entities]
    person_entities = keep_shortest_prefix_entities(person_entities)
    person_entities = normalize_and_deduplicate(person_entities)
    person_entities = remove_entities_with_unwanted_words(person_entities, UNWANTED_WORDS)

         # Se spaCy falhar, tenta regex
    if not person_entities:
        person_entities = fallback_regex_name_extraction(text, [])
    
    person_entities = remove_titles_from_entities(person_entities, NAME_TITLES)

        
    return person_entities


"""
text01 = "Despacho n.º 464/2025\nNomeia a licenciada em Direito, Anabela de Sousa Reis Varela, Técnica Superior do\nSistema Centralizado de Gestão de Recursos Humanos da Secretaria Regional de\nEducação, Ciência e Tecnologia, afeta à Direção Regional de Planeamento,\nRecursos e Infraestruturas, no cargo de Técnica Especialista do Gabinete do\nSecretário Regional da Economia."
text02 = "Aviso n.º 139/2025\nAutoriza a renovação da comissão de serviço da Licenciada Ana Cristina Fernandes\nEscórcio, como Chefe de Divisão do Gabinete de Conferência e Conformidade,\ncargo de direção intermédia de 2.º grau, do Instituto de Administração da Saúde."

print("text01")
print(extract_people_from_chunk(text01))
print("text02")
print(extract_people_from_chunk(text02))

"""