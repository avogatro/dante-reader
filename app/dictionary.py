import string
try:
    import simplemma
except ImportError:
    simplemma = None

from nltk.corpus import wordnet as wn

class DictionaryEngine:
    def __init__(self):
        # We assume 'wordnet' and 'omw-1.4' are downloaded by the system/user
        pass
        
    def lookup(self, word: str, source_lang: str = "it", target_lang: str = "Modern English") -> str | None:
        """Looks up a word and returns English definitions + target language translations formatted as HTML."""
        # Clean word (strip punctuation and whitespace)
        word = word.strip(string.punctuation + " \t\n\r").lower()
        if not word:
            return None
            
        # Map input languages to NLTK OMW 3-letter codes
        omw_map = {
            "it": "ita", "italian": "ita",
            "en": "eng", "modern english": "eng", "english": "eng",
            "es": "spa", "spanish": "spa",
            "fr": "fra", "french": "fra",
            "zh": "cmn", "simplified chinese": "cmn", "chinese": "cmn",
            "ja": "jpn", "japanese": "jpn"
        }
        
        omw_source = omw_map.get(source_lang[:2].lower() if source_lang else "", "ita")
        omw_target = omw_map.get(target_lang.lower(), "eng")
            
        def get_synsets(w):
            try:
                return wn.synsets(w, lang=omw_source)
            except Exception as e:
                print(f"[dictionary] Error looking up {w} in {omw_source}: {e}")
                return []
                
        synsets = get_synsets(word)
        
        # If exact match fails, use lightweight lemmatization heuristics
        if not synsets:
            candidates = []
            
            # 1. Use Simplemma for highly accurate multilingual lemmatization (verbs, plurals, adjectives)
            if simplemma:
                try:
                    # simplemma expects 2-letter ISO codes (e.g. 'it', 'en', 'fr')
                    iso_lang = source_lang[:2].lower() if source_lang else 'it'
                    lemma = simplemma.lemmatize(word, lang=iso_lang)
                    if lemma and lemma != word:
                        candidates.append(lemma)
                except Exception as e:
                    print(f"[dictionary] simplemma error: {e}")
            
            # 2. Poetic apocope (dropped last vowel, e.g. cammin -> cammino, dir -> dire)
            # This is specific to poetry/Dante where standard NLP models fail because it's not a real word.
            candidates.append(word + 'o')
            candidates.append(word + 'e')
            candidates.append(word + 'a')
            candidates.append(word + 'i')
            
            # Try candidates
            for cand in candidates:
                if len(cand) < 2: continue
                s = get_synsets(cand)
                if s:
                    synsets = s
                    word = cand  # Update the word to the base form so the tooltip header matches
                    break

        if not synsets:
            return None
            
        pos_map = {
            'n': 'Noun',
            'v': 'Verb',
            'a': 'Adjective',
            'r': 'Adverb',
            's': 'Adjective'
        }
        
        results = []
        for s in synsets:
            pos = pos_map.get(s.pos(), s.pos())
            definition = s.definition()
            
            # Fetch target language translated lemmas if requested and supported
            translations = ""
            if omw_target != "eng":
                try:
                    lemmas = s.lemma_names(lang=omw_target)
                    if lemmas:
                        # Replace underscores with spaces for readability
                        lemmas_str = ", ".join(lemmas).replace('_', ' ')
                        translations = f" <span style='color: #58a6ff;'>({lemmas_str})</span>"
                except Exception:
                    pass
            
            # Some synsets might share the exact same English definition but different nuance.
            results.append(f"<b>[{pos}]</b>{translations} {definition}")
            
        # Deduplicate and limit to top 5 definitions to keep the tooltip lightweight
        seen = set()
        unique_results = []
        for r in results:
            if r not in seen:
                seen.add(r)
                unique_results.append(r)
                if len(unique_results) >= 5:
                    break
                
        if not unique_results:
            return None
            
        # Wrap in a small container for QToolTip formatting
        header = f"<div style='margin-bottom: 4px; font-size: 14px;'><b>{word}</b></div>"
        body = "<br>".join(unique_results)
        
        return f"{header}<div style='font-size: 12px;'>{body}</div>"
