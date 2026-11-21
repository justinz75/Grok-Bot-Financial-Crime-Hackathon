"""Text folding shared by the name, country and date rules."""
import unicodedata

# Letters that Unicode decomposition leaves alone but that are plain accents in names.
_SPECIAL = str.maketrans({
    "ß": "ss", "ẞ": "SS", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L",
    "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE", "ı": "i", "þ": "th", "Þ": "TH",
    "ð": "d", "Ð": "D", "ħ": "h", "Ħ": "H", "ŧ": "t", "Ŧ": "T", "ŋ": "n", "Ŋ": "N",
})

APOSTROPHES = "'’‘ʼ`´"


def fold(text):
    """Lowercase and strip accents: 'Jérôme' -> 'jerome', 'Paweł' -> 'pawel'."""
    text = str(text).translate(_SPECIAL)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


def words(folded):
    """Split folded text into letter/digit runs. Apostrophes join (o'brien -> obrien);
    every other punctuation mark separates."""
    out, cur = [], []
    for ch in folded:
        if ch.isalnum() or unicodedata.category(ch)[0] == "M":
            cur.append(ch)
        elif ch in APOSTROPHES:
            continue
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out
