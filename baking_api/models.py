

class Band:
    """Class for band definition"""
    def __init__(self):
        self.name = ""
        self.decades = []

    def set_data(self, band_data):
        self.name = band_data["name"]
        for i in band_data["decades"]:
            self.decades.append(i)

    def serialize(self):
        # creating decades dictionary

        return {
            'band': {
                'name': self.name,
                'decades': [
                    self.decades
                ]
            }
        }




