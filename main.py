import json
from flask import Flask, request, Response, stream_with_context
import requests
import logging
import random

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

class QueryObject:
    def __init__(self, ip_address: str, id: int, query: str, results: dict):
        self.ip_address = ip_address  # IP Address as a string
        self.id = id                  # ID as an integer
        self.query = query            # query as a string
        self.results = results        # Results as a JSON-like dictionary
        
def create_query_object(ip_address: str, id: int, query: str, results: dict={}) -> QueryObject:
    id = id if id is not None else random.randint(1, 1000000)
    store_query_object(QueryObject(ip_address, id, query, results))
    return QueryObject(ip_address, id, query, results)

def store_query_object(query_object: QueryObject):
    # TODO: Implement storage in RAM
    logging.info(f"Storing query object: {query_object.__dict__}")

@app.route('/search/', methods=['GET'])
def search():
    query = request.args.get("query")
    if not query:
        logging.error("Missing 'query' parameter") # Debug
        return Response("Missing 'query' parameter", status=400)
    ip_address = request.remote_addr
    logging.info(f"Received search request for {query} from {ip_address}") # Debug
    # Valid request, create a QueryObject
    query_object = create_query_object(ip_address, None, query)
    # TODO: Implement API call to search for the query
    # TODO: Return the results in JSON format and the ID to the client
    
    # Dummy response
    data = {
        "id": query_object.id,
        "results": [
            {"title": "Result 1", "selectionID": "1"},
            {"title": "Result 2", "selectionID": "2"},
            {"title": "Result 3", "selectionID": "3"}
        ]
    }
    return Response(json.dumps(data), mimetype='application/json')


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, threaded=True)