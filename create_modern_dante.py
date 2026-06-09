import json
import zipfile
import os

with open("e-book/dante/modern_test.json", "r", encoding="utf-8") as f:
    data = json.load(f)

output_file = "e-book/modern_inferno.dante"

with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("content.json", json.dumps(data, indent=2, ensure_ascii=False))

print(f"Created {output_file} successfully!")
