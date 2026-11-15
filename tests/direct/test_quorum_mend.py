from hashlib import sha256
from itertools import combinations
import json
import re

import pytest


PAYLOAD = bytes([0, 255, 128, 17, 9, 0, 66, 3])
BASE = 'https://raw.githubusercontent.com/moorisi/quorum-mend/' + 'a' * 40 + '/fixtures/live/'


def encode_shares(payload):
    data = payload + b'\0' * (-len(payload) % 3)
    return {
        i: {'slot': i, 'symbols': [(a + b * i + c * i * i) % 257
                                  for a, b, c in zip(data[::3], data[1::3], data[2::3])]}
        for i in range(1, 6)
    }


def manifest(shares, payload=PAYLOAD):
    return {
        'size': len(payload), 'sha256': sha256(payload).hexdigest(),
        'sources': [{'url': BASE + f'{i}.json',
                     'sha256': sha256(b'QuorumMend-v1\0' + bytes([i]) +
                                      bytes(value for number in shares[i]['symbols'] for value in divmod(number, 256))).hexdigest()}
                    for i in range(1, 6)]
    }


def deploy(direct_deploy, commitment):
    return direct_deploy('contracts/quorum_mend.py', 'qm1:' + json.dumps(commitment), sdk_version='v0.2.16')


def reply(vm, slot, document, status=200):
    body = document if isinstance(document, bytes) else json.dumps(document).encode()
    vm.mock_web(re.escape(BASE + f'{slot}.json'), {'status': status, 'body': body})


def mock_shares(vm, shares):
    vm.clear_mocks()
    for slot, shard in shares.items():
        reply(vm, slot, shard)


def mask(slots):
    return sum(1 << (slot - 1) for slot in slots)


@pytest.mark.parametrize('basis', list(combinations(range(1, 6), 3)))
def test_every_three_shard_basis(direct_vm, direct_deploy, basis):
    shares = encode_shares(PAYLOAD)
    contract = deploy(direct_deploy, manifest(shares))
    assert contract.get_state()['status'] == 'COLLECTING'
    mock_shares(direct_vm, shares)
    contract.collect(mask(basis))
    assert direct_vm.run_validator() is True
    assert contract.get_state() == {'status': 'RECOVERED', 'accepted': list(basis), 'basis': list(basis),
                                    'payload_hex': PAYLOAD.hex()}


def test_poisoned_commitment_and_atomic_retry(direct_vm, direct_deploy, direct_bob):
    shares = encode_shares(PAYLOAD)
    shares[1]['symbols'][0] = (shares[1]['symbols'][0] + 1) % 257
    original = manifest(shares)
    contract = deploy(direct_deploy, original)
    shares[5]['symbols'][0] = (shares[5]['symbols'][0] + 1) % 257
    mock_shares(direct_vm, shares)
    contract.collect(mask([1, 2, 3]))
    waiting = {'status': 'NO_MATCH', 'accepted': [1, 2, 3], 'basis': [], 'payload_hex': None}
    assert contract.get_state() == waiting
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert('Shard commitment mismatch: 5'):
        contract.collect(mask([4, 5]))
    assert contract.get_state() == waiting
    contract.collect(mask([4]))
    result = {'status': 'RECOVERED', 'accepted': [1, 2, 3, 4], 'basis': [2, 3, 4], 'payload_hex': PAYLOAD.hex()}
    assert contract.get_state() == result
    assert contract.get_manifest() == original
    with direct_vm.expect_revert('Artifact already recovered'):
        contract.collect(mask([5]))
    assert contract.get_state() == result


def test_validator_reads_symbols_and_ignores_json_whitespace(direct_vm, direct_deploy):
    shares = encode_shares(PAYLOAD)
    contract = deploy(direct_deploy, manifest(shares))
    reply(direct_vm, 1, shares[1])
    contract.collect(1)
    direct_vm.clear_mocks()
    reply(direct_vm, 1, json.dumps(shares[1], indent=4).encode())
    assert direct_vm.run_validator() is True
    shares[1]['symbols'][0] = (shares[1]['symbols'][0] + 1) % 257
    direct_vm.clear_mocks()
    reply(direct_vm, 1, shares[1])
    assert direct_vm.run_validator() is False
    with direct_vm.expect_revert('Shard already retained'):
        contract.collect(1)


def test_unsatisfiable_payload_stops_with_all_slots_present(direct_vm, direct_deploy):
    shares = encode_shares(PAYLOAD)
    commitment = manifest(shares, bytes(reversed(PAYLOAD)))
    contract = deploy(direct_deploy, commitment)
    mock_shares(direct_vm, shares)
    contract.collect(31)
    assert contract.get_state() == {'status': 'EXHAUSTED', 'accepted': [1, 2, 3, 4, 5], 'basis': [],
                                    'payload_hex': None}


@pytest.mark.parametrize(('document', 'status', 'error'), [
    ({}, 404, 'Shard not available: 1'),
    (b'{"slot":1,"slot":1,"symbols":[1,2,3]}', 200, 'Invalid shard JSON: 1'),
    ({'slot': 2, 'symbols': [0, 0, 0]}, 200, 'Wrong shard slot: 1'),
    ({'slot': 1, 'symbols': [False, 0, 0]}, 200, 'Invalid shard symbols: 1'),
    ({'slot': 1, 'symbols': [257, 0, 0]}, 200, 'Invalid shard symbols: 1'),
])
def test_invalid_fetch_does_not_retain_data(direct_vm, direct_deploy, document, status, error):
    contract = deploy(direct_deploy, manifest(encode_shares(PAYLOAD)))
    reply(direct_vm, 1, document, status)
    with direct_vm.expect_revert(error):
        contract.collect(1)
    assert contract.get_state()['accepted'] == []
