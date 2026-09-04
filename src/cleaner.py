import re
import unicodedata
from typing import Dict, List, Optional, Tuple

URL_RE = re.compile(r"https?://\S+|www\.\S+")
USER_RE = re.compile(r"(?i)(?<![\w/])u/[a-z0-9_-]+")
SUBR_RE = re.compile(r"(?i)(?<![\w/])r/[a-z0-9_]+")
CODE_RE = re.compile(r"```.*?```", re.S)
MD_FMT = re.compile(r"[*_~>#]+")
MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]+")
TOK_RE = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*|<url>|<user>|<subreddit>|<code>|<num>")

FUNC_WORDS = set(
    "the be to of and a in that have it for not on with as you do at this but his by from they we "
    "say her she or an will my one all would there their what so up out if about who get which go "
    "me when make can like no just him know take into year your good some could them see other than "
    "then now look only come its over think also back after use two how our work first well way even "
    "new want because any these give day most us is are was were been has had were not never no".split()
)


def clean_and_tokenize(
    raw: Optional[str],
    min_chars: int = 10,
    min_tokens: int = 3
) -> Tuple[List[str], Dict]:
    """Meaning-preserving cleaner + tokenizer per spec v0.2.0+.
    Preserves stopwords and negation words (not, never, no).
    Replaces URLs, user mentions, subreddit mentions, code blocks with tokens.
    Converts numbers > 4 digits to <num>.
    """
    if raw is None:
        return [], {"dropped": "null"}
    t = raw.strip()
    if t in ("[deleted]", "[removed]", "") or not t.strip():
        return [], {"dropped": "deleted_removed_empty"}
    
    t = unicodedata.normalize("NFKC", t)
    t = MD_LINK.sub(r"\1", t)
    t = MD_FMT.sub(" ", t)
    
    has_code = bool(CODE_RE.search(t))
    t = CODE_RE.sub(" <CODE> ", t)
    t = URL_RE.sub(" <URL> ", t)
    t = USER_RE.sub(" <USER> ", t)
    t = SUBR_RE.sub(" <SUBREDDIT> ", t)
    
    emoji_n = len(EMOJI_RE.findall(t))
    t = EMOJI_RE.sub(" ", t)
    
    t = t.lower()
    toks: List[str] = []
    for m in TOK_RE.finditer(t):
        w = m.group(0)
        if w.isdigit() and len(w) > 4:
            toks.append("<num>")
        else:
            toks.append(w)
            
    if len(" ".join(toks)) < min_chars or len(toks) < min_tokens:
        return [], {"dropped": "too_short", "emoji_n": emoji_n}
        
    return toks, {"dropped": None, "emoji_n": emoji_n, "has_code": has_code}


def extract_text(ctype: str, rec: dict) -> str:
    """Extract full raw text depending on submission or comment."""
    if ctype == "comments":
        return rec.get("body", "") or ""
    title = rec.get("title", "") or ""
    selftext = rec.get("selftext", "") or ""
    return (title + "\n\n" + selftext).strip()


def lang_of(text: str, allow_heuristic: bool = True) -> Tuple[str, str]:
    """Lightweight language check: heuristic or fasttext lid if installed."""
    toks = [w.strip(".,!?;:()[]\"'").lower() for w in text.split()[:60]]
    toks = [w for w in toks if w]
    if len(toks) < 5:
        return "short", "skipped_short"
    if not allow_heuristic:
        return "unknown", "detector_required_stopped"
    hit = sum(1 for w in toks if w in FUNC_WORDS) / len(toks)
    return ("en" if hit >= 0.12 else "non-en"), "funcword_heuristic_estimate"


# Self-verifying sanity tests on import
_tests = [
    ("I am NOT happy with r/AskAcademia", ["i", "am", "not", "happy", "with", "<subreddit>"]),
    ("[deleted]", []),
    ("see https://x.io u/someone", ["see", "<url>", "<user>"]),
    ("123456 code ```test```", ["<num>", "code", "<code>"]),
]
for _raw, _expected in _tests:
    _res, _ = clean_and_tokenize(_raw)
    assert _res == _expected, f"Cleaner sanity test failed for {_raw}: got {_res}, expected {_expected}"
