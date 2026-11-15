const fs = require('node:fs');
const {assert, equal, sourceHash, invoke, read, rpc, receipt, receiptSummary, save} = require('./transport.cjs');
const {decodeReceipt} = require('./receipt-calldata.cjs');
const {encode, shardDigest, sha} = require('./shards.cjs');

async function main() {
  const revision = process.env.GITHUB_SHA;
  assert(/^[a-f0-9]{40}$/.test(revision || ''), 'Proof needs a public fixture commit');
  const source = 'https://raw.githubusercontent.com/moorisi/quorum-mend/' + revision + '/fixtures/live/';
  const wallets = JSON.parse(process.env.MEND_ACCOUNTS || '[]');
  assert(wallets.length === 2 && wallets[0].address !== wallets[1].address, 'Two distinct wallets required');
  const payload = Buffer.from(fs.readFileSync('fixtures/payload.hex', 'utf8').trim(), 'hex');
  const code = fs.readFileSync('contracts/quorum_mend.py');
  const honest = encode(payload);
  const fetched = await Promise.all(honest.map(async ({slot}) => {
    const response = await fetch(source + slot + '.json', {signal: AbortSignal.timeout(25000)});
    assert(response.ok, 'Fixture HTTP ' + response.status);
    const shard = await response.json();
    assert(shard.slot === slot, 'Fixture slot mismatch');
    return shard;
  }));
  const matching = fetched.filter((shard, index) => equal(shard, honest[index])).map(shard => shard.slot);
  assert(equal(matching, [2,3,4]), 'Expected exactly three shards of the original codeword');
  const manifest = {size: payload.length, sha256: sha(payload),
    sources: fetched.map(shard => ({url: source + shard.slot + '.json',
      sha256: shardDigest(shard.slot === 5 ? honest[4] : shard)}))};
  assert(shardDigest(fetched[4]) !== manifest.sources[4].sha256, 'Slot five must violate its commitment');
  const argument = 'qm1:' + JSON.stringify(manifest);
  assert(await rpc('eth_chainId', []) === '0xf22f', 'StudioNet only');

  process.env.MEND_ACCOUNT = wallets[0].name;
  const deployment = await invoke('deploy', ['deploy', '--contract', 'contracts/quorum_mend.py', '--args', argument]);
  const deployed = await receipt('deploy', deployment, true);
  const contract = deployed.to_address || deployed.recipient;
  assert(/^0x[0-9a-f]{40}$/i.test(contract), 'Missing deployed contract');
  assert(code.equals(Buffer.from(deployed.data.contract_code, 'base64')), 'Deployment source mismatch');
  const report = {contract, deployment, revision, source_sha256: sourceHash, manifest,
    fixture_checks: fetched.map(shard => ({slot: shard.slot, is_original: matching.includes(shard.slot),
      source: manifest.sources[shard.slot - 1].url, observed_commitment: shardDigest(shard)})), trace: []};

  const collecting = {status: 'COLLECTING', accepted: [], basis: [], payload_hex: null};
  const waiting = {status: 'NO_MATCH', accepted: [1,2,3], basis: [], payload_hex: null};
  const recovered = {status: 'RECOVERED', accepted: [1,2,3,4], basis: matching, payload_hex: payload.toString('hex')};

  async function verify(label, raw, actor, args, expected, error) {
    assert((raw.from_address || raw.sender).toLowerCase() === wallets[actor].address
      && (raw.to_address || raw.recipient).toLowerCase() === contract.toLowerCase(), 'Wrong receipt addresses');
    assert(equal(await decodeReceipt(raw), args), 'Unexpected signed calldata');
    if (error) {
      const result = Buffer.from(raw.consensus_data.leader_receipt[0].result, 'base64');
      assert(result[0] === 1 && result.subarray(1).toString() === error, 'Wrong revert');
    }
    const state = await read(label + '-state', ['call', contract, 'get_state']);
    assert(equal(state, expected), 'Unexpected onchain state for ' + label);
    const current = await read(label + '-manifest', ['call', contract, 'get_manifest']);
    assert(equal(current, manifest), 'Unexpected onchain manifest');
    report.trace.push({label, ...receiptSummary(raw), signer: wallets[actor].address, args, error: error || null, state});
    save('progress', report);
  }
  await verify('deploy', deployed, 0, {args: [argument]}, collecting);

  async function collect(label, mask, actor, expected, error) {
    process.env.MEND_ACCOUNT = wallets[actor].name;
    const hash = await invoke(label, ['write', contract, 'collect', '--args', String(mask)]);
    const raw = await receipt(label, hash, !error);
    await verify(label, raw, actor, {method: 'collect', args: [mask]}, expected, error);
  }
  await collect('poisoned-basis', 7, 1, waiting);
  await collect('reject-tampered-batch', 24, 0, waiting, 'Shard commitment mismatch: 5');
  await collect('recover', 8, 1, recovered);
  await collect('reject-after-recovery', 16, 0, recovered, 'Artifact already recovered');
  assert(code.equals(Buffer.from(await rpc('gen_getContractCode', [contract]), 'base64')), 'Fresh source read differs');
  save('verified', report);
  console.log(JSON.stringify({contract, deployment, receipts: report.trace.length, result: recovered}));
}

main().catch(error => { console.error(error); process.exitCode = 1; });
