def extract_emails(text):
    import re; return re.findall(r"\w+@\w+", text)
