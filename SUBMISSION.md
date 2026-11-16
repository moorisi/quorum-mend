# QuorumMend — Consensus shard recovery

**Category** Builder → Intelligent Contracts

QuorumMend recovers small public artifacts from five externally hosted shards. The leader and validators independently fetch commit-pinned files, check slot-specific commitments, and require exact agreement on decoded symbols before storing a batch. The contract tries three-shard combinations over GF(257) and publishes recovered bytes only when the original payload SHA-256 matches. The StudioNet fixture proved recovery after one committed shard disagreed with the payload, atomic rejection of a tampered batch, and closure after recovery. Slots 2, 3 and 4 recovered the exact 48-byte artifact. Five receipts finalized with MAJORITY_AGREE. The repo includes 18 direct GenVM tests and an independent shard encoder. Each instance supports one public payload of 1–768 bytes.

- [GenLayer contract source](contracts/quorum_mend.py)
- [StudioNet deployment](https://explorer-studio.genlayer.com/tx/0x81a29a3c2ddbb705a2278bc73f6ea543408aeafdf7d0063430af5cc33d7baca3)
- [Recovery transaction](https://explorer-studio.genlayer.com/tx/0x94b0f2ad44f89e0647cc5080108798d05397205eb7f59f837ea90139684232ec)
- [Full proof bundle](proofs/README.md)
