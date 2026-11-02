#!/usr/bin/env node
// kordoc 4.22.13 의 HWP5 읽기 상한을 올린다.
//   MAX_SECTIONS 100 → 2000 : 구역이 100개를 넘으면 나머지 구역을 조용히 버림
//   MAX_RECORDS  5e5 → 5e6  : 한 구역의 레코드가 50만 개를 넘으면 나머지를 조용히 버림
// 과기정통부 2027 사업설명자료 1·5·6권에서 사업 58개가 이 때문에 빠졌다.
// npm ci 로 새로 설치할 때마다 ensure-env.sh 가 실행한다. 여러 번 실행해도 결과는 같다.
// 사용: node patch-limits.cjs <kordoc dist 폴더> [--check]
'use strict';
const fs = require('fs');
const path = require('path');

const RULES = [
  ['var MAX_SECTIONS = 100;', 'var MAX_SECTIONS = 2000;'],
  ['var MAX_RECORDS = 5e5;', 'var MAX_RECORDS = 5e6;'],
];

const dist = process.argv[2];
const checkOnly = process.argv.includes('--check');
if (!dist || !fs.existsSync(dist)) {
  console.error('usage: patch-limits.cjs <kordoc/dist> [--check]');
  process.exit(2);
}

const counts = RULES.map(() => ({ before: 0, after: 0 }));
const changes = [];
for (const name of fs.readdirSync(dist)) {
  if (!name.endsWith('.js')) continue;
  const file = path.join(dist, name);
  let text = fs.readFileSync(file, 'utf8');
  let changed = false;
  RULES.forEach(([from, to], i) => {
    counts[i].before += text.split(from).length - 1;
    counts[i].after += text.split(to).length - 1;
    if (!checkOnly && text.includes(from)) {
      text = text.split(from).join(to);
      changed = true;
    }
  });
  if (changed) changes.push([file, text]);
}

// 상수 문구를 하나도 찾지 못하면 kordoc 버전이 바뀐 것이다. 아무것도 쓰지 않고 멈춘다.
for (const [i, [from, to]] of RULES.entries()) {
  if (counts[i].before + counts[i].after === 0) {
    console.error(`kordoc 상한 상수를 찾지 못함: ${from} — kordoc 버전을 확인하세요`);
    process.exit(1);
  }
}
if (checkOnly) {
  const left = RULES.filter((_, i) => counts[i].before > 0).map(([from]) => from);
  if (left.length) {
    console.error('kordoc 상한이 올려지지 않음: ' + left.join(', '));
    process.exit(1);
  }
  console.error('kordoc 상한 확인: 구역 2000, 레코드 5e6');
  process.exit(0);
}
for (const [file, text] of changes) fs.writeFileSync(file, text);
console.error(`kordoc 상한 올림: 파일 ${changes.length}개 수정 (구역 2000, 레코드 5e6)`);
