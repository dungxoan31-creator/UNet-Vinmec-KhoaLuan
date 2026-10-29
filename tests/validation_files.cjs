const fs = require('node:fs');
const { ensureSyntheticFixtures } = require('./helpers/synthetic_fixtures.cjs');

const fixtures = ensureSyntheticFixtures();
module.exports = [fixtures.left, fixtures.right].map(file => ({
  name: file.split(/[\\/]/).pop(),
  mimeType: 'image/png',
  buffer: fs.readFileSync(file),
}));
