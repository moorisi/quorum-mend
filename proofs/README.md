# StudioNet proofs

Contract address 0x0eFA1900075F4e8f3E50f801d6E7628D7Ce4AA38

All five receipts finalized with MAJORITY_AGREE. The live run used two callers and compared the fresh state and manifest after every call. The fixture is a synthetic 48-byte public artifact.

[Workflow](https://github.com/moorisi/quorum-mend/actions/runs/43754699905) · [Verified reads and fixture checks](verified.json)

| Outcome | Explorer | Receipt | Agree / disagree / idle |
| --- | --- | --- | --- |
| Deployed the five-slot commitment | [Transaction](https://explorer-studio.genlayer.com/tx/0x81a29a3c2ddbb705a2278bc73f6ea543408aeafdf7d0063430af5cc33d7baca3) | [JSON](deploy-receipt.json) | 5 / 0 / 0 |
| Retained three matching shard commitments with no payload match | [Transaction](https://explorer-studio.genlayer.com/tx/0xd4772a82a665c7c6a94e34440771109c412ca2957059d76605ce492e230f4fd6) | [JSON](poisoned-basis-receipt.json) | 3 / 0 / 2 |
| Rejected tampered slot 5 and retained no part of its batch | [Transaction](https://explorer-studio.genlayer.com/tx/0x3e1d94a8fef5af119d8bd8627cac3ee426efee916f529a855647ba309b244cdb) | [JSON](reject-tampered-batch-receipt.json) | 3 / 0 / 2 |
| Recovered the exact payload with slots 2, 3 and 4 | [Transaction](https://explorer-studio.genlayer.com/tx/0x94b0f2ad44f89e0647cc5080108798d05397205eb7f59f837ea90139684232ec) | [JSON](recover-receipt.json) | 3 / 0 / 2 |
| Rejected collection after recovery | [Transaction](https://explorer-studio.genlayer.com/tx/0xd8d1fa969700760d25c375b85a38fb2929316c5716c149e12c4dec17aafa9cb3) | [JSON](reject-after-recovery-receipt.json) | 4 / 0 / 1 |

The recovered bytes matched the original file and SHA-256 commitment. Slot 1 had a valid shard hash but belonged to a different codeword. Slot 5 failed its shard hash, so the batch containing slots 4 and 5 added neither. A separate request for slot 4 completed recovery.

Artifact SHA-256 ccab0066a67c4d9dce7f35c90fd38867bc0b54c189948035449749338787603e

Source revision 8242659927ff5b492f3fc3acd0ef7a1caea55898

Source SHA-256 edfac3351d34975c394f3e4a464773dba3ed1c7181822ae7cbb24de8f3d63b6d
