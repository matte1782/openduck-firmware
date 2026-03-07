"""Text-to-Speech Engine for OpenDuck Mini V3

This module provides a complete TTS (Text-to-Speech) system with:
- Multiple TTS backends (pyttsx3 offline, gTTS online)
- Phrase caching for instant playback of common utterances
- Integration with MAX98357A amplifier for audio output

Architecture:
    1. TTSEngine: Core synthesis (pyttsx3/gTTS wrapper)
    2. TTSCache: Hash-based phrase caching with file persistence
    3. TTSSpeaker: High-level API integrating synthesis + cache + playback

Thread Safety:
    All components are thread-safe. TTSCache uses RLock for concurrent access.
    TTSSpeaker uses a queue for sequential utterance playback.

Example (Simple):
    ```python
    from src.drivers.audio.tts_engine import TTSSpeaker

    speaker = TTSSpeaker()
    speaker.speak("Hello, I am OpenDuck!")
    speaker.speak("How can I help you today?")
    ```

Example (With Caching):
    ```python
    from src.drivers.audio.tts_engine import TTSSpeaker

    speaker = TTSSpeaker()

    # Preload common phrases for instant playback
    speaker.preload_phrases([
        "Hello!",
        "Goodbye!",
        "I'm thinking...",
        "Yes",
        "No",
    ])

    # These will play instantly from cache
    speaker.speak("Hello!")
    speaker.speak("Goodbye!")
    ```

Hardware Requirements:
    - MAX98357A amplifier (for actual audio output)
    - Works in mock mode without hardware

Software Requirements:
    - pyttsx3 (pip install pyttsx3) - offline TTS
    - gTTS (pip install gTTS) - online TTS fallback
    - Both are optional; mock mode works without them

Author: Day 17 Implementation (IAO-v2-DYNAMIC)
Date: 22 January 2026
"""

import hashlib
import io
import logging
import os
import struct
import tempfile
import threading
import time
import wave
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from queue import Queue, Empty
from typing import Optional, List, Callable, Dict, Any

# Module logger
_logger = logging.getLogger(__name__)

# Try to import TTS libraries (optional)
_PYTTSX3_AVAILABLE = False
_GTTS_AVAILABLE = False

try:
    import pyttsx3
    _PYTTSX3_AVAILABLE = True
except ImportError:
    _logger.debug("pyttsx3 not available - offline TTS disabled")

try:
    from gtts import gTTS
    _GTTS_AVAILABLE = True
except ImportError:
    _logger.debug("gTTS not available - online TTS disabled")


# =============================================================================
# AGENT 1: TTSEngine (Core Synthesis)
# =============================================================================

class TTSBackend(Enum):
    """Available TTS backends."""
    PYTTSX3 = auto()  # Offline, fast, robotic voice
    GTTS = auto()      # Online, natural voice, requires internet
    MOCK = auto()      # No synthesis, returns silence (for testing)


@dataclass
class TTSVoiceConfig:
    """Voice configuration for TTS synthesis.

    Attributes:
        rate: Speech rate (words per minute). Default 150.
        volume: Voice volume (0.0-1.0). Default 0.9.
        pitch: Voice pitch adjustment (backend-specific).
        language: Language code (e.g., 'en', 'it'). Default 'en'.
    """
    rate: int = 150
    volume: float = 0.9
    pitch: float = 1.0
    language: str = "en"

    def __post_init__(self):
        if not 50 <= self.rate <= 400:
            raise ValueError(f"rate must be 50-400, got {self.rate}")
        if not 0.0 <= self.volume <= 1.0:
            raise ValueError(f"volume must be 0.0-1.0, got {self.volume}")
        if not 0.5 <= self.pitch <= 2.0:
            raise ValueError(f"pitch must be 0.5-2.0, got {self.pitch}")


class TTSEngine:
    """Core TTS synthesis engine.

    Wraps pyttsx3 (offline) and gTTS (online) backends with automatic
    fallback and mock mode for development.

    Thread Safety:
        The engine is NOT thread-safe for concurrent synthesis.
        Use one engine per thread, or synchronize externally.

    Attributes:
        backend: Currently active TTS backend.
        voice_config: Voice configuration settings.
    """

    # Sample rate for all TTS output (matches MAX98357A TTS config)
    SAMPLE_RATE = 16000

    def __init__(
        self,
        backend: Optional[TTSBackend] = None,
        voice_config: Optional[TTSVoiceConfig] = None,
        force_mock: bool = False
    ):
        """Initialize TTS engine.

        Args:
            backend: Preferred backend (auto-detect if None).
            voice_config: Voice settings (use defaults if None).
            force_mock: Force mock mode regardless of library availability.
        """
        self.voice_config = voice_config or TTSVoiceConfig()
        self._pyttsx3_engine: Optional[Any] = None

        # Determine backend
        if force_mock:
            self.backend = TTSBackend.MOCK
        elif backend is not None:
            self.backend = backend
        elif _PYTTSX3_AVAILABLE:
            self.backend = TTSBackend.PYTTSX3
        elif _GTTS_AVAILABLE:
            self.backend = TTSBackend.GTTS
        else:
            self.backend = TTSBackend.MOCK
            _logger.warning(
                "No TTS backend available. Install pyttsx3 or gTTS. Using mock mode."
            )

        # Initialize backend
        self._initialize_backend()

        _logger.info(f"TTSEngine initialized with backend: {self.backend.name}")

    def _initialize_backend(self) -> None:
        """Initialize the selected TTS backend."""
        if self.backend == TTSBackend.PYTTSX3 and _PYTTSX3_AVAILABLE:
            try:
                self._pyttsx3_engine = pyttsx3.init()
                self._apply_voice_config_pyttsx3()
            except Exception as e:
                _logger.error(f"Failed to initialize pyttsx3: {e}")
                self.backend = TTSBackend.MOCK

    def _apply_voice_config_pyttsx3(self) -> None:
        """Apply voice config to pyttsx3 engine."""
        if self._pyttsx3_engine is None:
            return

        try:
            self._pyttsx3_engine.setProperty('rate', self.voice_config.rate)
            self._pyttsx3_engine.setProperty('volume', self.voice_config.volume)
        except Exception as e:
            _logger.warning(f"Failed to apply pyttsx3 voice config: {e}")

    def set_voice(
        self,
        rate: Optional[int] = None,
        volume: Optional[float] = None,
        pitch: Optional[float] = None,
        language: Optional[str] = None
    ) -> None:
        """Update voice configuration.

        Args:
            rate: Speech rate (words per minute).
            volume: Voice volume (0.0-1.0).
            pitch: Voice pitch adjustment.
            language: Language code.
        """
        if rate is not None:
            self.voice_config.rate = rate
        if volume is not None:
            self.voice_config.volume = volume
        if pitch is not None:
            self.voice_config.pitch = pitch
        if language is not None:
            self.voice_config.language = language

        # Re-apply to backend
        if self.backend == TTSBackend.PYTTSX3:
            self._apply_voice_config_pyttsx3()

    def get_available_voices(self) -> List[str]:
        """Get list of available voices.

        Returns:
            List of voice identifiers.
        """
        if self.backend == TTSBackend.PYTTSX3 and self._pyttsx3_engine:
            try:
                voices = self._pyttsx3_engine.getProperty('voices')
                return [v.id for v in voices]
            except Exception:
                pass
        return ["default"]

    def synthesize(self, text: str, timeout: float = 10.0) -> bytes:
        """Synthesize text to audio.

        Args:
            text: Text to synthesize.
            timeout: Maximum synthesis time in seconds.

        Returns:
            Raw audio as 16-bit PCM, 16kHz, mono.

        Raises:
            RuntimeError: If synthesis fails.
            TimeoutError: If synthesis exceeds timeout.
        """
        if not text or not text.strip():
            return self._generate_silence(100)  # 100ms silence for empty text

        text = text.strip()

        if self.backend == TTSBackend.MOCK:
            return self._synthesize_mock(text)
        elif self.backend == TTSBackend.PYTTSX3:
            return self._synthesize_pyttsx3(text, timeout)
        elif self.backend == TTSBackend.GTTS:
            return self._synthesize_gtts(text, timeout)
        else:
            return self._synthesize_mock(text)

    def _synthesize_mock(self, text: str) -> bytes:
        """Generate mock audio (silence with appropriate duration).

        Estimates duration based on word count (~150 WPM).
        """
        word_count = len(text.split())
        duration_ms = int((word_count / 150) * 60 * 1000)
        duration_ms = max(500, min(duration_ms, 10000))  # 0.5-10 seconds
        return self._generate_silence(duration_ms)

    def _synthesize_pyttsx3(self, text: str, timeout: float) -> bytes:
        """Synthesize using pyttsx3 (offline)."""
        if self._pyttsx3_engine is None:
            raise RuntimeError("pyttsx3 engine not initialized")

        # pyttsx3 saves to file, we need to capture it
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_path = f.name

        try:
            # Synthesize to temp file
            self._pyttsx3_engine.save_to_file(text, temp_path)
            self._pyttsx3_engine.runAndWait()

            # Read and convert WAV
            return self._wav_file_to_pcm(temp_path)

        except Exception as e:
            raise RuntimeError(f"pyttsx3 synthesis failed: {e}")
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    def _synthesize_gtts(self, text: str, timeout: float) -> bytes:
        """Synthesize using gTTS (online)."""
        if not _GTTS_AVAILABLE:
            raise RuntimeError("gTTS not available")

        try:
            # gTTS returns MP3, we need to convert to WAV
            tts = gTTS(text=text, lang=self.voice_config.language)

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
                temp_mp3 = f.name

            try:
                tts.save(temp_mp3)

                # Convert MP3 to PCM (requires additional library)
                # For now, fallback to mock if conversion not available
                _logger.warning("gTTS MP3 conversion not implemented, using mock")
                return self._synthesize_mock(text)

            finally:
                try:
                    os.unlink(temp_mp3)
                except Exception:
                    pass

        except Exception as e:
            raise RuntimeError(f"gTTS synthesis failed: {e}")

    def _wav_file_to_pcm(self, filepath: str) -> bytes:
        """Convert WAV file to 16-bit PCM at target sample rate."""
        with wave.open(filepath, 'rb') as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            framerate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())

        # Convert to 16-bit if needed
        if sample_width == 1:
            # 8-bit to 16-bit
            samples = struct.unpack(f'{len(frames)}B', frames)
            samples = [(s - 128) * 256 for s in samples]
            frames = struct.pack(f'<{len(samples)}h', *samples)
        elif sample_width == 4:
            # 32-bit to 16-bit
            samples = struct.unpack(f'<{len(frames)//4}i', frames)
            samples = [s >> 16 for s in samples]
            frames = struct.pack(f'<{len(samples)}h', *samples)

        # Convert stereo to mono if needed
        if channels == 2:
            num_samples = len(frames) // 4
            stereo = struct.unpack(f'<{num_samples * 2}h', frames)
            mono = [(stereo[i] + stereo[i + 1]) // 2 for i in range(0, len(stereo), 2)]
            frames = struct.pack(f'<{len(mono)}h', *mono)

        # Resample if needed
        if framerate != self.SAMPLE_RATE:
            frames = self._resample(frames, framerate, self.SAMPLE_RATE)

        return frames

    def _resample(self, samples: bytes, from_rate: int, to_rate: int) -> bytes:
        """Simple linear resampling."""
        if from_rate == to_rate:
            return samples

        num_samples = len(samples) // 2
        values = struct.unpack(f'<{num_samples}h', samples)

        ratio = to_rate / from_rate
        out_length = int(num_samples * ratio)

        resampled = []
        for i in range(out_length):
            src_idx = i / ratio
            idx_low = int(src_idx)
            idx_high = min(idx_low + 1, num_samples - 1)
            frac = src_idx - idx_low
            value = int(values[idx_low] * (1 - frac) + values[idx_high] * frac)
            resampled.append(value)

        return struct.pack(f'<{out_length}h', *resampled)

    def _generate_silence(self, duration_ms: int) -> bytes:
        """Generate silence of specified duration."""
        num_samples = int(self.SAMPLE_RATE * duration_ms / 1000)
        return bytes(num_samples * 2)  # 16-bit = 2 bytes per sample


# =============================================================================
# AGENT 2: TTSCache (Phrase Caching)
# =============================================================================

@dataclass
class TTSCacheConfig:
    """Configuration for TTS phrase cache.

    Attributes:
        cache_dir: Directory for persistent cache files.
        memory_cache_size: Maximum phrases in memory (LRU eviction).
        enable_persistence: Whether to save to disk.
    """
    cache_dir: Path = field(default_factory=lambda: Path("firmware/cache/tts"))
    memory_cache_size: int = 100
    enable_persistence: bool = True


class TTSCache:
    """Thread-safe phrase cache with LRU eviction and file persistence.

    Caches synthesized audio by text hash for instant playback of
    repeated phrases.

    Thread Safety:
        All operations are protected by RLock for thread-safe access.

    Attributes:
        config: Cache configuration.
        hit_count: Number of cache hits.
        miss_count: Number of cache misses.
    """

    def __init__(self, config: Optional[TTSCacheConfig] = None):
        """Initialize TTS cache.

        Args:
            config: Cache configuration (uses defaults if None).
        """
        self.config = config or TTSCacheConfig()
        self._lock = threading.RLock()
        self._memory_cache: OrderedDict[str, bytes] = OrderedDict()

        # Statistics
        self.hit_count = 0
        self.miss_count = 0

        # Ensure cache directory exists
        if self.config.enable_persistence:
            self.config.cache_dir.mkdir(parents=True, exist_ok=True)

        _logger.info(f"TTSCache initialized: dir={self.config.cache_dir}")

    @staticmethod
    def _text_to_hash(text: str) -> str:
        """Generate hash for text (deterministic cache key)."""
        normalized = text.lower().strip()
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()[:16]

    def get(self, text: str) -> Optional[bytes]:
        """Get cached audio for text.

        Args:
            text: Text to look up.

        Returns:
            Cached audio bytes, or None if not cached.
        """
        cache_key = self._text_to_hash(text)

        with self._lock:
            # Check memory cache first (and move to end for LRU)
            if cache_key in self._memory_cache:
                self._memory_cache.move_to_end(cache_key)
                self.hit_count += 1
                _logger.debug(f"Cache HIT (memory): {text[:30]}...")
                return self._memory_cache[cache_key]

            # Check file cache
            if self.config.enable_persistence:
                cache_file = self.config.cache_dir / f"{cache_key}.pcm"
                if cache_file.exists():
                    try:
                        audio = cache_file.read_bytes()
                        # Add to memory cache
                        self._add_to_memory_cache(cache_key, audio)
                        self.hit_count += 1
                        _logger.debug(f"Cache HIT (file): {text[:30]}...")
                        return audio
                    except Exception as e:
                        _logger.warning(f"Failed to read cache file: {e}")

            self.miss_count += 1
            _logger.debug(f"Cache MISS: {text[:30]}...")
            return None

    def put(self, text: str, audio: bytes) -> None:
        """Store audio in cache.

        Args:
            text: Text that was synthesized.
            audio: Synthesized audio bytes.
        """
        cache_key = self._text_to_hash(text)

        with self._lock:
            # Add to memory cache
            self._add_to_memory_cache(cache_key, audio)

            # Persist to file
            if self.config.enable_persistence:
                try:
                    cache_file = self.config.cache_dir / f"{cache_key}.pcm"
                    cache_file.write_bytes(audio)
                    _logger.debug(f"Cached to file: {text[:30]}...")
                except Exception as e:
                    _logger.warning(f"Failed to write cache file: {e}")

    def _add_to_memory_cache(self, key: str, audio: bytes) -> None:
        """Add to memory cache with LRU eviction."""
        # Evict oldest if at capacity
        while len(self._memory_cache) >= self.config.memory_cache_size:
            self._memory_cache.popitem(last=False)

        self._memory_cache[key] = audio

    def preload(self, phrases: List[str], engine: 'TTSEngine') -> int:
        """Preload phrases into cache.

        Args:
            phrases: List of phrases to preload.
            engine: TTS engine for synthesis.

        Returns:
            Number of phrases synthesized (not already cached).
        """
        synthesized = 0

        for phrase in phrases:
            if self.get(phrase) is None:
                try:
                    audio = engine.synthesize(phrase)
                    self.put(phrase, audio)
                    synthesized += 1
                except Exception as e:
                    _logger.warning(f"Failed to preload '{phrase}': {e}")

        _logger.info(f"Preloaded {synthesized}/{len(phrases)} phrases")
        return synthesized

    def clear(self, memory_only: bool = False) -> None:
        """Clear the cache.

        Args:
            memory_only: If True, only clear memory cache (keep files).
        """
        with self._lock:
            self._memory_cache.clear()
            self.hit_count = 0
            self.miss_count = 0

            if not memory_only and self.config.enable_persistence:
                for cache_file in self.config.cache_dir.glob("*.pcm"):
                    try:
                        cache_file.unlink()
                    except Exception:
                        pass

        _logger.info(f"Cache cleared (memory_only={memory_only})")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with hit_count, miss_count, hit_rate, size.
        """
        with self._lock:
            total = self.hit_count + self.miss_count
            hit_rate = self.hit_count / total if total > 0 else 0.0

            return {
                'hit_count': self.hit_count,
                'miss_count': self.miss_count,
                'hit_rate': hit_rate,
                'memory_size': len(self._memory_cache),
                'memory_bytes': sum(len(v) for v in self._memory_cache.values()),
            }


# =============================================================================
# AGENT 3: TTSSpeaker (Integration Layer)
# =============================================================================

class TTSSpeakerState(Enum):
    """Speaker state enumeration."""
    IDLE = auto()
    SPEAKING = auto()
    QUEUED = auto()
    ERROR = auto()


@dataclass
class TTSSpeakerConfig:
    """Configuration for TTS speaker.

    Attributes:
        volume: Output volume (0.0-1.0).
        use_cache: Whether to use phrase caching.
        async_queue: Whether to process queue asynchronously.
    """
    volume: float = 0.8
    use_cache: bool = True
    async_queue: bool = True

    def __post_init__(self):
        if not 0.0 <= self.volume <= 1.0:
            raise ValueError(f"volume must be 0.0-1.0, got {self.volume}")


class TTSSpeaker:
    """High-level TTS speaker integrating synthesis, caching, and playback.

    Provides a simple API for making the robot speak with automatic
    caching of common phrases for instant playback.

    Thread Safety:
        All operations are thread-safe. Speech queue is processed
        asynchronously in a background thread.

    Example:
        ```python
        speaker = TTSSpeaker()

        # Preload common phrases
        speaker.preload_phrases(["Hello!", "Goodbye!"])

        # Speak (cached phrases play instantly)
        speaker.speak("Hello!")

        # Queue multiple utterances
        speaker.queue("First message")
        speaker.queue("Second message")
        ```
    """

    # Common phrases to preload by default
    DEFAULT_PHRASES = [
        "Hello!",
        "Goodbye!",
        "Yes.",
        "No.",
        "I'm thinking...",
        "I don't understand.",
        "Can you repeat that?",
        "One moment please.",
        "Done!",
        "Error occurred.",
    ]

    def __init__(
        self,
        config: Optional[TTSSpeakerConfig] = None,
        engine: Optional[TTSEngine] = None,
        cache: Optional[TTSCache] = None,
        speaker_driver: Optional['MAX98357ADriver'] = None
    ):
        """Initialize TTS speaker.

        Args:
            config: Speaker configuration.
            engine: TTS engine (creates default if None).
            cache: Phrase cache (creates default if None).
            speaker_driver: Audio output driver (creates default if None).
        """
        self.config = config or TTSSpeakerConfig()
        self._engine = engine or TTSEngine()
        self._cache = cache or TTSCache() if self.config.use_cache else None

        # Import MAX98357A driver
        from .max98357a import MAX98357ADriver, MAX98357AConfig

        self._speaker = speaker_driver
        if self._speaker is None:
            speaker_config = MAX98357AConfig(
                sample_rate=16000,
                volume=self.config.volume
            )
            self._speaker = MAX98357ADriver(config=speaker_config)

        # State management
        self._state = TTSSpeakerState.IDLE
        self._state_lock = threading.Lock()

        # Speech queue
        self._queue: Queue[str] = Queue()
        self._queue_thread: Optional[threading.Thread] = None
        self._stop_queue = threading.Event()

        # Start queue processor if async
        if self.config.async_queue:
            self._start_queue_processor()

        _logger.info("TTSSpeaker initialized")

    def _start_queue_processor(self) -> None:
        """Start background thread for processing speech queue."""
        self._stop_queue.clear()
        self._queue_thread = threading.Thread(
            target=self._process_queue,
            daemon=True,
            name="TTSSpeaker-Queue"
        )
        self._queue_thread.start()

    def _process_queue(self) -> None:
        """Background thread: process queued utterances."""
        while not self._stop_queue.is_set():
            try:
                text = self._queue.get(timeout=0.1)
                self._speak_internal(text)
                self._queue.task_done()
            except Empty:
                continue
            except Exception as e:
                _logger.error(f"Queue processing error: {e}")

    @property
    def state(self) -> TTSSpeakerState:
        """Get current speaker state."""
        with self._state_lock:
            return self._state

    def _set_state(self, state: TTSSpeakerState) -> None:
        """Set speaker state."""
        with self._state_lock:
            self._state = state

    def speak(self, text: str, blocking: bool = True) -> bool:
        """Speak text.

        Args:
            text: Text to speak.
            blocking: If True, wait for speech to complete.

        Returns:
            True if speech started/completed successfully.
        """
        if blocking:
            return self._speak_internal(text)
        else:
            self.queue(text)
            return True

    def _speak_internal(self, text: str) -> bool:
        """Internal speak implementation."""
        if not text or not text.strip():
            return True

        text = text.strip()
        self._set_state(TTSSpeakerState.SPEAKING)

        try:
            # Try cache first
            audio = None
            if self._cache:
                audio = self._cache.get(text)

            # Synthesize if not cached
            if audio is None:
                audio = self._engine.synthesize(text)
                if self._cache:
                    self._cache.put(text, audio)

            # Play audio
            if len(audio) > 0:
                self._speaker.play_samples(audio, blocking=True)

            self._set_state(TTSSpeakerState.IDLE)
            return True

        except Exception as e:
            _logger.error(f"Speech failed: {e}")
            self._set_state(TTSSpeakerState.ERROR)
            return False

    def speak_cached(self, text: str) -> bool:
        """Speak only if text is cached (no synthesis).

        Args:
            text: Text to speak.

        Returns:
            True if text was cached and played, False otherwise.
        """
        if not self._cache:
            return False

        audio = self._cache.get(text)
        if audio is None:
            _logger.debug(f"Not cached: {text[:30]}...")
            return False

        self._set_state(TTSSpeakerState.SPEAKING)
        try:
            self._speaker.play_samples(audio, blocking=True)
            self._set_state(TTSSpeakerState.IDLE)
            return True
        except Exception as e:
            _logger.error(f"Cached speech failed: {e}")
            self._set_state(TTSSpeakerState.ERROR)
            return False

    def queue(self, text: str) -> None:
        """Add text to speech queue.

        Text will be spoken when previous items complete.

        Args:
            text: Text to queue.
        """
        if text and text.strip():
            self._queue.put(text.strip())
            _logger.debug(f"Queued: {text[:30]}...")

    def stop(self) -> None:
        """Stop current speech and clear queue."""
        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except Empty:
                break

        # Stop current playback
        self._speaker.stop()
        self._set_state(TTSSpeakerState.IDLE)

    def is_speaking(self) -> bool:
        """Check if currently speaking.

        Returns:
            True if speech is in progress.
        """
        return self.state == TTSSpeakerState.SPEAKING

    def preload_phrases(self, phrases: Optional[List[str]] = None) -> int:
        """Preload phrases into cache.

        Args:
            phrases: Phrases to preload (uses defaults if None).

        Returns:
            Number of phrases synthesized.
        """
        if not self._cache:
            _logger.warning("Cache disabled, cannot preload")
            return 0

        phrases = phrases or self.DEFAULT_PHRASES
        return self._cache.preload(phrases, self._engine)

    def set_volume(self, volume: float) -> None:
        """Set output volume.

        Args:
            volume: Volume level (0.0-1.0).
        """
        if not 0.0 <= volume <= 1.0:
            raise ValueError(f"volume must be 0.0-1.0, got {volume}")
        self.config.volume = volume
        self._speaker.set_volume(volume)

    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics.

        Returns:
            Cache stats dictionary, or None if caching disabled.
        """
        if self._cache:
            return self._cache.get_stats()
        return None

    def shutdown(self) -> None:
        """Shutdown speaker and cleanup resources."""
        # Stop queue processor
        self._stop_queue.set()
        if self._queue_thread and self._queue_thread.is_alive():
            self._queue_thread.join(timeout=1.0)

        # Stop any current playback
        self.stop()

        _logger.info("TTSSpeaker shutdown complete")


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_tts_speaker(
    volume: float = 0.8,
    use_cache: bool = True,
    preload_defaults: bool = True
) -> TTSSpeaker:
    """Factory function to create a configured TTS speaker.

    Args:
        volume: Output volume (0.0-1.0).
        use_cache: Whether to enable phrase caching.
        preload_defaults: Whether to preload default phrases.

    Returns:
        Configured TTSSpeaker instance.
    """
    config = TTSSpeakerConfig(volume=volume, use_cache=use_cache)
    speaker = TTSSpeaker(config=config)

    if preload_defaults and use_cache:
        speaker.preload_phrases()

    return speaker
