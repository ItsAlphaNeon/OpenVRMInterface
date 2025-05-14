from flask import Flask, request, Response, stream_with_context
import requests
import re
import logging
import random

# -=- Static Vars -=-
SERVER_URL = "http://localhost:8080"

# -=- Global Vars -=-
Lookup_Table = []  # This is a list in RAM for taking id .ts files and converting them to the correct URL

# Initialize the Flask application and configure logging
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# -=- API endpoints -=-
@app.route('/<path:url>', methods=['GET'])
def proxy(url):
    logging.info(f"Received request for {url}")
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        logging.info(f"Received response from {url}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {url}: {e}")
        return Response(status=500)

    new_m3u8 = process_m3u8_content(response.text)
    return Response(new_m3u8, mimetype="application/vnd.apple.mpegurl")
    

@app.route('/partial/<path:partial_url>', methods=['GET'])
def partial(partial_url):
    partial_id = partial_url.split(".")[0]
    original_url = None
    logging.info(f"Received request for {partial_id}")

    for item in Lookup_Table:
        if item[0] == partial_id:
            original_url = item[1]
            break

    if original_url is None:
        logging.error(f"Original URL not found for {partial_id}")
        return Response(status=404)

    try:
        response = requests.get(original_url, stream=True)
        response.raise_for_status()
        logging.info(f"Received response from {original_url}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching {original_url}: {e}")
        return Response(status=500)
    
    # Explicitly set the content-type as video/mp2t for .ts files
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

def process_m3u8_content(content):
    try:
        logging.info("Processing m3u8 content")
        drm_m3u8_lines = content.split("\n")
        new_m3u8_lines = []
        
        for line in drm_m3u8_lines:
            if line.startswith("https"):
                lookup_id = str(random.randint(1000000, 9999999))
                proxy_lookup_url = SERVER_URL + "/partial/" + lookup_id + ".ts"
                Lookup_Table.append((lookup_id, line))
                new_m3u8_lines.append(proxy_lookup_url)
            else:
                new_m3u8_lines.append(line)
        
        logging.info("Processed m3u8 content")
        return "\n".join(new_m3u8_lines)
    except Exception as e:
        logging.error(f"Error processing m3u8 content: {e}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)
