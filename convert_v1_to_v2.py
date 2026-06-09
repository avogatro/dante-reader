import json
import sys
import os

def convert_to_v2(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    v2_data = {
        "metadata": {
            "tracks": {
                "text": {"label": "Italian (Original)", "type": "text"},
                "ipa": {"label": "IPA Phonetics", "type": "text"},
                "longfellow": {"label": "English (Longfellow)", "type": "text"}
            }
        },
        "footnotes": {},
        "images": {},
        "audio_clips": {},
        "videos": {},
        "books": []
    }
    
    for book in data.get("books", []):
        v2_book = {
            "title": book.get("title", ""),
            "cantos": []
        }
        
        for canto in book.get("cantos", []):
            v2_canto = {
                "canto_number": canto.get("canto_number", 0),
                "blocks": []
            }
            
            canto_num = v2_canto["canto_number"]
            
            for b_idx, block in enumerate(canto.get("blocks", [])):
                block_id = f"c{canto_num}-b{b_idx+1}"
                v2_block = {
                    "id": block_id,
                    "tracks": {
                        "text": [],
                        "ipa": [],
                        "longfellow": []
                    }
                }
                
                for line in block:
                    if "text" in line:
                        v2_block["tracks"]["text"].append(line["text"])
                    if "ipa" in line:
                        v2_block["tracks"]["ipa"].append(line["ipa"])
                    if "longfellow" in line:
                        v2_block["tracks"]["longfellow"].append(line["longfellow"])
                        
                v2_canto["blocks"].append(v2_block)
                
            v2_book["cantos"].append(v2_canto)
            
        v2_data["books"].append(v2_book)
        
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(v2_data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully converted {input_path} to V2 schema at {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_v1_to_v2.py <input.json> <output.json>")
        sys.exit(1)
    convert_to_v2(sys.argv[1], sys.argv[2])
