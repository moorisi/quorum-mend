# QuorumMend

QuorumMend recovers a small committed public artifact from five externally hosted shards. It gives onchain consumers the actual recovered bytes and identifies which three shard slots produced them. A useful payload can be a compact configuration, manifest, or protocol parameter file.

The constructor takes one string consisting of the prefix `qm1:` and a JSON object with `size`, `sha256`, and `sources`. The five sources appear in shard-slot order. Each has a distinct commit-pinned raw GitHub `url` and a lowercase `sha256` of the normalized shard. The payload size is 1–768 bytes. Anyone can call `collect(mask)` with bits 0–4 selecting shard slots 1–5. GenLayer fetches the selected sources in one transaction.

The leader and each validator independently download the source bodies. They check the slot, symbol positions and ranges, and each SHA-256 commitment. They require exact equality of the decoded symbol arrays. JSON whitespace can vary. A failed download or mismatched commitment rejects the entire batch before any shard is added.

Three bytes form the coefficients of a quadratic over the prime field GF(257). Each shard contains the evaluation at its slot number for every three-byte stripe. Pad the last stripe with zero bytes. A shard document is a JSON object with `slot` and `symbols`. Its digest covers the ASCII tag `QuorumMend-v1`, a zero byte, one byte containing the slot, then each symbol as an unsigned 16-bit big-endian value.

The contract tries triples in lexicographic slot order. A candidate must decode entirely to bytes, have zero padding, and match the original payload digest. This lets a later shard repair a case where one source matched its own commitment but was inconsistent with the payload. If all five slots arrive with no matching triple, the state is `EXHAUSTED`. `get_state()` exposes the accepted slots and, on recovery, the basis and bytes in hex. `get_manifest()` returns the immutable commitment.

Successful recovery attests to byte integrity relative to the publisher's digest. Source availability depends on the configured repositories. Payloads and shards are public. The encoding uses polynomial interpolation over GF(257), with a project-specific wire format.

[GenLayer web access](https://docs.genlayer.com/developers/intelligent-contracts/features/web-access) · [Reed–Solomon erasure coding background](https://www.rfc-editor.org/info/rfc5510/)

## Verification

```sh
pip install -r requirements-dev.txt
genvm-lint download --version v0.2.16
genvm-lint check contracts/quorum_mend.py
python -m pytest tests/direct -q
npm ci
node --test tests/rpc-preflight.test.cjs
node scripts/shards.cjs path/to/payload path/to/output
```

The live proof uses a synthetic configuration fixture committed to this repository. Slot 1 matches its declared shard digest while disagreeing with the artifact. Slot 5 differs from its declared digest. The independent JavaScript encoder checks which downloaded shards match the original bytes. The proof then verifies signed calldata, exact recovery, rollback of a batch containing the tampered shard, and rejection after completion. Generic CLI receipt transport is reused under MIT.
