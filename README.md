# YouTube Livestream Betting System

A real-time system that transcribes YouTube livestreams to detect betting-related keywords and displays the results on a live dashboard.

# Note

Roughly about 3-6 seconds ahead of youtube, since youtube buffers videos for quality. Thus, audio ready before video and audio displayed together.

# Demo Video

https://www.youtube.com/watch?v=OyneyyiWA_w

## How It Works

The system connects to a YouTube livestream, transcribes the audio in real-time, and identifies specific keywords.

1.  **Audio Streaming**: The system takes a YouTube live URL and uses `yt-dlp` to get the direct audio stream. `ffmpeg` is then used to process this audio for transcription.
2.  **Real-Time Transcription**: The audio is streamed to Google's Speech-to-Text API, which provides a highly accurate, low-latency transcript.
3.  **Keyword Detection**: The incoming transcript is scanned for a predefined list of betting-related keywords (e.g., "bet", "odds", "win").
4.  **Live Dashboard**: A web-based dashboard connects to the system via WebSockets to display the full transcript and highlight any detected "betting events" as they happen.

## Project Components

*   `betting_system.py`: The core Python application that handles audio capture, transcription, keyword detection, and the WebSocket server for the dashboard.
*   `dashboard.html`: The frontend interface. It receives data from the Python application and displays the live transcript and betting events.
*   `server.js`: A simple Node.js Express server to serve the `dashboard.html` file.


## Setup and Installation

### Prerequisites

*   Python 3.8+
*   Node.js and npm
*   FFmpeg
*   Google Cloud Account with Speech-to-Text API enabled.

### 1. Google Cloud Authentication

The system uses Google's Application Default Credentials. You need to provide your service account credentials to authenticate.

1.  In the Google Cloud Console, create a service account for your project.
2.  Grant this service account the **Cloud Speech-to-Text API User** role.
3.  Create a key for the service account and download the JSON key file.
4.  Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to the path of your downloaded key file.

You can do this by running the following command in your terminal before starting the application:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"
```

For convenience, you can also create a `.env` file in the project's root directory and add the line there. The application will automatically load it.

**.env file:**
```
GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"
```

### 2. Install Dependencies

*   **Python**:
    ```bash
    pip install -r requirements.txt
    ```
*   **Node.js**:
    ```bash
    npm install
    ```

## How to Run

1.  **Start the Betting System**:
    Open a terminal and run the Python application with the URL of the YouTube livestream you want to monitor.
    ```bash
    python betting_system.py "YOUTUBE_LIVESTREAM_URL"
    ```
    This will start the transcription and the WebSocket server on port `8765`.

2.  **Start the Dashboard Server**:
    In a second terminal, start the Node.js server. This serves the `dashboard.html` page.
    ```bash
    npm start
    ```
    The server will run on `http://localhost:3000`.

3.  **View the Dashboard & Connect to WebSocket**:
    Open `http://localhost:3000` in your web browser. The JavaScript in the dashboard will automatically connect to the WebSocket server (started by the Python script) and begin displaying live results.
