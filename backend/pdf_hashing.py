import re

def compute_simhash(text: str, bits: int = 64) -> int:
    """Compute a SimHash fingerprint of the given text.
    Similar texts produce hashes with low Hamming distance.
    Returns an integer fingerprint."""
    import hashlib as _hl
    tokens = re.findall(r'\w+', text.lower())
    if not tokens:
        return 0
    v = [0] * bits
    for token in tokens:
        h = int(_hl.md5(token.encode("utf-8", errors="replace")).hexdigest(), 16)
        for i in range(bits):
            if h & (1 << i):
                v[i] += 1
            else:
                v[i] -= 1
    fingerprint = 0
    for i in range(bits):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint & 0x7FFF_FFFF_FFFF_FFFF


def simhash_distance(h1: int, h2: int) -> int:
    """Hamming distance between two SimHash fingerprints (number of differing bits)."""
    x = h1 ^ h2
    dist = 0
    while x:
        dist += x & 1
        x >>= 1
    return dist


def simhash_similarity(h1: int, h2: int, bits: int = 64) -> float:
    """Similarity [0.0 – 1.0] between two SimHash fingerprints."""
    if h1 == 0 and h2 == 0:
        return 1.0
    return 1.0 - simhash_distance(h1, h2) / bits
