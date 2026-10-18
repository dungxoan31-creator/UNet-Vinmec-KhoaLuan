const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const csv = process.env.SMOKE_VALIDATION_CSV || 'ai_training/splits/unified_vinmec_clean_2026-10-06/val.csv';
const [header,...rows] = fs.readFileSync(path.resolve(root,csv),'utf8').trim().split(/\r?\n/);
const imageColumn = header.split(',').indexOf('image_path');
module.exports = rows.map(row=>row.split(',')[imageColumn]).filter(Boolean).map(recorded=>{
  const original = path.resolve(root,recorded);
  return fs.existsSync(original) ? original : path.resolve(root,recorded.replace('dataset/Vinmec/Vinmec_2d/images/','dataset/2d/images/'));
}).filter(file=>fs.existsSync(file)).slice(0,2).map(file=>({
  name:path.basename(file), mimeType:/\.png$/i.test(file)?'image/png':'image/jpeg', buffer:fs.readFileSync(file),
}));
