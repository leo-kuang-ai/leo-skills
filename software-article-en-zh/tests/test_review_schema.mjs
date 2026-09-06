import test from 'node:test'; import assert from 'node:assert/strict'; import fs from 'node:fs'; import path from 'node:path';
const root=path.resolve(path.dirname(new URL(import.meta.url).pathname),'..');
const schema=JSON.parse(fs.readFileSync(path.join(root,'assets/review.schema.json'),'utf8'));
const rubric=fs.readFileSync(path.join(root,'references/review-rubric.md'),'utf8');
const issueTypes=schema.properties.issue_type.enum;
const required=schema.required;
const base={block_id:'b1',category:'semantic_fidelity',severity:'major',status:'open'};
test('issue_type is optional and backward compatible',()=>{
  assert.equal(schema.properties.issue_type.enum.length,7);
  assert.ok(!required.includes('issue_type'));
});
test('accepts every documented issue_type value',()=>{
  for(const v of issueTypes) assert.equal(typeof v,'string');
  assert.deepEqual([...issueTypes].sort(),['editorial_overreach','intensification','mistranslation','omission','structure_damage','terminology_inconsistency','weakening']);
});
test('rejects an unknown issue_type value',()=>{
  assert.ok(!issueTypes.includes('style-preference'));
});
test('rubric documents every schema issue_type token',()=>{
  for(const v of issueTypes) assert.ok(rubric.includes(`\`${v}\``),`rubric missing token ${v}`);
});
test('rubric documents the seven Chinese issue names',()=>{
  for(const name of ['漏译','误译','语义强化','语义弱化','术语不一致','结构损坏','编辑越界']) assert.ok(rubric.includes(name),`rubric missing name ${name}`);
});
test('rubric records the conjunctive publication verdict',()=>{
  assert.ok(/不抵消保真失败/.test(rubric));
  assert.ok(/合取/.test(rubric));
});
