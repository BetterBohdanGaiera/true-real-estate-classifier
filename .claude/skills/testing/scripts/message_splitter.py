"""
Message Splitter - Intelligently splits long responses into natural message chunks.

This utility splits long text responses into multiple shorter messages that feel
natural, respecting sentence boundaries and preserving Russian text patterns.

Used by conversation simulation to generate realistic multi-message bursts
that mimic how real users type in messaging apps like Telegram.
"""

import re
from typing import List


# =============================================================================
# Russian Abbreviation Patterns
# =============================================================================

# Common Russian abbreviations containing INTERNAL periods that should NOT cause splits
# These are abbreviations where the period is NOT at the end of a sentence
# Pattern: abbreviation followed by lowercase letter or number (not end of sentence)
RUSSIAN_ABBREVIATIONS_INTERNAL = [
    r"т\.е\.\s+(?=[a-zа-яё0-9])",     # т.е. followed by lowercase (mid-sentence)
    r"т\.к\.\s+(?=[a-zа-яё0-9])",     # т.к. followed by lowercase
    r"т\.н\.\s+(?=[a-zа-яё0-9])",     # т.н. followed by lowercase
    r"т\.п\.\s+(?=[a-zа-яё0-9])",     # т.п. followed by lowercase
    r"и т\.д\.\s+(?=[a-zа-яё0-9])",   # и т.д. followed by lowercase
    r"и т\.п\.\s+(?=[a-zа-яё0-9])",   # и т.п. followed by lowercase
    r"др\.\s+(?=[a-zа-яё0-9])",       # др. followed by lowercase
    r"пр\.\s+(?=[a-zа-яё0-9])",       # пр. followed by lowercase
    r"см\.\s+(?=[a-zа-яё0-9])",       # см. followed by lowercase
    r"ср\.\s+(?=[a-zа-яё0-9])",       # ср. followed by lowercase
    r"напр\.\s+(?=[a-zа-яё0-9])",     # напр. followed by lowercase
    r"г\.\s+(?=[a-zа-яё0-9])",        # г. followed by lowercase
    r"гг\.\s+(?=[a-zа-яё0-9])",       # гг. followed by lowercase
    r"в\.\s+(?=[a-zа-яё0-9])",        # в. followed by lowercase
    r"вв\.\s+(?=[a-zа-яё0-9])",       # вв. followed by lowercase
    r"н\.э\.\s+(?=[a-zа-яё0-9])",     # н.э. followed by lowercase
    r"до н\.э\.\s+(?=[a-zа-яё0-9])",  # до н.э. followed by lowercase
    r"руб\.\s+(?=[a-zа-яё0-9])",      # руб. followed by lowercase
    r"коп\.\s+(?=[a-zа-яё0-9])",      # коп. followed by lowercase
    r"млн\.\s+(?=[a-zа-яё0-9])",      # млн. followed by lowercase
    r"млрд\.\s+(?=[a-zа-яё0-9])",     # млрд. followed by lowercase
    r"тыс\.\s+(?=[a-zа-яё0-9])",      # тыс. followed by lowercase
    r"кв\.\s+(?=[a-zа-яё0-9])",       # кв. followed by lowercase
    r"м\.\s+(?=[a-zа-яё0-9])",        # м. followed by lowercase
    r"км\.\s+(?=[a-zа-яё0-9])",       # км. followed by lowercase
    r"ул\.\s+(?=[a-zа-яё0-9])",       # ул. followed by lowercase
    r"пер\.\s+(?=[a-zа-яё0-9])",      # пер. followed by lowercase
    r"д\.\s+(?=[a-zа-яё0-9])",        # д. followed by lowercase
    r"стр\.\s+(?=[a-zа-яё0-9])",      # стр. followed by lowercase
]

# Simple abbreviation patterns (just the abbreviation text)
SIMPLE_ABBREVIATIONS = [
    "т.е.", "т.к.", "т.н.", "т.п.", "и т.д.", "и т.п.",
    "др.", "пр.", "см.", "ср.", "напр.",
    "г.", "гг.", "в.", "вв.", "н.э.", "до н.э.",
    "руб.", "коп.", "млн.", "млрд.", "тыс.",
    "кв.", "м.", "км.", "ул.", "пер.", "д.", "стр.",
]

# URL pattern to preserve - URLs should never be split
# Note: Avoid capturing trailing sentence punctuation (., !, ?) that may end the URL
# We'll match URLs but strip trailing punctuation if followed by whitespace+capital
URL_PATTERN = r'https?://[^\s]+'


# =============================================================================
# Core Splitting Functions
# =============================================================================

# Special marker for abbreviation periods (won't be seen as sentence boundary)
_ABBREV_PERIOD_MARKER = "\x00ABBREV_DOT\x00"


def _protect_special_patterns(text: str) -> tuple[str, dict[str, str]]:
    """
    Replace URLs with placeholders and mark abbreviation periods specially.

    For abbreviations:
    - If followed by lowercase letter, replace period with marker (mid-sentence)
    - If followed by capital letter or end of text, keep period (sentence boundary)

    Args:
        text: Original text

    Returns:
        Tuple of (modified text, mapping of URL placeholders to originals)
    """
    protected = text
    url_replacements: dict[str, str] = {}
    counter = 0

    # Protect URLs first (most important - they have many dots)
    # Handle trailing punctuation: if URL ends with .!? followed by space+capital,
    # the punctuation is a sentence boundary, not part of the URL
    url_matches = re.findall(URL_PATTERN, protected)
    for url in url_matches:
        # Check if URL has trailing sentence punctuation
        actual_url = url
        trailing_punct = ""

        if url and url[-1] in '.!?':
            # Find position of this URL in the text
            url_pos = protected.find(url)
            if url_pos >= 0:
                after_url = url_pos + len(url)
                # Check what follows
                if after_url < len(protected):
                    # Skip whitespace
                    k = after_url
                    while k < len(protected) and protected[k] in ' \t':
                        k += 1
                    # If followed by capital letter, the trailing punct is sentence-ending
                    if k < len(protected) and (protected[k].isupper() or protected[k] in '"\'([{'):
                        trailing_punct = url[-1]
                        actual_url = url[:-1]
                elif after_url >= len(protected):
                    # End of text - trailing punct is sentence-ending
                    trailing_punct = url[-1]
                    actual_url = url[:-1]

        placeholder = f"__URL_{counter}__"
        # Replace the actual URL part (without trailing punct)
        if trailing_punct:
            protected = protected.replace(url, placeholder + trailing_punct, 1)
        else:
            protected = protected.replace(url, placeholder, 1)
        url_replacements[placeholder] = actual_url
        counter += 1

    # Handle abbreviations: replace their internal periods with markers
    # But keep the final period if it ends a sentence (followed by capital)
    # Sort by length (longest first) to avoid partial matches
    sorted_abbrevs = sorted(SIMPLE_ABBREVIATIONS, key=len, reverse=True)

    for abbrev in sorted_abbrevs:
        # Find all occurrences of this abbreviation
        pattern = re.escape(abbrev)
        idx = 0
        while True:
            match = re.search(pattern, protected[idx:], re.IGNORECASE)
            if not match:
                break

            start = idx + match.start()
            end = idx + match.end()
            matched_text = protected[start:end]

            # Look at what follows the abbreviation
            rest_start = end
            # Skip whitespace
            while rest_start < len(protected) and protected[rest_start] in ' \t':
                rest_start += 1

            # Determine if this abbreviation ends a sentence
            ends_sentence = False
            if rest_start >= len(protected):
                # End of text
                ends_sentence = True
            elif protected[rest_start] == '\n':
                # Newline
                ends_sentence = True
            elif protected[rest_start].isupper():
                # Capital letter follows
                ends_sentence = True
            elif protected[rest_start:rest_start+2] == '__':
                # Placeholder follows (likely URL) - treat as sentence end
                ends_sentence = True

            if ends_sentence:
                # Keep the abbreviation as-is (the final period will trigger split)
                # But we need to protect internal periods
                # E.g., "т.е." has one internal period
                parts = matched_text.split('.')
                if len(parts) > 2:
                    # Multiple internal periods - replace all but last with markers
                    new_text = _ABBREV_PERIOD_MARKER.join(parts[:-1]) + '.' + parts[-1]
                    protected = protected[:start] + new_text + protected[end:]
                    # Adjust for length change
                    length_diff = len(new_text) - len(matched_text)
                    idx = end + length_diff
                else:
                    idx = end
            else:
                # Mid-sentence: replace ALL periods with markers
                new_text = matched_text.replace('.', _ABBREV_PERIOD_MARKER)
                protected = protected[:start] + new_text + protected[end:]
                # Adjust for length change
                length_diff = len(new_text) - len(matched_text)
                idx = end + length_diff

    return protected, url_replacements


def _restore_markers(text: str) -> str:
    """
    Restore abbreviation period markers back to periods.

    Args:
        text: Text with markers

    Returns:
        Text with periods restored
    """
    return text.replace(_ABBREV_PERIOD_MARKER, '.')


def _restore_placeholders(text: str, replacements: dict[str, str]) -> str:
    """
    Restore protected patterns from placeholders.

    Args:
        text: Text with placeholders
        replacements: Mapping of placeholders to originals

    Returns:
        Text with original patterns restored
    """
    result = text
    for placeholder, original in replacements.items():
        result = result.replace(placeholder, original)
    return result


def _split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences at proper sentence boundaries.

    Handles sentence-ending punctuation (., !, ?) and multiple punctuation
    marks (!!, ?!, etc.). URLs should be pre-protected with placeholders,
    and abbreviation periods should be marked.

    Args:
        text: Text to split (special patterns should be protected/marked)

    Returns:
        List of sentences
    """
    if not text:
        return []

    sentences = []
    current_sentence = ""
    i = 0

    while i < len(text):
        char = text[i]
        current_sentence += char

        # Check for sentence-ending punctuation
        if char in '.!?':
            # Look ahead to gather multiple punctuation marks
            j = i + 1
            while j < len(text) and text[j] in '.!?':
                current_sentence += text[j]
                j += 1

            # Now check what follows the punctuation
            # Skip whitespace to find the next non-space character
            k = j
            while k < len(text) and text[k] in ' \t':
                k += 1

            # Determine if this is a sentence boundary
            is_sentence_end = False

            if k >= len(text):
                # End of text - definitely end of sentence
                is_sentence_end = True
            elif text[k] == '\n':
                # Newline after punctuation - sentence end
                is_sentence_end = True
            elif k < len(text):
                next_char = text[k]
                # After !? always split
                # After . split if followed by capital letter or quote/bracket
                if char in '!?':
                    is_sentence_end = True
                elif next_char.isupper() or next_char in '"\'([{':
                    is_sentence_end = True
                elif next_char == '_' and text[k:k+2] == '__':
                    # Placeholder follows - this could be URL starting new sentence
                    is_sentence_end = True
                else:
                    # Lowercase after period - not a sentence boundary
                    is_sentence_end = False

            if is_sentence_end:
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                current_sentence = ""
                i = j  # Move past the punctuation
            else:
                i = j  # Move past punctuation but continue sentence
        else:
            i += 1

    # Handle any remaining text
    if current_sentence.strip():
        sentences.append(current_sentence.strip())

    return sentences


def _merge_sentences_to_parts(sentences: List[str], max_parts: int) -> List[str]:
    """
    Merge sentences into the desired number of parts.

    Distributes sentences evenly across parts while keeping
    related sentences together when possible.

    Args:
        sentences: List of sentences to merge
        max_parts: Maximum number of parts to create

    Returns:
        List of message parts
    """
    if not sentences:
        return []

    num_sentences = len(sentences)

    # If we have fewer sentences than max_parts, return them as-is
    if num_sentences <= max_parts:
        return sentences

    # Calculate how many sentences per part
    sentences_per_part = num_sentences / max_parts

    parts = []
    current_part_sentences = []
    current_count = 0
    target_count = sentences_per_part

    for i, sentence in enumerate(sentences):
        current_part_sentences.append(sentence)
        current_count += 1

        # Check if we should finalize this part
        # We finalize when we've reached the target OR we're at the last sentence
        should_finalize = (
            current_count >= target_count or
            i == num_sentences - 1 or
            len(parts) == max_parts - 1  # Last allowed part, collect all remaining
        )

        if should_finalize and current_part_sentences:
            # Join sentences with space
            parts.append(" ".join(current_part_sentences))
            current_part_sentences = []
            # Update target for next part
            remaining_sentences = num_sentences - (i + 1)
            remaining_parts = max_parts - len(parts)
            if remaining_parts > 0:
                target_count = remaining_sentences / remaining_parts
                current_count = 0

    # Handle any remaining sentences
    if current_part_sentences:
        if parts and len(parts) < max_parts:
            parts.append(" ".join(current_part_sentences))
        elif parts:
            # Append to the last part
            parts[-1] += " " + " ".join(current_part_sentences)
        else:
            parts.append(" ".join(current_part_sentences))

    return parts[:max_parts]


# =============================================================================
# Main API
# =============================================================================

def split_response_naturally(text: str, max_parts: int = 5) -> List[str]:
    """
    Split text into multiple natural message parts.

    Handles:
    - Sentence boundaries (., !, ?)
    - Russian abbreviations (т.е., и т.д., т.п., т.к., и т.п.)
    - URL preservation
    - Empty/whitespace input

    Args:
        text: The text to split
        max_parts: Maximum number of parts (default 5, always capped at 5)

    Returns:
        List of 1-5 message strings

    Examples:
        >>> split_response_naturally("Hello. World.")
        ['Hello.', 'World.']

        >>> split_response_naturally("Short")
        ['Short']

        >>> split_response_naturally("Это т.е. важно. Понял?")
        ['Это т.е. важно.', 'Понял?']
    """
    # Cap max_parts at 5
    max_parts = min(max_parts, 5)

    # Handle empty/whitespace input
    if not text or not text.strip():
        return []

    text = text.strip()

    # Very short text - return as single message
    if len(text) < 20:
        return [text]

    # Step 1: Protect special patterns (URLs, abbreviation periods) from splitting
    protected_text, url_replacements = _protect_special_patterns(text)

    # Step 2: Split into sentences
    sentences = _split_into_sentences(protected_text)

    # Step 3: Restore markers and placeholders in each sentence
    sentences = [_restore_markers(s) for s in sentences]
    sentences = [_restore_placeholders(s, url_replacements) for s in sentences]

    # Filter out empty sentences
    sentences = [s for s in sentences if s.strip()]

    # If no valid sentences found, return original text
    if not sentences:
        return [text]

    # Step 4: Merge sentences into parts
    parts = _merge_sentences_to_parts(sentences, max_parts)

    # Clean up parts
    parts = [p.strip() for p in parts if p.strip()]

    return parts if parts else [text]


# =============================================================================
# Self-Test Entry Point
# =============================================================================

if __name__ == "__main__":
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    console = Console()

    def run_test(name: str, text: str, expected_count: int = None,
                 contains: List[str] = None, max_parts: int = 5) -> bool:
        """Run a single test case."""
        result = split_response_naturally(text, max_parts)

        passed = True
        issues = []

        # Check count if specified
        if expected_count is not None and len(result) != expected_count:
            passed = False
            issues.append(f"Expected {expected_count} parts, got {len(result)}")

        # Check contains if specified
        if contains:
            full_text = " ".join(result)
            for term in contains:
                if term not in full_text:
                    passed = False
                    issues.append(f"Missing expected term: '{term}'")

        # Check max parts limit
        if len(result) > max_parts:
            passed = False
            issues.append(f"Exceeded max_parts ({max_parts}): got {len(result)}")

        # Display result
        status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
        console.print(f"\n{status} - {name}")
        console.print(f"  Input: {text[:80]}{'...' if len(text) > 80 else ''}")
        console.print(f"  Parts ({len(result)}):")
        for i, part in enumerate(result, 1):
            console.print(f"    [{i}] {part[:60]}{'...' if len(part) > 60 else ''}")

        if issues:
            for issue in issues:
                console.print(f"  [red]Issue: {issue}[/red]")

        return passed

    # Run all tests
    console.print(Panel.fit(
        "[bold]Message Splitter Self-Test[/bold]",
        border_style="blue"
    ))

    all_passed = True

    # Test 1: Basic sentence splitting
    all_passed &= run_test(
        "Basic sentence splitting",
        "Hello. World. How are you?",
        expected_count=3
    )

    # Test 2: Exclamation and question marks
    all_passed &= run_test(
        "Mixed punctuation",
        "Wow! That's amazing. Really? Yes!",
        expected_count=4
    )

    # Test 3: Russian abbreviations - т.е.
    all_passed &= run_test(
        "Russian abbreviation т.е.",
        "Это важно, т.е. нужно обратить внимание. Понял?",
        expected_count=2,
        contains=["т.е."]
    )

    # Test 4: Russian abbreviations - и т.д.
    all_passed &= run_test(
        "Russian abbreviation и т.д.",
        "Есть виллы, апартаменты и т.д. Выбор большой.",
        expected_count=2,
        contains=["и т.д."]
    )

    # Test 5: Russian abbreviation т.п.
    all_passed &= run_test(
        "Russian abbreviation т.п.",
        "Можно купить виллу, квартиру и т.п. Все доступно.",
        expected_count=2,
        contains=["т.п."]
    )

    # Test 6: Russian abbreviation т.к.
    all_passed &= run_test(
        "Russian abbreviation т.к.",
        "Это выгодно, т.к. цены растут. Инвестируйте сейчас!",
        expected_count=2,
        contains=["т.к."]
    )

    # Test 7: Russian abbreviation и т.п.
    all_passed &= run_test(
        "Russian abbreviation и т.п.",
        "Бассейн, сад и т.п. включены. Отличное предложение!",
        expected_count=2,
        contains=["и т.п."]
    )

    # Test 8: URL preservation
    all_passed &= run_test(
        "URL preservation",
        "Посмотрите наш сайт https://example.com/property.html для деталей. Там все объекты.",
        expected_count=2,
        contains=["https://example.com/property.html"]
    )

    # Test 9: Multiple URLs
    all_passed &= run_test(
        "Multiple URLs",
        "Сайт: https://site1.com. Фото: https://photos.site2.com/gallery.html. Смотрите!",
        expected_count=3,
        contains=["https://site1.com", "https://photos.site2.com/gallery.html"]
    )

    # Test 10: Empty input
    all_passed &= run_test(
        "Empty input",
        "",
        expected_count=0
    )

    # Test 11: Whitespace-only input
    all_passed &= run_test(
        "Whitespace-only input",
        "   \n\t  ",
        expected_count=0
    )

    # Test 12: Very short text (no split needed)
    all_passed &= run_test(
        "Very short text",
        "Привет!",
        expected_count=1
    )

    # Test 13: Max 5 parts limit with many sentences
    all_passed &= run_test(
        "Max 5 parts with 10 sentences",
        "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten.",
        max_parts=5
    )
    # Additional check that it doesn't exceed 5
    result_10 = split_response_naturally("One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten.", 5)
    if len(result_10) > 5:
        all_passed = False
        console.print("[red]  FAIL: Exceeded 5 parts limit[/red]")
    else:
        console.print(f"  [green]Confirmed: {len(result_10)} parts (max 5)[/green]")

    # Test 14: Single sentence (no split)
    all_passed &= run_test(
        "Single sentence",
        "This is a single long sentence without any punctuation that ends here",
        expected_count=1
    )

    # Test 15: Complex Russian text
    all_passed &= run_test(
        "Complex Russian text",
        "Привет! Я помогу вам с недвижимостью на Бали. У нас есть виллы, т.е. отдельные дома. А также апартаменты, коттеджи и т.д. Цены от $100к. Интересно?",
        contains=["т.е.", "и т.д."]
    )

    # Test 16: Text without punctuation
    all_passed &= run_test(
        "Text without punctuation",
        "This is text without punctuation marks at the end",
        expected_count=1
    )

    # Test 17: Multiple punctuation marks
    all_passed &= run_test(
        "Multiple punctuation",
        "What?! That's crazy!! Really...?",
        expected_count=3
    )

    # Test 18: Mixed Russian and English
    all_passed &= run_test(
        "Mixed Russian and English",
        "Привет! Hello. Как дела? How are you?",
        expected_count=4
    )

    # Final summary
    console.print()
    if all_passed:
        console.print(Panel.fit(
            "[bold green]All tests passed![/bold green]",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            "[bold red]Some tests failed![/bold red]",
            border_style="red"
        ))

    # Assert for CI/CD
    assert all_passed, "Not all tests passed"
