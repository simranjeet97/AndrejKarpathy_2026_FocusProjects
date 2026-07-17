from typing import Any, Dict, List, NamedTuple
import structlog
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

logger = structlog.get_logger()


class ScrubResult(NamedTuple):
    scrubbed_text: str
    entities_found: List[str]


# Initialize engines at module load to avoid reloading models on every call
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()


def scrub(text: str) -> ScrubResult:
    """
    Scrubs credit cards, emails, phone numbers, and SSNs from text.
    Replaces sensitive data with [ENTITY_TYPE_REDACTED] flags.
    """
    if not text:
        return ScrubResult("", [])

    # 1. Analyze text for specific PII entities
    target_entities = ["CREDIT_CARD", "EMAIL_ADDRESS", "PHONE_NUMBER", "US_SSN"]
    analyzer_results = analyzer.analyze(
        text=text,
        language="en",
        entities=target_entities
    )

    # 2. Define custom anonymization redaction tokens
    operators = {
        "CREDIT_CARD": OperatorConfig("replace", {"new_value": "[CARD_REDACTED]"}),
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL_REDACTED]"}),
        "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[PHONE_REDACTED]"}),
        "US_SSN": OperatorConfig("replace", {"new_value": "[SSN_REDACTED]"}),
    }

    # 3. Anonymize the text
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=analyzer_results,
        operators=operators
    )

    entities_found = [res.entity_type for res in analyzer_results]

    # Log PII occurrences anonymously
    if entities_found:
        logger.info(
            "PII entities scrubbed from text",
            entities_count=len(entities_found),
            entity_types=list(set(entities_found))
        )

    return ScrubResult(
        scrubbed_text=anonymized_result.text,
        entities_found=entities_found
    )


def scrub_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Recursively scrubs PII from a list of conversational messages.
    Supports both plain string contents and list-of-block structures.
    """
    scrubbed_list = []
    for msg in messages:
        msg_copy = msg.copy()
        content = msg.get("content")

        if isinstance(content, str):
            res = scrub(content)
            msg_copy["content"] = res.scrubbed_text
        elif isinstance(content, list):
            new_content = []
            for block in content:
                block_copy = block.copy()
                # Check for standard text blocks
                if "text" in block_copy and isinstance(block_copy["text"], str):
                    res = scrub(block_copy["text"])
                    block_copy["text"] = res.scrubbed_text
                # Check for tool results or nested content strings
                elif "content" in block_copy and isinstance(block_copy["content"], str):
                    res = scrub(block_copy["content"])
                    block_copy["content"] = res.scrubbed_text
                new_content.append(block_copy)
            msg_copy["content"] = new_content

        scrubbed_list.append(msg_copy)
    return scrubbed_list
