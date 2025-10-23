#!/usr/bin/env python3
"""
Real-Time YouTube Betting System with Google's Streaming STT API

This high-performance system uses Google's official Streaming Speech-to-Text API 
for the lowest possible latency and highest accuracy.
"""

import asyncio
import subprocess
import time
import json
import logging
import sys
from typing import List, Set, Optional
from dotenv import load_dotenv

from google.cloud import speech
import websockets
from websockets.server import WebSocketServerProtocol

# --- Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BettingSystem:
    """The main class for the real-time betting system."""

    def __init__(self, keywords: List[str], ws_port: int = 8765):
        self.keywords = set(kw.lower() for kw in keywords)
        self.ws_port = ws_port
        
        # Google Cloud Speech Client
        self.speech_client = speech.SpeechAsyncClient()          #Load the Google Cloud Speech Client - finds API key in environment
        self.streaming_config = self._get_streaming_config()
        
        # Streaming & Processing State
        self.is_running = False
        self.ffmpeg_process = None
        
        # WebSocket Clients
        self.clients: Set[WebSocketServerProtocol] = set()

    def _get_streaming_config(self) -> speech.StreamingRecognitionConfig:
        """Creates the configuration for Google's streaming STT."""
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="video", # Model optimized for audio from video
        )
        return speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True  # Get faster, less accurate results as they come in
        )

    async def start(self, youtube_url: str):
        """Starts all components of the betting system."""
        self.is_running = True
        logger.info("--- Starting Real-Time Betting System (Google Streaming API) ---")
        logger.info(f"YouTube URL: {youtube_url}")
        
        server = await websockets.serve(self._websocket_handler, "localhost", self.ws_port)
        logger.info(f"WebSocket server started on ws://localhost:{self.ws_port}")

        try:
            stream_url = await self._get_stream_url(youtube_url)
            if not stream_url:
                raise RuntimeError("Failed to get stream URL.")
            
            await self._start_ffmpeg_process(stream_url)
            
            # This is now the main processing task
            await self._google_stt_stream()

        except Exception as e:
            logger.error(f"System failed to start: {e}")
        finally:
            self.stop()
            server.close()
            await server.wait_closed()
            logger.info("--- System Shutting Down ---")

    async def _get_stream_url(self, youtube_url: str) -> Optional[str]:
        """Gets the direct HLS stream URL from yt-dlp with a timeout."""
        logger.info("Getting direct stream URL from yt-dlp (15s timeout)...")
        try:
            process = await asyncio.create_subprocess_exec(
                'yt-dlp', '-g', youtube_url,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15.0)
            if process.returncode != 0:
                logger.error(f"yt-dlp error: {stderr.decode()}")
                return None
            
            stream_url = stdout.decode().strip().split('\n')[-1]
            logger.info(f"Successfully got stream URL.")
            return stream_url
        except asyncio.TimeoutError:
            logger.error("yt-dlp timed out.")
            return None
        except Exception as e:
            logger.error(f"Error getting stream URL: {e}")
            return None

    async def _start_ffmpeg_process(self, stream_url: str):
        """Starts the FFmpeg process to capture the audio stream."""
        cmd = [
            'ffmpeg', '-i', stream_url,
            '-f', 's16le', '-ar', '16000', '-ac', '1', '-'
        ]
        
        logger.info("Starting FFmpeg to capture audio stream...")
        self.ffmpeg_process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await asyncio.sleep(2) # Give FFmpeg a moment to start
        if self.ffmpeg_process.returncode is not None:
             _, stderr = await self.ffmpeg_process.communicate()
             raise RuntimeError(f"FFmpeg failed to start: {stderr.decode()}")
        logger.info("Audio stream capture started successfully.")

    async def _google_stt_stream(self):
        """The main loop that streams audio to Google and processes results."""
        
        async def request_generator():
            """Yields the config request first, then audio chunks."""
            # The first request must contain the configuration
            yield speech.StreamingRecognizeRequest(streaming_config=self.streaming_config)
            
            # Following requests contain the audio data
            while self.is_running:
                try:
                    chunk = await self.ffmpeg_process.stdout.read(8000)
                    if not chunk:
                        break
                    yield speech.StreamingRecognizeRequest(audio_content=chunk)
                except asyncio.CancelledError:
                    break
        
        # The streaming_recognize method returns a coroutine that must be awaited
        responses = await self.speech_client.streaming_recognize(requests=request_generator())

        logger.info("Streaming audio to Google STT...")
        async for response in responses:
            if not self.is_running:
                break
            self._process_stt_response(response)

    def _process_stt_response(self, response: speech.StreamingRecognizeResponse):
        """Processes a single response from the Google STT stream."""
        for result in response.results:
            if not result.alternatives:
                continue
            
            transcript = result.alternatives[0].transcript
            
            # We can get results that are not yet "final"
            is_final = result.is_final
            
            detected_keywords = self._find_keywords(transcript)
            
            message = {
                "type": "transcription",
                "timestamp": time.time(),
                "text": transcript,
                "keywords": detected_keywords,
                "is_final": is_final
            }
            
            # Use asyncio.create_task to broadcast without blocking
            asyncio.create_task(self._broadcast(message))

            if is_final and detected_keywords:
                logger.info(f"💬 \"{transcript}\" -> 🎯 DETECTED: {detected_keywords}")

    def _find_keywords(self, text: str) -> List[str]:
        """Finds registered keywords in the transcribed text."""
        found = []
        words = text.lower().replace('.', '').replace(',', '').split()
        for word in words:
            if word in self.keywords:
                found.append(word)
        return list(set(found))

    async def _websocket_handler(self, websocket: WebSocketServerProtocol):
        """Handles new WebSocket client connections."""
        logger.info(f"New dashboard client connected: {websocket.remote_address}")
        self.clients.add(websocket)
        try:
            await websocket.wait_closed()
        finally:
            logger.info(f"Dashboard client disconnected: {websocket.remote_address}")
            self.clients.remove(websocket)

    async def _broadcast(self, message: dict):
        """Broadcasts a JSON message to all connected WebSocket clients."""
        if not self.clients:
            return
        
        # Use asyncio.gather for concurrent broadcasting
        tasks = [client.send(json.dumps(message)) for client in self.clients]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    def stop(self):
        """Stops the system and cleans up processes."""
        self.is_running = False
        if self.ffmpeg_process and self.ffmpeg_process.returncode is None:
            self.ffmpeg_process.terminate()
            logger.info("FFmpeg process terminated.")

async def main():
    """Entry point of the application."""
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <youtube_live_url>")
        sys.exit(1)
    
    youtube_url = sys.argv[1]
    
    #List of Words that are actively being looked for
    betting_keywords = [
        'bet', 'wager', 'odds', 'win', 'lose', 'money', 'cash', 'profit',
        'jackpot', 'bonus', 'multiplier', 'double', 'triple', 'all-in',
        'fold', 'call', 'raise', 'bluff', 'poker', 'blackjack', 'roulette',
        'hit', 'stand', 'bust', 'dealer', 'hand', 'card', 'ace', 'king'
    ]

    system = BettingSystem(keywords=betting_keywords)
    try:
        await system.start(youtube_url)
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
    except Exception as e:
        logger.error(f"An unhandled error occurred: {e}")
    finally:
        system.stop()
        logger.info("System has been shut down.")

if __name__ == "__main__":
    asyncio.run(main())
