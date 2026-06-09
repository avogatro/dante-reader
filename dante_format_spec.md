# `.dante` Archive Format Specification

The `.dante` format is a specialized, multi-track e-book container optimized for comparative reading. It packages original text, translations, and pronunciations into a single easily distributable file.

## 🗂️ Archive Structure

A `.dante` file is technically a standard **ZIP archive** with its extension changed from `.zip` to `.dante`.

If you were to unzip a `.dante` file, you would typically see the following structure:

```text
book_name.dante/
│
├── content.json       # Core text and translation data
└── cover.jpg          # (Optional) Cover image for the book
```

- **`content.json`**: This is the heart of the format. It contains the entire book hierarchy (Books > Cantos > Blocks > Lines) serialized into a single JSON file.
- **`cover.jpg`**: An optional image file that the reader can extract and display in the UI.

---

## 📄 JSON Schema (`content.json`)

The data inside `content.json` strictly follows a hierarchical schema to maintain synchronization between the original Italian verse, its English translation, and its phonetic (IPA) pronunciation.

### Complete Schema Definition

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Dante Book Content",
  "description": "Multi-track data structure for a Dante book",
  "type": "object",
  "required": ["books"],
  "properties": {
    "books": {
      "type": "array",
      "description": "A list of books/volumes (e.g., Inferno, Purgatorio, Paradiso)",
      "items": {
        "type": "object",
        "required": ["title", "cantos"],
        "properties": {
          "title": {
            "type": "string",
            "description": "The title of the book (e.g., 'Inferno')"
          },
          "cantos": {
            "type": "array",
            "description": "The chapters (cantos) within the book",
            "items": {
              "type": "object",
              "required": ["canto_number", "blocks"],
              "properties": {
                "canto_number": {
                  "type": "integer",
                  "description": "The sequential number of the canto"
                },
                "blocks": {
                  "type": "array",
                  "description": "A list of stanzas (tercet blocks) in the canto",
                  "items": {
                    "type": "array",
                    "description": "A list of lines making up a single stanza",
                    "items": {
                      "type": "object",
                      "description": "A single line containing multiple translation tracks",
                      "properties": {
                        "text": {
                          "type": "string",
                          "description": "The original Italian text"
                        },
                        "longfellow": {
                          "type": "string",
                          "description": "The English translation by Longfellow"
                        },
                        "ipa": {
                          "type": "string",
                          "description": "The International Phonetic Alphabet pronunciation"
                        }
                      },
                      "required": ["text"]
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## 📝 Example `content.json` Payload

Below is a minimized example demonstrating the structure for the opening lines of *Inferno*, Canto 1:

```json
{
  "books": [
    {
      "title": "Inferno",
      "cantos": [
        {
          "canto_number": 1,
          "blocks": [
            [
              {
                "text": "Nel mezzo del cammin di nostra vita",
                "longfellow": "Midway upon the journey of our life",
                "ipa": "nel met͡so del kamːin di nostra vita"
              },
              {
                "text": "mi ritrovai per una selva oscura,",
                "longfellow": "I found myself within a forest dark,",
                "ipa": "mi ritrovai per una selva oʃura,"
              },
              {
                "text": "ché la diritta via era smarrita.",
                "longfellow": "For the straightforward pathway had been lost.",
                "ipa": "ke la diritːa via era zmarːita."
              }
            ]
          ]
        }
      ]
    }
  ]
}
```

### Breakdown of the Data Flow
1. **Books Array**: Top level array wrapping major sections.
2. **Cantos Array**: Organizes the book into chapters.
3. **Blocks Array**: Within a canto, the poem is broken down into stanzas (blocks). In the *Divine Comedy*, Dante uses *terza rima*, so these blocks typically consist of arrays containing 3 lines (tercets).
4. **Line Objects**: Each line object holds the different "tracks". `text` is the Italian anchor, `longfellow` holds the English equivalent, and `ipa` holds the phonetic spelling. The UI maps these to distinct columns for side-by-side reading.
