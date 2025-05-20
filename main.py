import json
from flask import Flask, request, Response, stream_with_context
import requests
import logging
from typing import Optional
import random
import dotenv
import os

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# .env file variables
dotenv.load_dotenv()
THEMOVIEDB_API_KEY = os.getenv("THEMOVIEDB_API_KEY")
env_endpoint = os.getenv("VRM_ENDPOINT")
if env_endpoint is not None:
    VRM_ENDPOINT = 'https://' + env_endpoint
else:
    VRM_ENDPOINT = None
if not THEMOVIEDB_API_KEY or not VRM_ENDPOINT:
    logging.error("Missing environment variables: THEMOVIEDB_API_KEY or VRM_ENDPOINT")
    exit(1)

# In-memory storage for query objects, Long-term storage isn't necessary
query_object_storage = []


class QueryObject:
    def __init__(self, ip_address: str, id: int, query: str, results: dict):
        self.ip_address = ip_address  # IP Address as a string
        self.id = id  # ID as an integer
        self.query = query  # query as a string
        self.results = results  # Results as a JSON-like dictionary

    def __repr__(self):
        return f"<QueryObject id={self.id} ip={self.ip_address} query={self.query}>"


def create_query_object(
    ip_address: str, id: Optional[int], query: str, results: Optional[dict] = None
) -> QueryObject:
    if results is None:
        results = {}
    id = id if id is not None else random.randint(1, 1000000)
    obj = QueryObject(ip_address, id, query, results)
    store_query_object(obj)
    return obj


def store_query_object(query_object: QueryObject):
    logging.info(f"Storing query object: {query_object.__dict__}")
    # Store the query object in the in-memory storage
    query_object_storage.append(query_object)


def retrieve_query_object(id: int) -> Optional[QueryObject]:
    # Retrieve the query object from the in-memory storage
    for obj in query_object_storage:
        if obj.id == id:
            return obj
    return None


@app.route("/submit/", methods=["GET"])
def submit():
    id_param = request.args.get("id")
    if id_param is None:
        logging.error("Missing 'id' parameter")
        return Response("Missing 'id' parameter", status=400)
    try:
        id_int = int(id_param)
    except ValueError:
        logging.error("Invalid 'id' parameter")
        return Response("Invalid 'id' parameter", status=400)
    selection_id = request.args.get("selection")
    if not selection_id:
        logging.error("Missing 'selection' parameter")
        return Response("Missing 'selection' parameter", status=400)
    # Valid request, start m3u8 retrieval
    query_object = retrieve_query_object(id_int)
    if not query_object:
        logging.error(f"Query object with ID {id_int} not found")
        return Response(f"Query object with ID {id_int} not found", status=404)
    try:
        # Defensive: ensure VRM_ENDPOINT is not None
        vrm_endpoint = VRM_ENDPOINT or "https://vr-m.net/"
        vrm_endpoint = vrm_endpoint.rstrip('/')
        # Step 1: Get lock_id from VRM /0/l/{selection_id}
        lock_url = f"{vrm_endpoint}/0/l/{selection_id}"
        lock_resp = requests.get(lock_url, verify=False)
        if lock_resp.status_code != 200:
            logging.error(f"Failed to get lock_id from VRM: {lock_resp.status_code}")
            return Response("Failed to get lock_id from VRM", status=502)
        import base64
        decoded = base64.b64decode(lock_resp.text)
        try:
            lock_data = json.loads(decoded)
            lock_id = lock_data.get("lock_id")
        except Exception as e:
            logging.error(f"Failed to parse lock_id JSON: {e}")
            return Response("Failed to parse lock_id JSON", status=502)
        if not lock_id:
            logging.error("lock_id not found in VRM response")
            return Response("lock_id not found in VRM response", status=502)
        # Step 2: Get m3u8 file from VRM /p/{lock_id}.m3u8
        m3u8_url = f"{vrm_endpoint}/p/{lock_id}.m3u8"
        m3u8_resp = requests.get(m3u8_url, verify=False)
        if m3u8_resp.status_code != 200:
            logging.error(f"Failed to get m3u8 from VRM: {m3u8_resp.status_code}")
            return Response("Failed to get m3u8 from VRM", status=502)
        # Optionally, store m3u8 in QueryObject
        query_object.results['m3u8'] = m3u8_resp.text
        return Response(m3u8_resp.text, mimetype="application/vnd.apple.mpegurl")
    except Exception as e:
        logging.error(f"Error during VRM m3u8 retrieval: {e}")
        return Response("Internal server error during m3u8 retrieval", status=500)


@app.route("/search/", methods=["GET"])
def search():
    query = request.args.get("query")
    if not query:
        logging.error("Missing 'query' parameter")  # Debug
        return Response("Missing 'query' parameter", status=400)
    ip_address = request.remote_addr
    logging.info(f"Received search request for {query} from {ip_address}")  # Debug
    # Valid request, create a QueryObject
    query_object = create_query_object(str(ip_address), None, query)
    try:
        vrm_endpoint = VRM_ENDPOINT or "https://vr-m.net/"
        vrm_endpoint = vrm_endpoint.rstrip('/')
        import base64
        from urllib.parse import quote_plus
        # Step 1: Call VRM search API
        encoded_query = quote_plus(query)
        search_url = f"{vrm_endpoint}/0/s?q={encoded_query}"
        resp = requests.get(search_url, verify=False)
        if resp.status_code != 200:
            logging.error(f"Failed to search VRM: {resp.status_code}")
            return Response("Failed to search VRM", status=502)
        decoded = base64.b64decode(resp.text)
        try:
            results_json = json.loads(decoded)
        except Exception as e:
            logging.error(f"Failed to parse VRM search JSON: {e}")
            return Response("Failed to parse VRM search JSON", status=502)
        # Step 2: Extract results (assuming a list of movies with title and id)
        results = []
        for item in results_json.get('results', []):
            title = item.get('title') or item.get('name') or str(item)
            selection_id = item.get('id') or item.get('selectionID') or str(item)
            results.append({"title": title, "selectionID": selection_id})
        # Store results in QueryObject
        query_object.results['results'] = results
        data = {
            "id": query_object.id,
            "results": results,
        }
        return Response(json.dumps(data), mimetype="application/json")
    except Exception as e:
        logging.error(f"Error during VRM search: {e}")
        return Response("Internal server error during search", status=500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
