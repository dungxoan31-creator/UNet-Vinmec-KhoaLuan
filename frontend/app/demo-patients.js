// Synthetic local demonstration records, never imported as real patient identities.
const surnames = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Huỳnh', 'Phan', 'Vũ', 'Võ', 'Đặng', 'Bùi', 'Đỗ', 'Hồ', 'Ngô', 'Dương'];
const names = ['Minh Anh', 'Thu Hà', 'Ngọc Mai', 'Thanh Vy', 'Thảo Nguyên', 'Khánh Linh', 'Bảo Ngọc', 'Phương Thảo', 'Quỳnh Anh', 'Hồng Nhung', 'Kim Chi', 'Hải Yến', 'Mai Phương', 'Thùy Dung', 'Ngọc Hân', 'Thanh Tâm', 'Mỹ Linh', 'Diệu Hương', 'Tú Anh', 'Lan Hương'];
export const DEMO_PATIENTS = surnames.flatMap((surname, i) => names.map((name, j) => ({
  name: `${surname} ${name}`, age: 18 + (i * 17 + j * 3) % 58, synthetic: true,
})));
export const patientSearchKey = value => String(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
