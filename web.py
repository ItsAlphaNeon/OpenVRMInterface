import subprocess
import threading
import time
import requests
from flask import Flask, render_template_string, request, jsonify

# This is a simple web interface to test the OpenVRMInterface backend.
# It starts the backend as a subprocess and provides a GUI to interact with it.
# Make sure to have the OpenVRMInterface backend (main.py) in the same directory.
# This file is not essential for the backend to work, but provides a convenient way to test it.

# Start main.py as a subprocess
backend_proc = subprocess.Popen(["python3", "main.py"])


def shutdown_backend():
    backend_proc.terminate()


app = Flask(__name__)

# HTML template for the GUI
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>OpenVRMInterface Web GUI</title>
    <style>
        body { font-family: Arial, sans-serif; background: #181c20; color: #eee; margin: 0; padding: 0; }
        .container { max-width: 700px; margin: 40px auto; background: #23272b; border-radius: 8px; box-shadow: 0 2px 8px #0008; padding: 32px; }
        h1 { text-align: center; }
        input[type=text] { width: 80%; padding: 8px; border-radius: 4px; border: none; }
        button { padding: 8px 16px; border-radius: 4px; border: none; background: #4caf50; color: #fff; cursor: pointer; }
        button:hover { background: #388e3c; }
        .results { margin-top: 24px; }
        .result { display: flex; align-items: center; background: #2c3136; margin-bottom: 12px; border-radius: 4px; padding: 8px; }
        .result img { width: 60px; height: 90px; object-fit: cover; border-radius: 4px; margin-right: 16px; }
        .result-title { flex: 1; }
        .player { margin-top: 32px; text-align: center; }
        .m3u8-link { color: #4caf50; }
    </style>
</head>
<body>
<div class="container">
    <h1>OpenVRMInterface Web GUI</h1>
    <form id="searchForm">
        <input type="text" id="query" placeholder="Search for a movie..." required>
        <button type="submit">Search</button>
    </form>
    <div class="results" id="results"></div>
    <div class="player" id="player"></div>
</div>
<script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
<script>
const backend = 'http://localhost:8080';
const gui = 'http://localhost:5000';
let lastQueryId = null;
let lastResults = [];

document.getElementById('searchForm').onsubmit = async function(e) {
    e.preventDefault();
    const q = document.getElementById('query').value;
    document.getElementById('results').innerHTML = 'Searching...';
    document.getElementById('player').innerHTML = '';
    try {
        const resp = await fetch(`${backend}/search/?query=` + encodeURIComponent(q));
        if (!resp.ok) throw new Error('Search failed');
        const data = await resp.json();
        lastQueryId = data.id;
        lastResults = data.results;
        let html = '';
        for (let i = 0; i < data.results.length; i++) {
            const r = data.results[i];
            // Only enable select if selectionID is a string or number
            let canSelect = typeof r.selectionID === 'string' || typeof r.selectionID === 'number';
            html += `<div class='result'>` +
                `<img src='${r.thumbnail}' onerror="this.src='/static/fallback.png'">` +
                `<div class='result-title'>${r.title}</div>` +
                (canSelect
                  ? `<button onclick='selectResult(${i})'>Select</button>`
                  : `<button disabled title='No valid selectionID'>N/A</button>`)
                + `</div>`;
        }
        document.getElementById('results').innerHTML = html || 'No results.';
    } catch (err) {
        document.getElementById('results').innerHTML = 'Error: ' + err;
    }
};

window.selectResult = async function(idx) {
    const sel = lastResults[idx];
    // Defensive: Only proceed if selectionID is valid
    if (!(typeof sel.selectionID === 'string' || typeof sel.selectionID === 'number')) {
        document.getElementById('player').innerHTML = 'Error: No valid selectionID for this result.';
        return;
    }
    document.getElementById('player').innerHTML = 'Loading stream...';
    try {
        // Pass only the index (integer) as the selection parameter
        const resp = await fetch(`${backend}/submit/?id=${lastQueryId}&selection=${idx}`);
        if (!resp.ok) throw new Error('Failed to get m3u8');
        const m3u8url = await resp.text();
        let html = `<div>M3U8 Proxy URL: <a class='m3u8-link' href='${m3u8url}' target='_blank'>${m3u8url}</a></div>`;
        // Try to play with hls.js
        html += `<video id='video' width='480' height='270' controls style='margin-top:16px; background:#000;'></video>`;
        document.getElementById('player').innerHTML = html;
        if (Hls.isSupported()) {
            var video = document.getElementById('video');
            var hls = new Hls();
            hls.loadSource(m3u8url);
            hls.attachMedia(video);
            hls.on(Hls.Events.ERROR, function(event, data) {
                if (data.fatal) {
                    document.getElementById('player').innerHTML += '<div style="color:red">Playback error: ' + data.type + '</div>';
                }
            });
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = m3u8url;
        } else {
            document.getElementById('player').innerHTML += '<div style="color:orange">Your browser does not support m3u8 playback. Use the link above in a compatible player.</div>';
        }
    } catch (err) {
        document.getElementById('player').innerHTML = 'Error: ' + err;
    }
};
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        shutdown_backend()
