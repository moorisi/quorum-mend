# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from hashlib import sha256
from itertools import combinations
import json
import re


FIELD = 257
SLOTS = (1, 2, 3, 4, 5)
MAX_BYTES = 768
PINNED_RAW_URL = (
    r'https://raw\.githubusercontent\.com/[A-Za-z0-9-]{1,39}/'
    r'[A-Za-z0-9._-]{1,100}/[0-9a-f]{40}/'
    r'(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.json'
)


def fail(message):
    raise gl.vm.UserError(message)


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def parse(text, error):
    try:
        return json.loads(text, object_pairs_hook=unique_fields)
    except (ValueError, UnicodeError):
        fail(error)


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def normalize_manifest(text):
    if not text.startswith('qm1:') or len(text) > 4096:
        fail('Invalid manifest')
    item = parse(text[4:], 'Invalid manifest')
    if not isinstance(item, dict) or set(item) != {'size', 'sha256', 'sources'}:
        fail('Invalid manifest')
    size, digest, sources = item['size'], item['sha256'], item['sources']
    if type(size) is not int or not 1 <= size <= MAX_BYTES or not valid_hash(digest):
        fail('Invalid artifact commitment')
    if not isinstance(sources, list) or len(sources) != len(SLOTS):
        fail('Exactly five shard sources required')
    used_urls = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != {'url', 'sha256'} or not valid_hash(source['sha256']):
            fail('Invalid shard source')
        url = source['url']
        if (not isinstance(url, str) or len(url) > 330 or re.fullmatch(PINNED_RAW_URL, url) is None
                or url in used_urls):
            fail('Shard URLs must be distinct and commit-pinned')
        used_urls.add(url)
    return item


def shard_digest(slot, symbols):
    packed = b''.join(symbol.to_bytes(2, 'big') for symbol in symbols)
    return sha256(b'QuorumMend-v1\0' + bytes([slot]) + packed).hexdigest()


def read_shard(slot, source, stripes):
    response = gl.nondet.web.get(source['url'])
    if response.status != 200 or not 1 <= len(response.body) <= 8192:
        fail('Shard not available: ' + str(slot))
    try:
        text = response.body.decode('utf-8')
    except UnicodeError:
        fail('Invalid shard JSON: ' + str(slot))
    shard = parse(text, 'Invalid shard JSON: ' + str(slot))
    if not isinstance(shard, dict) or set(shard) != {'slot', 'symbols'}:
        fail('Invalid shard shape: ' + str(slot))
    if type(shard['slot']) is not int or shard['slot'] != slot:
        fail('Wrong shard slot: ' + str(slot))
    symbols = shard['symbols']
    if (not isinstance(symbols, list) or len(symbols) != stripes
            or any(type(symbol) is not int or not 0 <= symbol < FIELD for symbol in symbols)):
        fail('Invalid shard symbols: ' + str(slot))
    if shard_digest(slot, symbols) != source['sha256']:
        fail('Shard commitment mismatch: ' + str(slot))
    return symbols


def observe(slots, manifest):
    stripes = (manifest['size'] + 2) // 3

    def collect():
        return [read_shard(slot, manifest['sources'][slot - 1], stripes) for slot in slots]

    def verify(proposal):
        try:
            independent = collect()
        except gl.vm.UserError as error:
            return not isinstance(proposal, gl.vm.Return) and getattr(proposal, 'message', None) == error.message
        except Exception:
            return False
        if not isinstance(proposal, gl.vm.Return):
            return False
        return json.dumps(independent) == json.dumps(proposal.calldata)

    return gl.vm.run_nondet_unsafe(collect, verify)


def interpolate(points, shards):
    """Recover byte coefficients of a quadratic at each stripe using Lagrange bases."""
    weights = []
    for point in points:
        first, second = (other for other in points if other != point)
        inverse = pow((point - first) * (point - second) % FIELD, FIELD - 2, FIELD)
        weights.append((first * second * inverse, -(first + second) * inverse, inverse))
    result = bytearray()
    for values in zip(*(shards[str(point)] for point in points)):
        for coefficient in range(3):
            value = sum(values[i] * weights[i][coefficient] for i in range(3)) % FIELD
            if value == 256:
                return None
            result.append(value)
    return bytes(result)


def repair(shards, size, digest):
    for points in combinations(sorted(int(slot) for slot in shards), 3):
        candidate = interpolate(points, shards)
        if candidate is not None and not any(candidate[size:]) and sha256(candidate[:size]).hexdigest() == digest:
            return {'basis': list(points), 'payload_hex': candidate[:size].hex()}
    return None


class QuorumMend(gl.Contract):
    commitment: str
    collected: str
    outcome: str

    def __init__(self, manifest: str):
        self.commitment = json.dumps(normalize_manifest(manifest), sort_keys=True, separators=(',', ':'))
        self.collected = '{}'
        self.outcome = ''

    @gl.public.write
    def collect(self, mask: int) -> None:
        if self.outcome:
            fail('Artifact already recovered')
        if type(mask) is not int or not 1 <= mask <= 31:
            fail('Invalid shard mask')
        shards = json.loads(self.collected)
        slots = [slot for slot in SLOTS if mask & (1 << (slot - 1))]
        if any(str(slot) in shards for slot in slots):
            fail('Shard already retained')
        manifest = json.loads(self.commitment)
        values = observe(slots, manifest)
        shards.update((str(slot), symbols) for slot, symbols in zip(slots, values))
        recovery = repair(shards, manifest['size'], manifest['sha256'])
        self.collected = json.dumps(shards, sort_keys=True, separators=(',', ':'))
        if recovery is not None:
            self.outcome = json.dumps(recovery, sort_keys=True, separators=(',', ':'))

    @gl.public.view
    def get_manifest(self) -> dict:
        return json.loads(self.commitment)

    @gl.public.view
    def get_state(self) -> dict:
        accepted = sorted(int(key) for key in json.loads(self.collected))
        if self.outcome:
            return {'status': 'RECOVERED', 'accepted': accepted, **json.loads(self.outcome)}
        status = 'COLLECTING' if len(accepted) < 3 else 'EXHAUSTED' if len(accepted) == 5 else 'NO_MATCH'
        return {'status': status, 'accepted': accepted, 'basis': [], 'payload_hex': None}
