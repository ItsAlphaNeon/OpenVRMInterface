# OpenVRMInterface

A Flask-based proxy and search interface for the VRM streaming API, with integrated TheMovieDB (TMDB) thumbnail lookups. This project provides endpoints for searching VRM, proxying m3u8 playlists and .ts video segments, and serving results with movie thumbnails.

## Features

- **Search VRM**: Query the VRM API for movies or shows.
- **TMDB Integration**: Fetches movie thumbnails from TheMovieDB for search results.
- **Proxy Streaming**: Proxies m3u8 playlists and .ts segments for seamless playback.
- **CORS Enabled**: Allows cross-origin requests for easy integration with web clients.

## Requirements

- Python 3.10+
- [Flask](https://flask.palletsprojects.com/)
- [requests](https://docs.python-requests.org/)
- [python-dotenv](https://pypi.org/project/python-dotenv/)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Setup

### 1. Create a `.env` file

Create a `.env` file in the project root with the following variables:

```env
THEMOVIEDB_API_KEY=
VRM_ENDPOINT=vr-m.net/
HOST=http://localhost:8080
```

- `THEMOVIEDB_API_KEY`: Your [TMDB API key](https://www.themoviedb.org/documentation/api).
- `VRM_ENDPOINT`: The VRM API endpoint (without protocol, e.g., `vr-m.net/`).
- `HOST`: The host URL for your Flask server (default: `http://localhost:8080`).

### 2. (Optional) Set up a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## Usage

Start the server:

```bash
python main.py
```

The server will run on `0.0.0.0:8080` by default.

### Endpoints

#### `/search/?query=...`

Search for a movie via VRM. Returns a JSON object with results and thumbnails.

**Example:**

```http
GET http://localhost:8080/search/?query=Inception
```

**Response:**

```json
{
  "id": 123456,
  "results": [
    {
      "title": "Inception",
      "selectionID": "...",
      "thumbnail": "https://image.tmdb.org/t/p/w500/...jpg"
    },
    ...
  ]
}
```

#### `/submit/?id=...&selection=...`

Given a search result ID and selection, retrieves and proxies the m3u8 playlist for playback.

**Example:**

```http
GET http://localhost:8080/submit/?id=123456&selection=abcdef
```

**Response:**

```text
http://localhost:8080/proxy/6543210.m3u8
```

#### `/proxy/<m3u8_id>.m3u8`

Proxies the m3u8 playlist, rewriting segment URLs to go through the server.

#### `/partial/<segment_id>.ts`

Proxies individual .ts video segments.

## Static Files

- `static/fallback.png`: Used as a fallback thumbnail if TMDB lookup fails.

## Notes

- The VRM API requires a specific User-Agent. This is handled automatically.
- All data is stored in-memory; this is not intended for production use without modification.
- CORS headers are set to allow all origins.

## License

MIT License
