import pytest
from src.policy.pii_scrubber import scrub, scrub_messages


def test_scrub_pii_entities() -> None:
    # 1. Test credit cards
    text_cc = "My card number is 4111 1111 1111 1111."
    res_cc = scrub(text_cc)
    assert "[CARD_REDACTED]" in res_cc.scrubbed_text
    assert "CREDIT_CARD" in res_cc.entities_found

    # 2. Test email addresses
    text_email = "Please contact me at test@example.com."
    res_email = scrub(text_email)
    assert "[EMAIL_REDACTED]" in res_email.scrubbed_text
    assert "EMAIL_ADDRESS" in res_email.entities_found

    # 3. Test phone numbers
    text_phone = "My phone number is 555-555-0199."
    res_phone = scrub(text_phone)
    assert "[PHONE_REDACTED]" in res_phone.scrubbed_text
    assert "PHONE_NUMBER" in res_phone.entities_found

    # 4. Test SSN
    text_ssn = "My SSN is 456-78-9012."
    res_ssn = scrub(text_ssn)
    assert "[SSN_REDACTED]" in res_ssn.scrubbed_text
    assert "US_SSN" in res_ssn.entities_found


def test_scrub_no_pii() -> None:
    text_safe = "Hello, I have a question about my package."
    res_safe = scrub(text_safe)
    assert res_safe.scrubbed_text == text_safe
    assert len(res_safe.entities_found) == 0


def test_scrub_messages() -> None:
    messages = [
        {"role": "user", "content": "My email is test@example.com."},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Sending confirmation to test@example.com."}
            ]
        }
    ]
    
    scrubbed = scrub_messages(messages)
    
    # Verify string content scrubbing
    assert "[EMAIL_REDACTED]" in scrubbed[0]["content"]
    assert "test@example.com" not in scrubbed[0]["content"]
    
    # Verify list content scrubbing
    assert "[EMAIL_REDACTED]" in scrubbed[1]["content"][0]["text"]
    assert "test@example.com" not in scrubbed[1]["content"][0]["text"]
