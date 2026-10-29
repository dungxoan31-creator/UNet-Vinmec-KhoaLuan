const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const root = path.resolve(__dirname, '../..');
const directory = path.join(root, 'artifacts', 'synthetic_fixtures');
const python = process.env.PYTHON || path.join(
  root,
  process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python',
);
const required = [
  'synthetic_left.png',
  'synthetic_right.png',
  'synthetic_letterbox_640x480.png',
  'synthetic_color_doppler_640x480.png',
  'synthetic_left.jpg',
  'synthetic_ovary.dcm',
  'fake_corrupted.png',
  'empty_zero_byte.png',
  'oversized_26mb.png',
];

function ensureSyntheticFixtures() {
  if (required.some(name => !fs.existsSync(path.join(directory, name)))) {
    execFileSync(python, ['scripts/generate_synthetic_e2e_fixtures.py'], {
      cwd: root,
      stdio: 'inherit',
    });
  }
  for (const name of required) {
    const file = path.join(directory, name);
    if (!fs.existsSync(file) || !fs.statSync(file).isFile()) {
      throw new Error(`Required synthetic E2E fixture is missing: ${file}`);
    }
  }
  const png = fs.readFileSync(path.join(directory, 'synthetic_left.png'));
  if (!png.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
    throw new Error('Synthetic PNG fixture failed signature validation.');
  }
  if (fs.statSync(path.join(directory, 'oversized_26mb.png')).size <= 25 * 1024 * 1024) {
    throw new Error('Oversized synthetic fixture must exceed the configured 25 MiB boundary.');
  }
  return {
    directory,
    left: path.join(directory, 'synthetic_left.png'),
    right: path.join(directory, 'synthetic_right.png'),
    letterbox: path.join(directory, 'synthetic_letterbox_640x480.png'),
    colorDoppler: path.join(directory, 'synthetic_color_doppler_640x480.png'),
    jpeg: path.join(directory, 'synthetic_left.jpg'),
    dicom: path.join(directory, 'synthetic_ovary.dcm'),
    corrupted: path.join(directory, 'fake_corrupted.png'),
    empty: path.join(directory, 'empty_zero_byte.png'),
    oversized: path.join(directory, 'oversized_26mb.png'),
  };
}

module.exports = { ensureSyntheticFixtures };
