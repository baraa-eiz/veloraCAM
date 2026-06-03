import os
import json

class SettingsManager:
    """
    Persistent application settings manager for Velora CNC.
    Saves user preferences (theme, units, default post-processor, defaults) to a JSON file.
    """
    def __init__(self, settings_path=None):
        if settings_path is None:
            # Save in user's home directory under .veloracnc
            home = os.path.expanduser("~")
            self.dir_path = os.path.join(home, ".veloracnc")
            self.settings_path = os.path.join(self.dir_path, "settings.json")
        else:
            self.settings_path = settings_path
            self.dir_path = os.path.dirname(settings_path)
            
        self.settings = {
            "theme": "Industrial Dark",
            "units": "mm",
            "default_post_processor": "Mach3",
            "default_machine": "Generic Stone Router",
            "default_material": "Soft Wood",
            "default_export_mode": "Single File",
            "autosave_enabled": True,
            "autosave_interval_mins": 5,
            "recent_projects": []
        }
        self.load()

    def load(self):
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings.update(data)
        except Exception:
            # Silent fallback to defaults if reading settings fails
            pass

    def save(self):
        try:
            os.makedirs(self.dir_path, exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception:
            pass

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()

    def add_recent_project(self, path):
        recent = self.settings.get("recent_projects", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        self.settings["recent_projects"] = recent[:10]  # Keep last 10
        self.save()
