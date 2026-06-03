import json

log_path = r"C:\Users\pc\.gemini\antigravity\brain\a1f70500-94ec-46f5-87e8-58b18c3b611b\.system_generated\logs\overview.txt"
with open(log_path, 'r', encoding='utf-8') as f:
    for line in f:
        if '"step_index":26' in line or '"step_index": 26' in line:
            data = json.loads(line)
            code = data['tool_calls'][0]['args']['CodeContent']
            print("Type of code:", type(code))
            print("Length of code:", len(code))
            print("Start of code:", repr(code[:100]))
            print("End of code:", repr(code[-100:]))
            
            # If code is double-encoded or has quotes
            # Let's see what it actually is.
            # In Python json.loads(line) parses the JSON object.
            # The value of 'CodeContent' should be a normal string if it was valid JSON.
            # Let's save it directly to main_raw.py
            with open(r"c:\Users\pc\Desktop\cnc\main_raw.py", "w", encoding="utf-8") as out:
                out.write(code)
            print("Wrote main_raw.py, size:", os.path.getsize(r"c:\Users\pc\Desktop\cnc\main_raw.py") if 'os' in globals() else "unknown")
            import os
            print("Actual size:", os.path.getsize(r"c:\Users\pc\Desktop\cnc\main_raw.py"))
            break
