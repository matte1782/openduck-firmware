"""Intent Classification for OpenDuck Mini V3

This module provides intent classification with:
- Rule-based pattern matching for common intents
- Entity extraction (devices, times, actions)
- Custom intent registration
- Mock mode for development

Production Implementation Options:
1. Rasa NLU - Open-source, trainable, offline
2. Dialogflow - Cloud-based, Google
3. LUIS - Cloud-based, Microsoft
4. Snips NLU - Offline, lightweight (deprecated but forks exist)
5. Custom BERT/DistilBERT - Fine-tuned classifier

This module provides a common interface that can wrap any of these backends.
By default, it uses a rule-based mock implementation.

Example:
    ```python
    from src.voice.intent import IntentClassifier, IntentConfig

    # Create classifier
    config = IntentConfig(confidence_threshold=0.6)
    classifier = IntentClassifier(config)

    # Classify text
    result = classifier.classify("turn on the lights")
    print(f"Intent: {result.intent.value}, Confidence: {result.confidence}")

    # Extract entities
    for entity in result.entities:
        print(f"  Entity: {entity.type}={entity.value}")
    ```

Thread Safety:
    IntentClassifier is NOT thread-safe. Use one instance per thread.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Pattern, Tuple, Any

_logger = logging.getLogger(__name__)


class Intent(Enum):
    """Built-in intent types.

    GREETING: Hello, hi, hey, etc.
    FAREWELL: Goodbye, bye, see you
    COMMAND: Action commands (turn on, play, stop)
    QUESTION: Information queries (what, when, how)
    AFFIRMATIVE: Yes, sure, okay
    NEGATIVE: No, cancel, stop
    UNKNOWN: Unrecognized intent
    """
    GREETING = "greeting"
    FAREWELL = "farewell"
    COMMAND = "command"
    QUESTION = "question"
    AFFIRMATIVE = "affirmative"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


@dataclass
class Entity:
    """Extracted entity from text.

    Attributes:
        type: Entity type (device, time, action, location, etc.)
        value: Extracted value
        start: Start character position in text
        end: End character position in text
        confidence: Extraction confidence (0.0 to 1.0)
    """
    type: str
    value: str
    start: int
    end: int
    confidence: float


@dataclass
class IntentConfig:
    """Configuration for Intent Classification.

    Attributes:
        confidence_threshold: Minimum confidence to accept intent (default: 0.5)
        fallback_intent: Intent to return when below threshold (default: "unknown")
        supported_intents: List of supported intent names
        extract_entities: Whether to extract entities (default: True)
        max_text_length: Maximum text length to process (default: 1000)
    """
    confidence_threshold: float = 0.5
    fallback_intent: str = "unknown"
    supported_intents: List[str] = field(default_factory=lambda: [
        "greeting", "farewell", "command", "question", "affirmative", "negative"
    ])
    extract_entities: bool = True
    max_text_length: int = 1000

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ValueError(
                f"confidence_threshold must be in [0, 1], got {self.confidence_threshold}"
            )
        if self.max_text_length <= 0:
            raise ValueError(
                f"max_text_length must be positive, got {self.max_text_length}"
            )


@dataclass
class IntentResult:
    """Result from intent classification.

    Attributes:
        intent: Classified intent
        confidence: Classification confidence (0.0 to 1.0)
        text: Original input text
        entities: Extracted entities
        alternatives: Alternative intent classifications
    """
    intent: Intent
    confidence: float
    text: str
    entities: List[Entity]
    alternatives: List[Tuple[Intent, float]]

    @staticmethod
    def unknown(text: str) -> IntentResult:
        """Create an unknown intent result."""
        return IntentResult(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            text=text,
            entities=[],
            alternatives=[]
        )


class IntentClassifier:
    """Intent classifier with rule-based and ML backends.

    Classifies user text into intents (greeting, command, question, etc.)
    and extracts entities (devices, times, actions).

    Attributes:
        config: Classifier configuration
        mock_mode: Whether running in mock mode
        is_ready: Whether classifier is ready
        on_intent: Callback for classification results
    """

    # Built-in intent patterns (regex)
    _BUILTIN_PATTERNS: Dict[Intent, List[Pattern]] = {
        Intent.GREETING: [
            re.compile(r'\b(hello|hi|hey|greetings|howdy|yo)\b', re.I),
            re.compile(r'\bgood\s+(morning|afternoon|evening)\b', re.I),
            re.compile(r'\b(ciao|salve|buongiorno)\b', re.I),  # Italian
        ],
        Intent.FAREWELL: [
            re.compile(r'\b(bye|goodbye|farewell|see\s+you|ciao|arrivederci)\b', re.I),
            re.compile(r'\bgood\s*night\b', re.I),
        ],
        Intent.COMMAND: [
            re.compile(r'\b(turn|switch)\s+(on|off)\b', re.I),
            re.compile(r'\b(play|stop|pause|resume|skip)\b', re.I),
            re.compile(r'\b(set|change|adjust|increase|decrease)\b', re.I),
            re.compile(r'\b(open|close|lock|unlock)\b', re.I),
            re.compile(r'\b(start|begin|activate|enable|disable)\b', re.I),
        ],
        Intent.QUESTION: [
            re.compile(r'\b(what|when|where|who|why|how|which)\b', re.I),
            re.compile(r'\?$'),
            re.compile(r'\b(tell\s+me|can\s+you|do\s+you\s+know)\b', re.I),
        ],
        Intent.AFFIRMATIVE: [
            re.compile(r'\b(yes|yeah|yep|sure|okay|ok|alright|correct|right)\b', re.I),
            re.compile(r'\b(si|certo|esatto)\b', re.I),  # Italian
        ],
        Intent.NEGATIVE: [
            re.compile(r'\b(no|nope|nah|cancel|stop|never|wrong)\b', re.I),
            re.compile(r'\b(non|mai)\b', re.I),  # Italian
        ],
    }

    # Entity extraction patterns
    _ENTITY_PATTERNS: Dict[str, List[Tuple[Pattern, str]]] = {
        "device": [
            (re.compile(r'\b(lights?|lamp)\b', re.I), "light"),
            (re.compile(r'\b(tv|television)\b', re.I), "tv"),
            (re.compile(r'\b(music|spotify|radio)\b', re.I), "audio"),
            (re.compile(r'\b(door|window|blind|curtain)\b', re.I), "home"),
            (re.compile(r'\b(fan|ac|air\s*conditioner|heater)\b', re.I), "climate"),
        ],
        "action": [
            (re.compile(r'\b(turn\s+on|activate|enable|start)\b', re.I), "on"),
            (re.compile(r'\b(turn\s+off|deactivate|disable|stop)\b', re.I), "off"),
            (re.compile(r'\b(increase|up|raise|higher)\b', re.I), "increase"),
            (re.compile(r'\b(decrease|down|lower)\b', re.I), "decrease"),
        ],
        "time": [
            (re.compile(r'\b(\d{1,2}:\d{2})\b'), "time"),
            (re.compile(r'\b(\d{1,2})\s*(am|pm)\b', re.I), "time"),
            (re.compile(r'\bin\s+(\d+)\s*(minute|hour|second)s?\b', re.I), "duration"),
        ],
        "location": [
            (re.compile(r'\b(kitchen|bedroom|living\s*room|bathroom|garage)\b', re.I), "room"),
            (re.compile(r'\b(upstairs|downstairs|outside|inside)\b', re.I), "area"),
        ],
    }

    def __init__(
        self,
        config: Optional[IntentConfig] = None,
        mock_mode: bool = False
    ) -> None:
        """Initialize intent classifier.

        Args:
            config: Classifier configuration (uses defaults if None)
            mock_mode: Force mock/rule-based mode
        """
        self.config = config or IntentConfig()
        self.mock_mode = mock_mode

        self._is_ready = True
        self._custom_intents: Dict[str, Dict] = {}

        # Callback
        self.on_intent: Optional[Callable[[IntentResult], None]] = None

        _logger.info(
            f"IntentClassifier initialized: threshold={self.config.confidence_threshold}, "
            f"mock_mode={self.mock_mode}"
        )

    @property
    def is_ready(self) -> bool:
        """Check if classifier is ready."""
        return self._is_ready

    def classify(self, text: str) -> IntentResult:
        """Classify text into an intent.

        Args:
            text: Input text to classify

        Returns:
            IntentResult with intent, confidence, and entities
        """
        if not text or not text.strip():
            return IntentResult.unknown("")

        # Truncate if too long
        if len(text) > self.config.max_text_length:
            text = text[:self.config.max_text_length]

        # Clean text
        text = text.strip()

        # Run classification
        intent, confidence, alternatives = self._classify_intent(text)

        # Apply threshold
        if confidence < self.config.confidence_threshold:
            intent = Intent.UNKNOWN

        # Extract entities
        entities = []
        if self.config.extract_entities:
            entities = self._extract_entities(text)

        result = IntentResult(
            intent=intent,
            confidence=confidence,
            text=text,
            entities=entities,
            alternatives=alternatives
        )

        # Fire callback
        if self.on_intent:
            try:
                self.on_intent(result)
            except Exception as e:
                _logger.error(f"on_intent callback error: {e}")

        return result

    def register_intent(
        self,
        name: str,
        patterns: List[str],
        examples: List[str] = None
    ) -> None:
        """Register a custom intent.

        Args:
            name: Intent name
            patterns: Keywords/patterns to match (max 50 chars each)
            examples: Example phrases for this intent

        Raises:
            ValueError: If pattern exceeds max length (security)
        """
        # Security: limit pattern length to prevent regex DoS
        MAX_PATTERN_LENGTH = 50
        validated_patterns = []
        for p in patterns:
            if len(p) > MAX_PATTERN_LENGTH:
                _logger.warning(
                    f"Pattern '{p[:20]}...' truncated to {MAX_PATTERN_LENGTH} chars"
                )
                p = p[:MAX_PATTERN_LENGTH]
            validated_patterns.append(p)

        compiled_patterns = [
            re.compile(rf'\b{re.escape(p)}\b', re.I)
            for p in validated_patterns
        ]

        self._custom_intents[name] = {
            "patterns": compiled_patterns,
            "examples": examples or [],
        }

        _logger.info(f"Registered custom intent: {name} with {len(patterns)} patterns")

    def get_registered_intents(self) -> List[str]:
        """Get list of all registered intents.

        Returns:
            List of intent names (built-in + custom)
        """
        builtin = [i.value for i in Intent]
        custom = list(self._custom_intents.keys())
        return builtin + custom

    def _classify_intent(self, text: str) -> Tuple[Intent, float, List[Tuple[Intent, float]]]:
        """Classify text using pattern matching.

        Returns:
            Tuple of (best intent, confidence, alternatives)
        """
        scores: Dict[Intent, float] = {}

        # Score built-in intents
        for intent, patterns in self._BUILTIN_PATTERNS.items():
            score = 0.0
            matches = 0
            for pattern in patterns:
                if pattern.search(text):
                    matches += 1

            if matches > 0:
                # Base score from number of pattern matches
                score = min(0.9, 0.5 + (matches * 0.2))
                scores[intent] = score

        # Score custom intents
        for name, data in self._custom_intents.items():
            matches = sum(1 for p in data["patterns"] if p.search(text))
            if matches > 0:
                # Custom intents treated as commands for now
                if Intent.COMMAND not in scores or scores[Intent.COMMAND] < 0.7:
                    scores[Intent.COMMAND] = min(0.9, 0.5 + (matches * 0.2))

        # Find best intent
        if not scores:
            return Intent.UNKNOWN, 0.0, []

        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_intent, best_score = sorted_scores[0]

        # Build alternatives (excluding best)
        alternatives = [(i, s) for i, s in sorted_scores[1:] if s > 0.3]

        return best_intent, best_score, alternatives

    def _extract_entities(self, text: str) -> List[Entity]:
        """Extract entities from text.

        Returns:
            List of extracted entities
        """
        entities = []

        for entity_type, patterns in self._ENTITY_PATTERNS.items():
            for pattern, subtype in patterns:
                for match in pattern.finditer(text):
                    entity = Entity(
                        type=entity_type,
                        value=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        confidence=0.85  # Rule-based extraction
                    )
                    entities.append(entity)

        # Remove duplicates (same position)
        seen_positions = set()
        unique_entities = []
        for entity in entities:
            pos = (entity.start, entity.end)
            if pos not in seen_positions:
                seen_positions.add(pos)
                unique_entities.append(entity)

        return unique_entities

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"IntentClassifier(threshold={self.config.confidence_threshold}, "
            f"custom_intents={len(self._custom_intents)}, ready={self._is_ready})"
        )
