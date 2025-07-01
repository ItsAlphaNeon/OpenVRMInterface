import json
from flask import Flask, request, Response, stream_with_context
import requests
import logging
from typing import Optional
import random
import dotenv
import os
import traceback

app = Flask(__name__, static_folder='static')
logging.basicConfig(level=logging.INFO)

# .env file variables
dotenv.load_dotenv()
THEMOVIEDB_API_KEY = os.getenv("THEMOVIEDB_API_KEY")
env_endpoint = os.getenv("VRM_ENDPOINT")
HOST = os.getenv("HOST")
if not HOST:
    HOST = "http://localhost:8080"
if env_endpoint is not None:
    VRM_ENDPOINT = 'https://' + env_endpoint
else:
    VRM_ENDPOINT = None
if not THEMOVIEDB_API_KEY or not VRM_ENDPOINT:
    logging.error("Missing environment variables: THEMOVIEDB_API_KEY or VRM_ENDPOINT")
    exit(1)

# In-memory storage for query objects
query_object_storage = []

# Query object is the main data structure for storing search queries and results
class QueryObject:
    def __init__(self, ip_address: str, id: int, query: str, results: dict):
        self.ip_address = ip_address
        self.id = id
        self.query = query
        self.results = results

    def __repr__(self):
        return f"<QueryObject id={self.id} ip={self.ip_address} query={self.query}>"


def create_query_object(
    ip_address: str, id: Optional[int], query: str, results: Optional[dict] = None
) -> QueryObject:
    if results is None:
        results = {}
    # TODO: This should be changed because by some ungodly chance we could generate the same ID twice
    id = id if id is not None else random.randint(1, 100000000)
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


# Proxy Server Vars and Functions
SERVER_URL = "http://localhost:8080"
Lookup_Table = []  # For mapping .ts file ids to URLs
M3U8_Table = {}    # For mapping m3u8 ids to playlist content
import re

# Proxy endpoint for m3u8 playlists
@app.route('/proxy/<m3u8_id>.m3u8', methods=['GET'])
def proxy_m3u8(m3u8_id):
    logging.info(f"Proxying m3u8 for id {m3u8_id}")
    m3u8_content = M3U8_Table.get(m3u8_id)
    if not m3u8_content:
        logging.error(f"No m3u8 found for id {m3u8_id}")
        return Response("Not found", status=404)
    new_m3u8 = process_m3u8_content(m3u8_content, m3u8_id)
    return Response(new_m3u8, mimetype="application/vnd.apple.mpegurl")

# Proxy endpoint for .ts segments
# The point of this is to ensure compatability with legacy VLC versions that expect .ts files
@app.route('/partial/<path:partial_url>', methods=['GET'])
def partial(partial_url):
    partial_id = partial_url.split(".")[0]
    original_url = None
    logging.info(f"Received request for partial_id {partial_id}")
    for item in Lookup_Table:
        if item[0] == partial_id:
            original_url = item[1]
            break
    if original_url is None:
        logging.error(f"Original URL not found for {partial_id}")
        return Response(status=404)
    try:
        response = requests.get(original_url, stream=True, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        logging.info(f"Received response from {original_url}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {original_url}: {e}")
        return Response(status=500)
    headers = {
        "Content-Type": "video/mp2t",
        "Content-Length": response.headers.get('Content-Length')
    }
    return Response(
        stream_with_context(response.iter_content(chunk_size=4096)),
        headers=headers
    )

@app.after_request
def apply_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

# Process m3u8 content to replace .ts URLs with proxy URLs
def process_m3u8_content(content, m3u8_id):
    try:
        logging.info("Processing m3u8 content")
        drm_m3u8_lines = content.split("\n")
        new_m3u8_lines = []
        for line in drm_m3u8_lines:
            if line.startswith("https"):
                lookup_id = str(random.randint(1000000, 9999999999))
                proxy_lookup_url = f"{SERVER_URL}/partial/{lookup_id}.ts"
                Lookup_Table.append((lookup_id, line))
                new_m3u8_lines.append(proxy_lookup_url)
            else:
                new_m3u8_lines.append(line)
        logging.info("Processed m3u8 content")
        return "\n".join(new_m3u8_lines)
    except Exception as e:
        logging.error(f"Error processing m3u8 content: {e}")
        return content

# Endpoint to handle selection and return proxied m3u8 URL
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
    try:
        selection_int = int(selection_id)
    except ValueError:
        logging.error("Selection parameter must be an integer")
        return Response("Selection parameter must be an integer", status=400)
    if not (0 <= selection_int <= 10):
        logging.error("Selection parameter must be between 0 and 10")
        return Response("Selection parameter must be between 0 and 10", status=400)
    
    query_object = retrieve_query_object(id_int)
    if not query_object:
        logging.error(f"Query object with ID {id_int} not found")
        return Response(f"Query object with ID {id_int} not found", status=404)
    
    # Get the stored VRM response and sorted results
    vrm_response = query_object.results.get('vrm_response')
    sorted_results = query_object.results.get('sorted_results')
    
    if not vrm_response or not sorted_results:
        logging.error("Missing VRM response or sorted results in query object")
        return Response("Missing VRM response data", status=500)
    
    if selection_int >= len(sorted_results):
        logging.error(f"Selection index {selection_int} out of range")
        return Response("Selection index out of range", status=400)
    
    # Get the selected item from our sorted results
    selected_item = sorted_results[selection_int]
    
    # Find the original index of this item in the unsorted VRM results
    original_results = vrm_response.get('results', [])
    original_index = None
    
    for i, original_item in enumerate(original_results):
        if (original_item.get('title') == selected_item.get('title') and 
            original_item.get('rating') == selected_item.get('rating') and
            original_item.get('type') == selected_item.get('type')):
            original_index = i
            break
    
    if original_index is None:
        logging.error("Could not find selected item in original VRM results")
        return Response("Could not find selected item in original results", status=500)
    
    try:
        vrm_endpoint = VRM_ENDPOINT or "https://vr-m.net/"
        vrm_endpoint = vrm_endpoint.rstrip('/')
        # Use the original index from the VRM results array
        lock_url = f"{vrm_endpoint}/0/l/{original_index}"
        lock_resp = requests.get(lock_url, verify=False, headers={"User-Agent": USER_AGENT})
        if lock_resp.status_code != 200:
            logging.error(f"Failed to get lockId from VRM: {lock_resp.status_code}")
            return Response("Failed to get lockId from VRM", status=502)
        
        try:
            lock_data = json.loads(lock_resp.text)
            lockId = lock_data.get("lockId")
        except Exception as e:
            logging.error(f"Failed to parse lockId JSON: {e}")
            return Response("Failed to parse lockId from VRM response", status=502)
        if not lockId:
            logging.error("lockId not found in VRM response")
            return Response("lockId not found in VRM response", status=502)
        m3u8_url = f"{vrm_endpoint}/p/{lockId}.m3u8"
        m3u8_resp = requests.get(m3u8_url, verify=False, headers={"User-Agent": USER_AGENT})
        if m3u8_resp.status_code != 200:
            logging.error(f"Failed to get m3u8 from VRM: {m3u8_resp.status_code}")
            return Response("Failed to get m3u8 from VRM", status=502)
        # Store m3u8 in QueryObject and in M3U8_Table with a unique id
        m3u8_id = str(random.randint(1000000, 9999999))
        M3U8_Table[m3u8_id] = m3u8_resp.text
        query_object.results['m3u8'] = m3u8_resp.text
        # Return the proxy URL for the playlist
        proxy_url = f"{SERVER_URL}/proxy/{m3u8_id}.m3u8"
        return Response(proxy_url, mimetype="text/plain")
    except Exception as e:
        logging.error(f"Error during VRM m3u8 retrieval: {e}")
        return Response("Internal server error during m3u8 retrieval", status=500)

# Endpoint to handle search requests
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
        from urllib.parse import quote_plus
        # Step 1: Call VRM search API
        encoded_query = quote_plus(query)
        search_url = f"{vrm_endpoint}/0/s?q={encoded_query}"
        resp = requests.get(search_url, verify=False, headers={"User-Agent": USER_AGENT})
        if resp.status_code != 200:
            logging.error(f"Failed to search VRM: {resp.status_code}")
            return Response("Failed to search VRM", status=502)
        print(resp.text)  # Debug
        try:
            results_json = json.loads(resp.text)
        except Exception as e:
            logging.error(f"Failed to parse VRM search JSON: {e}")
            logging.error(f"Full stacktrace: {traceback.format_exc()}")
            return Response("Failed to parse VRM search JSON", status=502)
        
        # Store the full VRM response in the QueryObject for later use
        query_object.results['vrm_response'] = results_json
        
        # Step 2: Extract and sort results by rating
        results = []
        vrm_results = results_json.get('results', [])
        
        # Sort by rating in descending order (highest rating first)
        sorted_vrm_results = sorted(vrm_results, key=lambda x: x.get('rating', 0), reverse=True)
        
        # Limit to top 10 results for thumbnail API processing
        for index, item in enumerate(sorted_vrm_results[:10]):
            title = item.get('title') or item.get('name') or str(item)
            # Use the array index as the selection ID (this is what we'll send back to VRM)
            selection_id = index
            # TMDB thumbnail lookup
            thumbnail_url = None
            try:
                tmdb_search_url = f"https://api.themoviedb.org/3/search/movie?query={quote_plus(title)}&api_key={THEMOVIEDB_API_KEY}"
                tmdb_resp = requests.get(tmdb_search_url)
                if tmdb_resp.status_code == 200:
                    tmdb_data = tmdb_resp.json()
                    if tmdb_data.get('results'):
                        poster_path = tmdb_data['results'][0].get('poster_path')
                        if poster_path:
                            thumbnail_url = f"https://image.tmdb.org/t/p/w500{poster_path}"
                if not thumbnail_url:
                    thumbnail_url = f"{HOST}/static/fallback.png"
            except Exception as e:
                logging.warning(f"TMDB lookup failed for '{title}': {e}")
                logging.warning(f"TMDB lookup stacktrace: {traceback.format_exc()}")
                thumbnail_url = f"{HOST}/static/fallback.png"
            
            results.append({
                "title": title, 
                "selectionID": selection_id, 
                "thumbnail": thumbnail_url,
                "rating": item.get('rating', 0)
            })
        
        # Store the sorted results in QueryObject
        query_object.results['sorted_results'] = sorted_vrm_results[:10]
        query_object.results['results'] = results
        
        data = {
            "id": query_object.id,
            "results": results,
        }
        return Response(json.dumps(data), mimetype="application/json")
    except Exception as e:
        logging.error(f"Error during VRM search: {e}")
        logging.error(f"Full stacktrace: {traceback.format_exc()}")
        return Response("Internal server error during search", status=500)

# Without this exact user agent, the VRM API will not deny the request
USER_AGENT = "NSPlayer/12.00.19041.5848"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
