import json
import os

log_path = r"C:\Users\pc\.gemini\antigravity\brain\a1f70500-94ec-46f5-87e8-58b18c3b611b\.system_generated\logs\overview.txt"
output_path = r"c:\Users\pc\Desktop\cnc\main_restored.py"

with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        if '"step_index":26' in line or '"step_index": 26' in line:
            data = json.loads(line)
            code = data['tool_calls'][0]['args']['CodeContent']
            if isinstance(code, str) and (code.startswith('"') or code.startswith('{') or code.startswith('[')):
                try:
                    code = json.loads(code)
                except Exception as e:
                    # If it fails, maybe it's just raw with escaped quotes or something. Let's try eval or ast.literal_eval or just strip and parse
                    if code.startswith('"') and code.endswith('"'):
                        # Wrap it in curly braces or try to load as json string
                        try:
                            code = json.loads(code)
                        except:
                            code = code[1:-1].replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
            
            with open(output_path, 'w', encoding='utf-8') as out:
                out.write(code)
            print("Successfully extracted code to:", output_path)
            break
