const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');

const sha = bytes => createHash('sha256').update(bytes).digest('hex');

function shardDigest(shard) {
  const bytes = Buffer.alloc(shard.symbols.length * 2);
  shard.symbols.forEach((symbol, i) => bytes.writeUInt16BE(symbol, i * 2));
  return sha(Buffer.concat([Buffer.from('QuorumMend-v1\0'), Buffer.from([shard.slot]), bytes]));
}

function encode(payload) {
  if (!Buffer.isBuffer(payload) || payload.length < 1 || payload.length > 768) throw Error('Payload must be 1–768 bytes');
  const padded = Buffer.concat([payload, Buffer.alloc((3 - payload.length % 3) % 3)]);
  return Array.from({length: 5}, (_, i) => {
    const slot = i + 1;
    const symbols = [];
    for (let offset = 0; offset < padded.length; offset += 3) {
      symbols.push((padded[offset] + slot * padded[offset + 1] + slot ** 2 * padded[offset + 2]) % 257);
    }
    return {slot, symbols};
  });
}

if (require.main === module) {
  const [input, output] = process.argv.slice(2);
  if (!input || !output) throw Error('Usage: node scripts/shards.cjs INPUT OUTPUT_DIRECTORY');
  const payload = fs.readFileSync(input);
  const shards = encode(payload);
  fs.mkdirSync(output, {recursive: true});
  for (const shard of shards) {
    fs.writeFileSync(path.join(output, shard.slot + '.json'), JSON.stringify(shard) + '\n');
  }
  console.log(JSON.stringify({size: payload.length, sha256: sha(payload),
    shards: Object.fromEntries(shards.map(shard => [shard.slot, shardDigest(shard)]))}, null, 2));
}

module.exports = {encode, shardDigest, sha};
