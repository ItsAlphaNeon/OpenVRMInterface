import json

class QueryObject:
    def __init__(self, ip_address: str, id: int, query: str, results: dict):
        self.ip_address = ip_address  # IP Address as a string
        self.id = id                  # ID as an integer
        self.query = query            # query as a string
        self.results = results        # Results as a JSON-like dictionary

if __name__ == "__main__":
    pass