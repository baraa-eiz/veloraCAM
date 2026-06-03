class MaterialLibrary:
    """
    Manages physical material preset values for Velora CNC.
    Preloads target operational speed/feed suggestions without locking user configuration.
    """
    def __init__(self):
        self.materials = {
            "Soft Stone": {
                "feed_rate_suggest": 2500.0,
                "plunge_rate_suggest": 600.0,
                "spindle_rpm_suggest": 18000,
                "stepdown_factor": 0.3,     # 30% of tool diameter per pass max
                "stepover_factor": 0.4,     # 40% stepover
                "rough_allowance": 1.0,     # mm
                "safety_multiplier": 0.8,   # Conservative scale
                "finishing_strategy": "Scallop Raster",
                "notes": "Marble, Limestone, Sandstone. Requires constant coolant."
            },
            "Hard Stone": {
                "feed_rate_suggest": 1200.0,
                "plunge_rate_suggest": 300.0,
                "spindle_rpm_suggest": 14000,
                "stepdown_factor": 0.15,
                "stepover_factor": 0.3,
                "rough_allowance": 1.5,
                "safety_multiplier": 0.5,
                "finishing_strategy": "Cross Scallop Raster",
                "notes": "Granite, Basalt. Extremely slow passes, diamond tool mandatory."
            },
            "Soft Wood": {
                "feed_rate_suggest": 4500.0,
                "plunge_rate_suggest": 1500.0,
                "spindle_rpm_suggest": 22000,
                "stepdown_factor": 1.0,      # 100% tool diameter stepdown
                "stepover_factor": 0.5,
                "rough_allowance": 0.5,
                "safety_multiplier": 1.2,
                "finishing_strategy": "Raster Fast",
                "notes": "Pine, Cedar, Fir. High speed, chip clearing critical."
            },
            "Hard Wood": {
                "feed_rate_suggest": 3500.0,
                "plunge_rate_suggest": 1000.0,
                "spindle_rpm_suggest": 20000,
                "stepdown_factor": 0.6,
                "stepover_factor": 0.4,
                "rough_allowance": 0.8,
                "safety_multiplier": 1.0,
                "finishing_strategy": "Raster Balanced",
                "notes": "Oak, Beech, Walnut, Maple. High density, sharp cutters mandatory."
            },
            "MDF": {
                "feed_rate_suggest": 5000.0,
                "plunge_rate_suggest": 1800.0,
                "spindle_rpm_suggest": 24000,
                "stepdown_factor": 1.2,
                "stepover_factor": 0.5,
                "rough_allowance": 0.3,
                "safety_multiplier": 1.3,
                "finishing_strategy": "Raster Fast",
                "notes": "Medium Density Fiberboard. Generates heavy dust, fast feeds prevent burns."
            },
            "Acrylic": {
                "feed_rate_suggest": 3000.0,
                "plunge_rate_suggest": 800.0,
                "spindle_rpm_suggest": 18000,
                "stepdown_factor": 0.5,
                "stepover_factor": 0.4,
                "rough_allowance": 0.5,
                "safety_multiplier": 0.9,
                "finishing_strategy": "Raster Clean",
                "notes": "PMMA, Plexiglass. Single flute bit recommended to prevent melting."
            },
            "ACP / Alucobond": {
                "feed_rate_suggest": 4000.0,
                "plunge_rate_suggest": 1200.0,
                "spindle_rpm_suggest": 22000,
                "stepdown_factor": 1.0,
                "stepover_factor": 0.5,
                "rough_allowance": 0.0,
                "safety_multiplier": 1.1,
                "finishing_strategy": "Contour Bending",
                "notes": "Aluminum Composite Panel. Fast routing of folding grooves."
            },
            "Foam": {
                "feed_rate_suggest": 6000.0,
                "plunge_rate_suggest": 2500.0,
                "spindle_rpm_suggest": 24000,
                "stepdown_factor": 2.0,
                "stepover_factor": 0.6,
                "rough_allowance": 0.2,
                "safety_multiplier": 2.0,
                "finishing_strategy": "Raster Aggressive",
                "notes": "EPS, Polyurethane tooling board. High feeds, zero stress."
            }
        }

    def get_material(self, name):
        return self.materials.get(name, self.materials["Soft Wood"])

    def get_all_names(self):
        return list(self.materials.keys())
