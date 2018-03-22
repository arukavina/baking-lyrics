class Band:
    """Class for band definition"""
    def __init__(self):
        self.name = ""
        self.decades = []

    def set_data(self, band_data):
        self.name = band_data["name"]
        self.decades = band_data["decades"]





